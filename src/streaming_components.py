"""
Composant micro en temps réel — dictée vocale dans Streamlit.

Architecture :
  - Backend : ``audio_relay.py`` (serveur HTTP local, stdlib, thread-safe)
  - Frontend : JS inliné via ``st.components.v1.html()`` (MediaRecorder + fetch)
  - Transcription : ``NurseLogEngine.transcrire_audio()`` (Whisper local ou API OpenAI)

Flux :
  1. L'utilisateur clique "▶️ Démarrer" dans le widget → le JS capture l'audio
  2. L'utilisateur clique "⏹️ Arrêter" dans le widget → le JS envoie le blob au relay
  3. L'indicateur "✅ Audio prêt" apparaît automatiquement (poll du relay)
  4. L'utilisateur clique "🎧 Transcrire" (bouton Streamlit) → Python lit + transcrit
  5. L'utilisateur peut "🔊 Écouter" l'enregistrement avant transcription
  6. L'utilisateur insère le texte dans sa dictée (ajouter / remplacer / accumuler)

Features v2 :
  - Poll avec timeout au lieu de time.sleep(0.3) → pas de race condition
  - Auto-stop à 5 min + avertissement visuel à 4:30
  - Bouton "🔊 Écouter" pour pré-écouter le blob avant transcription
  - Indicateur "Audio prêt" qui apparaît sans clic
  - Health-check relay (détection crash silencieux)
  - Retry transcription (bouton "🔄 Réessayer" en cas d'échec)
  - Bouton "📋 Copier" (clipboard)
  - Mode accumulation (plusieurs enregistrements → un seul texte concaténé)
"""

from __future__ import annotations

import time

import streamlit as st

from audio_relay import get_audio_relay, mime_vers_extension
from nurselog_engine import NurseLogEngine, TranscriptionError

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

MAX_DURATION_SEC = 300          # 5 minutes max
WARNING_DURATION_SEC = 270      # Avertissement à 4:30
POLL_TIMEOUT_SEC = 5.0          # Timeout pour attendre le POST (5s)
POLL_INTERVAL_SEC = 0.1         # Intervalle de poll (100ms)
MAX_RETRIES = 3                 # Nombre max de retries transcription


# ---------------------------------------------------------------------------
# Widget JavaScript (inliné dans un iframe Streamlit)
# ---------------------------------------------------------------------------

_WIDGET_JS = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 140px; padding: 16px;
    background: #f8f9fa; border-radius: 10px; gap: 12px;
  }
  .controls {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: center;
  }
  .btn {
    padding: 8px 18px; border: none; border-radius: 6px;
    font-size: 0.9rem; cursor: pointer; font-weight: 500;
    transition: background 0.15s, opacity 0.15s;
  }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-start { background: #006699; color: #fff; }
  .btn-start:hover:not(:disabled) { background: #004d66; }
  .btn-stop { background: #dc3545; color: #fff; }
  .btn-stop:hover:not(:disabled) { background: #b02a37; }
  .btn-listen { background: #6c757d; color: #fff; }
  .btn-listen:hover:not(:disabled) { background: #545b62; }
  .status-row {
    display: flex; align-items: center; gap: 8px;
  }
  .rec-dot {
    width: 12px; height: 12px; border-radius: 50%;
    background: #adb5bd; transition: background 0.2s;
  }
  .rec-dot.active {
    background: #dc3545;
    animation: pulse 1.2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.4); }
  }
  .label {
    font-size: 0.9rem; color: #495057;
  }
  .timer {
    font-size: 0.85rem; color: #6c757d; font-variant-numeric: tabular-nums;
  }
  .timer.warning { color: #ffc107; font-weight: bold; }
  .msg {
    font-size: 0.85rem; min-height: 1.2em; text-align: center;
  }
  .msg.ok { color: #28a745; }
  .msg.err { color: #dc3545; }
  .msg.warn { color: #ffc107; }
</style>
</head>
<body>
  <div class="controls">
    <button class="btn btn-start" id="btnStart" onclick="startRec()">▶️ Démarrer</button>
    <button class="btn btn-stop" id="btnStop" onclick="stopRec()" disabled>⏹️ Arrêter</button>
    <button class="btn btn-listen" id="btnListen" onclick="listenRec()" disabled>🔊 Écouter</button>
  </div>
  <div class="status-row">
    <div class="rec-dot" id="dot"></div>
    <span class="label" id="label">Prêt</span>
    <span class="timer" id="timer"></span>
  </div>
  <div class="msg" id="msg"></div>

<script>
const RELAY_URL = "__RELAY_URL__";
const MAX_DURATION = __MAX_DURATION__;
const WARNING_DURATION = __WARNING_DURATION__;

let mediaRecorder = null;
let audioChunks = [];
let stream = null;
let startTime = 0;
let timerInterval = null;
let lastBlob = null;  // Garde le blob pour la pré-écoute

const $ = id => document.getElementById(id);

function setMsg(text, cls = '') {
  const el = $('msg');
  el.textContent = text;
  el.className = 'msg ' + cls;
}

function updateTimer() {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const s = elapsed;
  $('timer').textContent = String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');

  // Avertissement à 4:30
  if (elapsed >= WARNING_DURATION && elapsed < MAX_DURATION) {
    $('timer').classList.add('warning');
    if (elapsed === WARNING_DURATION) {
      setMsg('⚠️ ' + (MAX_DURATION - elapsed) + 's restantes — auto-stop à ' + MAX_DURATION + 's', 'warn');
    }
  }

  // Auto-stop à 5 min
  if (elapsed >= MAX_DURATION) {
    stopRec();
    setMsg('⏱️ Durée max atteinte (' + MAX_DURATION + 's) — enregistrement arrêté automatiquement', 'warn');
  }
}

async function startRec() {
  try {
    setMsg('');
    lastBlob = null;
    $('btnListen').disabled = true;
    $('timer').classList.remove('warning');

    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });

    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
               : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';

    mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    audioChunks = [];

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };

    mediaRecorder.onstop = async () => {
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
      audioChunks = [];

      if (blob.size === 0) { setMsg('⚠️ Enregistrement vide', 'err'); return; }

      // Garder le blob pour la pré-écoute
      lastBlob = blob;
      $('btnListen').disabled = false;

      try {
        const resp = await fetch(RELAY_URL + '/audio', {
          method: 'POST',
          headers: { 'Content-Type': mediaRecorder.mimeType || 'audio/webm' },
          body: blob
        });
        const data = await resp.json();
        if (data.ok) {
          setMsg('✅ Audio reçu (' + (blob.size/1024).toFixed(1) + ' Ko) — prêt à transcrire', 'ok');
        } else {
          setMsg('❌ ' + (data.erreur || 'Erreur serveur'), 'err');
        }
      } catch (err) {
        setMsg('❌ ' + err.message, 'err');
      }
    };

    mediaRecorder.start(1000);
    startTime = Date.now();
    $('dot').classList.add('active');
    $('label').textContent = 'Enregistrement…';
    $('btnStart').disabled = true;
    $('btnStop').disabled = false;
    timerInterval = setInterval(updateTimer, 1000);

  } catch (err) {
    setMsg('❌ Micro refusé : ' + err.message, 'err');
  }
}

function stopRec() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  $('dot').classList.remove('active');
  $('label').textContent = 'Arrêté';
  $('btnStart').disabled = false;
  $('btnStop').disabled = true;
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

function listenRec() {
  if (!lastBlob) return;
  const url = URL.createObjectURL(lastBlob);
  const audio = new Audio(url);
  audio.play().then(() => {
    setMsg('🔊 Lecture en cours…', 'ok');
  }).catch(err => {
    setMsg('❌ Lecture impossible : ' + err.message, 'err');
  });
  audio.onended = () => {
    URL.revokeObjectURL(url);
    setMsg('✅ Lecture terminée', 'ok');
  };
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attendre_nouvel_enregistrement(relay, timestamp_repere: float) -> dict | None:
    """
    Poll le relay jusqu'à ce qu'un nouvel enregistrement (timestamp > repère)
    soit disponible, ou jusqu'au timeout.

    Remplace le time.sleep(0.3) par un poll déterministe.
    """
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    while time.monotonic() < deadline:
        info = relay.get_latest_recording()
        if info is not None and info["horodatage"] > timestamp_repere:
            return info
        time.sleep(POLL_INTERVAL_SEC)
    return None


def _transcrire_avec_retry(
    relay,
    info: dict,
    langue: str | None,
    model: str,
    local_model: str,
) -> tuple[str | None, str | None]:
    """
    Tente la transcription avec retry automatique.

    Returns:
        (texte, erreur) — l'un des deux est None.
    """
    derniere_erreur = None
    for tentative in range(1, MAX_RETRIES + 1):
        try:
            with open(info["path"], "rb") as f:
                audio_bytes = f.read()
            engine = NurseLogEngine()
            texte = engine.transcrire_audio(
                audio_data=audio_bytes,
                filename=f"micro_{int(info['horodatage'])}.{mime_vers_extension(info.get('mime', ''))}",
                langue=langue,
                model=model,
                local_model=local_model,
            )
            return texte, None
        except TranscriptionError as e:
            derniere_erreur = str(e)
        except Exception as e:
            derniere_erreur = f"Erreur inattendue : {e}"
        # Petit délai avant retry (exponentiel)
        if tentative < MAX_RETRIES:
            time.sleep(0.5 * tentative)

    return None, derniere_erreur


# ---------------------------------------------------------------------------
# Composant Streamlit
# ---------------------------------------------------------------------------

def afficher_module_micro(dictee_actuelle: str) -> None:
    """
    Affiche le module de dictée vocale (micro navigateur + transcription).

    Paramètres
    ----------
    dictee_actuelle : str
        Le texte déjà présent dans la zone de dictée (pour l'ajout).
    """

    # --- Vérifier la disponibilité du backend de transcription ---
    statut = NurseLogEngine.statut_transcription()
    if not statut["disponible"]:
        if statut["api_key"] and not statut["openai_installe"]:
            st.warning("⚠️ Le package `openai` n'est pas installé. Exécutez : `pip install openai`")
        else:
            st.info(
                "🎙️ Reconnaissance vocale inactive. Pour l'activer :\n\n"
                "- **API OpenAI** : `pip install openai` + définir `OPENAI_API_KEY`\n"
                "- **100% local (RGPD)** : `pip install openai-whisper` + `ffmpeg`"
            )
        return

    backend = statut["backend"]
    if backend == "openai":
        st.caption("🎙️ Transcription via **API OpenAI**")
    else:
        st.caption("🎙️ Transcription **100% locale** (Whisper) — aucune donnée ne quitte la machine")

    # --- Démarrer le relay audio (singleton, thread daemon) ---
    relay = get_audio_relay()

    # --- Health-check relay ---
    if not relay.is_alive:
        st.error(
            "⚠️ **Relay audio hors ligne** — le serveur local a probablement crashé.\n\n"
            "Rechargez la page (F5) pour redémarrer le relay."
        )
        return

    # --- État de session ---
    if "micro_transcript" not in st.session_state:
        st.session_state.micro_transcript = ""
    if "micro_last_processed_ts" not in st.session_state:
        st.session_state.micro_last_processed_ts = 0.0
    if "micro_accumulated" not in st.session_state:
        st.session_state.micro_accumulated = ""
    if "micro_error" not in st.session_state:
        st.session_state.micro_error = None
    if "micro_retry_info" not in st.session_state:
        st.session_state.micro_retry_info = None

    # --- Widget JS (iframe avec boutons Start/Stop/Listen intégrés) ---
    js_html = (
        _WIDGET_JS
        .replace("__RELAY_URL__", relay.url)
        .replace("__MAX_DURATION__", str(MAX_DURATION_SEC))
        .replace("__WARNING_DURATION__", str(WARNING_DURATION_SEC))
    )
    st.components.v1.html(js_html, height=160, scrolling=False)

    # --- Indicateur "Audio prêt" (apparaît automatiquement, sans clic) ---
    info = relay.get_latest_recording()
    if info is not None and info["horodatage"] > st.session_state.micro_last_processed_ts:
        taille_ko = info["taille"] / 1024
        st.success(f"✅ Audio prêt à transcrire ({taille_ko:.1f} Ko) — cliquez « 🎧 Transcrire » ci-dessous")

    # --- Boutons Transcrire / Effacer ---
    col_transcrire, col_effacer = st.columns([1, 0.4])

    with col_transcrire:
        if st.button("🎧 Transcrire l'enregistrement", use_container_width=True):
            # Repère : timestamp du dernier enregistrement déjà traité
            timestamp_repere = st.session_state.micro_last_processed_ts

            # Poll avec timeout au lieu de time.sleep(0.3)
            info = _attendre_nouvel_enregistrement(relay, timestamp_repere)
            if info is None:
                # Fallback : si aucun nouvel enregistrement, vérifier s'il y en a un
                info = relay.get_latest_recording()
                if info is None:
                    st.warning("⚠️ Aucun audio détecté. Cliquez d'abord ▶️ Démarrer puis ⏹️ Arrêter dans le widget ci-dessus.")
                    return

            # Transcription avec retry
            with st.spinner("🎧 Transcription en cours…"):
                texte, erreur = _transcrire_avec_retry(
                    relay, info,
                    langue=st.session_state.voix_prefs.get("langue"),
                    model=st.session_state.voix_prefs.get("model", "whisper-1"),
                    local_model=st.session_state.voix_prefs.get("model_local", "base"),
                )

            if erreur is not None:
                st.session_state.micro_error = erreur
                st.session_state.micro_retry_info = info
                st.error(f"❌ {erreur}")
                st.error(f"⚠️ {MAX_RETRIES} tentatives échouées.")
                # Bouton retry manuel
                if st.button("🔄 Réessayer manuellement", use_container_width=True):
                    st.session_state.micro_error = None
                    st.session_state.micro_retry_info = None
                    st.rerun()
                return

            # Marquer comme traité
            st.session_state.micro_last_processed_ts = info["horodatage"]
            st.session_state.micro_transcript = texte
            st.session_state.micro_error = None
            st.session_state.micro_retry_info = None
            st.rerun()

    with col_effacer:
        if st.button("✖️ Effacer", use_container_width=True,
                     disabled=not st.session_state.micro_transcript):
            st.session_state.micro_transcript = ""
            st.session_state.micro_accumulated = ""
            st.session_state.micro_error = None
            st.session_state.micro_retry_info = None
            st.rerun()

    # --- Affichage du transcript ---
    if st.session_state.micro_transcript:
        nb_mots = len(st.session_state.micro_transcript.split())
        st.success(f"✅ Transcription terminée ({nb_mots} mots)")

        # --- Mode accumulation : afficher le texte accumulé ---
        if st.session_state.micro_accumulated:
            st.info(f"📎 {len(st.session_state.micro_accumulated.split())} mots déjà accumulés")

        st.text_area(
            "📄 Transcript (modifiable)",
            value=st.session_state.micro_transcript,
            height=150,
            key="micro_transcript_area",
            label_visibility="collapsed",
        )

        # --- Bouton copier ---
        def _texte_final() -> str:
            return (st.session_state.get("micro_transcript_area") or st.session_state.micro_transcript).strip()

        col_copier, col_spacer = st.columns([1, 2])
        with col_copier:
            if st.button("📋 Copier dans le presse-papiers", use_container_width=True):
                # Streamlit n'a pas de clipboard natif → on utilise un JS inline
                st.markdown(f"""
<script>
navigator.clipboard.writeText({_texte_final()!r}).then(() => {{
    // Le feedback est géré par le rerun Streamlit
}});
</script>
""", unsafe_allow_html=True)
                st.success("✅ Copié !")
                st.rerun()

        st.divider()

        # --- Insertion dans la dictée ---
        col_ajouter, col_remplacer, col_accumuler = st.columns([1, 1, 1])

        with col_ajouter:
            if st.button("➕ Ajouter à la dictée", use_container_width=True):
                base = dictee_actuelle.strip()
                st.session_state.dictee_draft = f"{base} {_texte_final()}".strip()
                st.session_state.micro_transcript = ""
                st.session_state.micro_accumulated = ""
                st.rerun()

        with col_remplacer:
            if st.button("🔄 Remplacer la dictée", use_container_width=True):
                st.session_state.dictee_draft = _texte_final()
                st.session_state.micro_transcript = ""
                st.session_state.micro_accumulated = ""
                st.rerun()

        with col_accumuler:
            if st.button("📎 Accumuler", use_container_width=True,
                         help="Ajoute ce passage au texte accumulé (pour dicter en plusieurs segments)"):
                st.session_state.micro_accumulated = (
                    st.session_state.micro_accumulated + " " + _texte_final()
                ).strip()
                st.session_state.micro_transcript = ""
                st.rerun()

    # --- Zone d'accumulation (si des passages ont été accumulés) ---
    if st.session_state.micro_accumulated and not st.session_state.micro_transcript:
        st.info("📎 **Texte accumulé** (plusieurs segments) :")
        st.text_area(
            "Texte accumulé (modifiable)",
            value=st.session_state.micro_accumulated,
            height=200,
            key="micro_accumulated_area",
            label_visibility="collapsed",
        )

        def _accumule_final() -> str:
            return (st.session_state.get("micro_accumulated_area") or st.session_state.micro_accumulated).strip()

        col_ins, col_valider, col_annuler = st.columns([1, 1, 0.5])

        with col_ins:
            if st.button("✅ Insérer dans la dictée", use_container_width=True):
                base = dictee_actuelle.strip()
                st.session_state.dictee_draft = f"{base} {_accumule_final()}".strip()
                st.session_state.micro_accumulated = ""
                st.rerun()

        with col_valider:
            if st.button("🔄 Remplacer la dictée", use_container_width=True):
                st.session_state.dictee_draft = _accumule_final()
                st.session_state.micro_accumulated = ""
                st.rerun()

        with col_annuler:
            if st.button("✖️", help="Annuler l'accumulation", use_container_width=True):
                st.session_state.micro_accumulated = ""
                st.rerun()
