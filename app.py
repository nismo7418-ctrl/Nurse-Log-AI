"""
NurseLog AI - Assistant de Documentation Infirmière par IA
Prototype MVP - Belgium Edition
"""

import copy
import datetime
import json
import os
import sys

# Ajouter le dossier src au chemin d'import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import streamlit as st
from nurselog_engine import NurseLogEngine, TranscriptionError
from templates import RAPPORT_TEMPLATE
from database import (
    sauvegarder_rapport,
    recuperer_historique,
    recuperer_stats,
    sauvegarder_infirmier,
    sauvegarder_brouillon,
    recuperer_brouillon,
    supprimer_brouillon,
    generer_pdf_rapport,
    exporter_pdf_rapport,
)

# ============ CONFIGURATION PAGE ============
st.set_page_config(
    page_title="NurseLog AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ CUSTOM CSS (responsive) ============
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #006699;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .report-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #006699;
        margin-bottom: 15px;
    }
    .alert-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #ffc107;
        margin-bottom: 15px;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin-bottom: 15px;
    }
    .stButton > button {
        width: 100%;
        background-color: #006699;
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 1rem;
        border-radius: 8px;
    }
    .stButton > button:hover {
        background-color: #004d66;
    }
    .signature-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-top: 20px;
        border: 2px dashed #006699;
    }
    .badge-bientot {
        display: inline-block;
        background-color: #e9ecef;
        color: #6c757d;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.9rem;
        border: 1px solid #dee2e6;
    }
    /* Responsive: empiler les colonnes sur mobile/tablette */
    @media (max-width: 768px) {
        .main-header { font-size: 1.8rem; }
        .sub-header { font-size: 0.95rem; }
        .stButton > button { padding: 10px 16px; font-size: 0.9rem; }
    }
</style>
""", unsafe_allow_html=True)

# ============ INITIALISATION SESSION STATE ============
if 'rapport' not in st.session_state:
    st.session_state.rapport = None
if 'validated' not in st.session_state:
    st.session_state.validated = False
if 'infirmier_id' not in st.session_state:
    st.session_state.infirmier_id = None
if 'rapport_origin_page' not in st.session_state:
    st.session_state.rapport_origin_page = None
if 'dictee_draft' not in st.session_state:
    st.session_state.dictee_draft = ""

# ============ INITIALISATION ENGINE ============
engine = NurseLogEngine()

# ============ INITIALISATION BASE DE DONNEES ============
from database import initialiser_base
initialiser_base()  # Activer l'initialisation pour l'application principale

# ============ INITIALISATION PDF EXPORT ============
# Le drapeau reflète la disponibilité réelle de ReportLab (dépendance optionnelle).
import importlib.util
PDF_EXPORT_AVAILABLE = importlib.util.find_spec("reportlab") is not None

# ============ CONFIGURATION RECONNAISSANCE VOCALE ============
# Le moteur gère les backends (API OpenAI / Whisper local) et la validation.
# L'interface n'affiche que le statut et les préférences utilisateur.
VOIX_STATUT = NurseLogEngine.statut_transcription()

# Préférences utilisateur (persistées en session)
if "voix_prefs" not in st.session_state:
    st.session_state.voix_prefs = {
        "langue": "Auto",          # Auto / Français / Néerlandais
        "model": "whisper-1",      # modèle API OpenAI
        "model_local": "base",     # taille Whisper local (tiny / base / small)
    }
# Migration : ajouter la taille de modèle local aux préférences existantes
if "model_local" not in st.session_state.voix_prefs:
    st.session_state.voix_prefs["model_local"] = "base"

# ============ MODULE VOIX (dictée rapide) ============
def _afficher_module_voix(dictee_actuelle: str):
    """
    Module de reconnaissance vocale : upload audio, transcription via le
    moteur (API OpenAI ou Whisper local), aperçu et insertion dans la dictée.
    """
    if not VOIX_STATUT["disponible"]:
        # Aucun backend : afficher un guide d'installation clair
        if VOIX_STATUT["api_key"] and not VOIX_STATUT["openai_installe"]:
            st.warning("⚠️ Le package `openai` n'est pas installé. Exécutez : `pip install openai`")
        elif not VOIX_STATUT["api_key"]:
            st.info(
                "🎙️ Reconnaissance vocale inactive. Pour l'activer :\n\n"
                "- **API OpenAI** : installez `openai` (`pip install openai`) "
                "et définissez `OPENAI_API_KEY`\n"
                "- **100% local (RGPD)** : installez `openai-whisper` "
                "(`pip install openai-whisper`)"
            )
        return

    backend = VOIX_STATUT["backend"]
    if backend == "openai":
        st.success("🎙️ Transcription via **API OpenAI** (vocabulaire médical activé)")
    else:
        st.success("🎙️ Transcription **100% locale** (Whisper) — aucune donnée ne quitte la machine")
        if not VOIX_STATUT.get("ffmpeg_disponible"):
            st.warning(
                "⚠️ `ffmpeg` n'est pas détecté — requis par Whisper local pour décoder l'audio.\n\n"
                "Installation : **Windows** `winget install Gyan.FFmpeg` — "
                "**macOS** `brew install ffmpeg` — **Linux** `sudo apt install ffmpeg`\n\n"
                "Puis relancez l'application."
            )

    formats = [f".{f}" for f in VOIX_STATUT["formats"]]
    audio_file = st.file_uploader(
        "Fichier audio de la dictée",
        type=VOIX_STATUT["formats"],
        key="audio_uploader",
        help=f"Formats acceptés : {', '.join(formats)} — max {VOIX_STATUT['taille_max_mo']} Mo",
    )

    if audio_file is None:
        return

    # --- Informations sur le fichier ---
    taille_mo = audio_file.size / (1024 * 1024)
    info_col, btn_col = st.columns([3, 1])
    with info_col:
        statut_taille = "✅" if taille_mo <= VOIX_STATUT["taille_max_mo"] else "⚠️"
        st.caption(f"{statut_taille} `{audio_file.name}` — {taille_mo:.2f} Mo (max {VOIX_STATUT['taille_max_mo']} Mo)")
    with btn_col:
        lancer = st.button("🎤 Transcrire", type="primary", width="stretch")

    if not lancer:
        return

    # --- Transcription via le moteur ---
    with st.spinner("🎧 Transcription en cours..."):
        try:
            texte = engine.transcrire_audio(
                audio_data=audio_file.getvalue(),
                filename=audio_file.name,
                langue=st.session_state.voix_prefs["langue"],
                model=st.session_state.voix_prefs["model"],
                local_model=st.session_state.voix_prefs.get("model_local", "base"),
            )
        except TranscriptionError as e:
            st.error(f"❌ {e}")
            return
        except Exception as e:
            st.error(f"❌ Erreur inattendue lors de la transcription : {e}")
            return

    # --- Aperçu de la transcription ---
    st.session_state.transcription_preview = texte
    nb_mots = len(texte.split())
    st.success(f"✅ Transcription terminée ({nb_mots} mots) — vérifiez avant insertion")

    st.text_area(
        "📄 Aperçu de la transcription",
        value=texte,
        height=150,
        key="transcription_preview_area",
        label_visibility="collapsed",
    )

    # Le texte inséré est celui de l'aperçu (modifiable), pas la transcription brute
    def _texte_final() -> str:
        return (st.session_state.get("transcription_preview_area") or texte).strip()

    col_remplacer, col_ajouter, col_annuler = st.columns([1, 1, 0.5])
    with col_remplacer:
        if st.button("✅ Remplacer la dictée", width="stretch"):
            st.session_state.dictee_draft = _texte_final()
            st.session_state.transcription_preview = None
            st.rerun()
    with col_ajouter:
        if st.button("➕ Ajouter à la dictée", width="stretch"):
            base = dictee_actuelle.strip()
            st.session_state.dictee_draft = f"{base} {_texte_final()}".strip()
            st.session_state.transcription_preview = None
            st.rerun()
    with col_annuler:
        if st.button("✖️", help="Annuler l'aperçu", width="stretch"):
            st.session_state.transcription_preview = None
            st.rerun()


# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("### 🏥 NurseLog AI")
    st.markdown("*Documentation intelligente pour infirmiers belges*")
    st.divider()
    
    # Menu de navigation
    page = st.radio("Navigation", [
        "🎙️ Dictée Rapide",
        "📝 Rapport Manuel",
        "📋 Historique",
        "📊 Tableau de bord",
        "⚙️ Paramètres",
        "ℹ️ À propos"
    ])
    
    st.divider()
    
    # Stats (par infirmier si connecté)
    st.markdown("### 📊 Statistiques")
    stats = recuperer_stats(infirmier_id=st.session_state.infirmier_id)
    st.metric("Rapports total", stats["total"])
    st.metric("Rapports validés", stats["valides"])

    if stats["total"] > 0:
        st.success(f"✅ {stats['valides']} documentation(s) validée(s)")
    
    # Statut infirmier
    st.divider()
    if st.session_state.infirmier_id:
        st.success(f"👤 Infirmier·e #{st.session_state.infirmier_id} connecté·e")
    else:
        st.info("👤 Non connecté — voir ⚙️ Paramètres")

    # Statut reconnaissance vocale
    st.divider()
    if VOIX_STATUT["backend"] == "openai":
        st.caption("🎙️ Voix : API OpenAI ✅")
    elif VOIX_STATUT["backend"] == "local":
        st.caption("🎙️ Voix : Whisper local ✅")
    else:
        st.caption("🎙️ Voix : inactive")

# ============ PAGE: DICTÉE RAPIDE ============
if page == "🎙️ Dictée Rapide":
    st.markdown("<p class='main-header'>🎙️ Dictée Rapide</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Dictez vos soins naturellement — l'IA structure le rapport automatiquement</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📋 Informations Patient")
        
        patient_nom = st.text_input("Nom du patient", placeholder="ex: Marie Dupont")
        patient_prenom = st.text_input("Prénom du patient", placeholder="ex: Marie")
        chambre = st.text_input("Chambre/Lieu", placeholder="ex: CH 12A / Domicile")
        numero_dossier = st.text_input("N° Dossier (optionnel)", placeholder="ex: D-2025-001")
        date_naissance = st.date_input("Date de naissance", value=datetime.date(1950, 1, 1))
        
        st.markdown("### 🎤 Dictée des soins")
        st.info("💡 Parlez naturellement comme si vous racontiez ce que vous avez fait. Exemple : *'Pansement plaie sacrum réalisé, plaie propre 5x3cm, douleur 2/10, prochain pansement dans 48h'*")
        
        # Pré-remplir avec le brouillon si disponible
        dictee_initial = st.session_state.dictee_draft
        if st.session_state.infirmier_id:
            brouillon = recuperer_brouillon(st.session_state.infirmier_id)
            if brouillon and brouillon["texte"]:
                dictee_initial = brouillon["texte"]
        
        dictée = st.text_area(
            "📝 Entrez votre dictée ici :",
            height=150,
            value=dictee_initial,
            placeholder="Dictez vos observations ici...",
            help="Le texte est sauvegardé automatiquement comme brouillon"
        )
        
        # Sauvegarde automatique du brouillon (si infirmier connecté)
        if dictée and st.session_state.infirmier_id:
            try:
                sauvegarder_brouillon(
                    st.session_state.infirmier_id,
                    patient_nom, patient_prenom, dictée, ""
                )
            except Exception as e:
                st.error(f"Erreur lors de la sauvegarde du brouillon : {e}")  # Log
                # Brouillon est optionnel, ne pas bloquer
        
        # Option pour l'enregistrement vocal
        st.markdown("### 🎙️ Enregistrement vocal")
        _afficher_module_voix(dictée)
        
        st.markdown("### 🎯 Type de rapport")
        type_rapport = st.selectbox(
            "Sélectionnez le type de documentation",
            [
                "Rapport de soins standard",
                "Transmission de quart",
                "Observation ponctuelle",
                "Évaluation douleur",
                "Suivi plaie",
                "Administration médicamenteuse",
            ]
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            quart = st.selectbox("Quart", ["Matin (07h-15h)", "Après-midi (15h-23h)", "Nuit (23h-07h)"])
        with col_b:
            langue = st.selectbox("Langue du rapport", ["Français", "Néerlandais", "Mixte"])
        
        st.markdown("---")
        
        # Bouton de génération
        if st.button("🤖 Générer le rapport", type="primary", disabled=not dictée):
            with st.spinner("🔄 Analyse en cours par l'IA..."):
                patient_data = {
                    "nom": patient_nom,
                    "prenom": patient_prenom,
                    "chambre": chambre,
                    "numero_dossier": numero_dossier,
                    "date_naissance": str(date_naissance),
                    "quart": quart,
                    "langue": langue,
                    "type_rapport": type_rapport
                }
                
                rapport = engine.generer_rapport(dictée, patient_data)
                
                st.session_state.rapport = rapport
                st.session_state.validated = False
                st.session_state.rapport_origin_page = "🎙️ Dictée Rapide"
                st.session_state.dictee_draft = dictée
                
                st.success("✅ Rapport généré avec succès !")
    
    with col2:
        st.markdown("### 💡 Conseils")
        st.info("""
**Pour une dictée efficace :**
- Parlez clairement et à rythme normal
- Mentionnez les éléments importants
- Incluez les observations cliniques
- Précisez les actions **réalisées**
- Notez les alertes ou points de vigilance
        """)
        
        st.markdown("### 📖 Exemple de dictée")
        st.code("""
"Patiente Marie Dupont, 
chambre 12. Pansement plaie 
sacrum réalisé. Plaie propre, 
5x3cm, granulation en bonne 
évolution. Pas de drainage. 
Patiente tolère bien, douleur 
2/10. Prochain pansement 
dans 48h. Transmission : 
surveiller l'appétit, a mangé 
30% ce midi."
        """)

# ============ PAGE: RAPPORT MANUEL ============
elif page == "📝 Rapport Manuel":
    st.markdown("<p class='main-header'>📝 Rapport Manuel</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Créez un rapport en remplissant les champs structurés — sans parsing automatique</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Informations Patient")
        patient_nom = st.text_input("Nom du patient", key="man_nom")
        patient_prenom = st.text_input("Prénom du patient", key="man_prenom")
        chambre = st.text_input("Chambre/Lieu", key="man_chambre")
        numero_dossier = st.text_input("N° Dossier (optionnel)", key="man_dossier")
        
        st.markdown("### 🩺 Évaluation Clinique")
        st.markdown("*Laissez vide si non applicable*")
        tension = st.text_input("Tension artérielle", placeholder="ex: 120/80", key="man_ta")
        pouls = st.text_input("Pouls (bpm)", placeholder="ex: 72", key="man_pouls")
        temperature = st.text_input("Température (°C)", placeholder="ex: 37.2", key="man_temp")
        spo2 = st.text_input("SpO2 (%)", placeholder="ex: 98", key="man_spo2")
        douleur = st.slider("Échelle douleur (0-10)", 0, 10, 0, key="man_douleur")
        glycémie = st.text_input("Glycémie (g/L)", placeholder="ex: 1.1", key="man_glyc")
        etat_general = st.text_input("État général", placeholder="ex: Conscient, orienté, stable", key="man_etat")
        
    with col2:
        st.markdown("### 📝 Soins Réalisés")
        soins_texte = st.text_area(
            "Listez les soins (un par ligne)",
            height=120,
            placeholder="Pansement plaie sacrum\nAdministration paracétamol 1g\nSurveillance signes vitaux",
            key="man_soins"
        )
        
        st.markdown("### ⚠️ Alertes")
        alertes_texte = st.text_area(
            "Points de vigilance (un par ligne)",
            height=80,
            placeholder="Surveiller la douleur\nAlerter médecin si T° > 38°C",
            key="man_alertes"
        )
        
        st.markdown("### 📅 Plan de Soins")
        plan_texte = st.text_area(
            "Prochains soins / actions (un par ligne)",
            height=80,
            placeholder="Prochain pansement dans 48h\nRéévaluation douleur dans 2h",
            key="man_plan"
        )
        
        st.markdown("### 🎯 Type & Quart")
        type_rapport = st.selectbox(
            "Type de documentation",
            [
                "Rapport de soins standard",
                "Transmission de quart",
                "Observation ponctuelle",
                "Évaluation douleur",
                "Suivi plaie",
                "Administration médicamenteuse",
            ],
            key="man_type"
        )
        quart = st.selectbox("Quart", ["Matin (07h-15h)", "Après-midi (15h-23h)", "Nuit (23h-07h)"], key="man_quart")
        langue = st.selectbox("Langue du rapport", ["Français", "Néerlandais", "Mixte"], key="man_langue")
    
    st.markdown("---")
    
    if st.button("📋 Générer le rapport structuré", type="primary"):
        with st.spinner("🔄 Structuration en cours..."):
            # Construire l'évaluation directement depuis les champs
            evaluation = {
                "Signes vitaux": {},
                "Confort douleur": f"EVA: {douleur}/10" if douleur > 0 else "Aucune douleur",
                "État général": etat_general,
                "Nutrition hydratation": "",
                "Mobilité": "",
                "Pele muqueuses": "",
                "Eliminations": "",
                "État psychologique": "",
            }
            
            if tension:
                evaluation["Signes vitaux"]["Tension artérielle"] = f"{tension} mmHg"
            if pouls:
                evaluation["Signes vitaux"]["Pouls"] = f"{pouls} bpm"
            if temperature:
                evaluation["Signes vitaux"]["Température"] = f"{temperature}°C"
            if spo2:
                evaluation["Signes vitaux"]["SpO2"] = f"{spo2}%"
            if glycémie:
                evaluation["Signes vitaux"]["Glycémie"] = f"{glycémie} g/L"
            
            # Convertir les textes multi-lignes en listes
            soins_liste = [s.strip() for s in soins_texte.split("\n") if s.strip()]
            alertes_liste = [a.strip() for a in alertes_texte.split("\n") if a.strip()]
            plan_liste = [p.strip() for p in plan_texte.split("\n") if p.strip()]
            
            patient_data = {
                "nom": patient_nom,
                "prenom": patient_prenom,
                "chambre": chambre,
                "numero_dossier": numero_dossier,
                "date_naissance": "",
                "quart": quart,
                "langue": langue,
                "type_rapport": type_rapport
            }
            
            # Utiliser la méthode directe (pas de regex)
            rapport = engine.generer_rapport_structure(
                patient_data, evaluation, soins_liste, alertes_liste, plan_liste
            )
            
            st.session_state.rapport = rapport
            st.session_state.validated = False
            st.session_state.rapport_origin_page = "📝 Rapport Manuel"
            
            st.success("✅ Rapport structuré généré !")

# ============ PAGE: HISTORIQUE ============
elif page == "📋 Historique":
    st.markdown("<p class='main-header'>📋 Historique des Rapports</p>", unsafe_allow_html=True)
    
    # Filtres
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        recherche_nom = st.text_input("🔍 Rechercher par nom patient", placeholder="ex: Dupont")
    with col_f2:
        date_filtre = st.date_input("📅 Filtrer par date (optionnel)", value=None)
    with col_f3:
        st.write("")  # spacer
        btn_tous = st.button("🔄 Réinitialiser")
    
    # Charger depuis SQLite avec filtrage par infirmier
    inf_id = st.session_state.infirmier_id
    historique_db = recuperer_historique(infirmier_id=inf_id, limite=100)
    
    # Appliquer les filtres côté client
    if recherche_nom:
        recherche_lower = recherche_nom.lower()
        historique_db = [
            r for r in historique_db
            if recherche_lower in r.get("patient", {}).get("nom", "").lower()
            or recherche_lower in r.get("patient", {}).get("prenom", "").lower()
        ]
    
    if date_filtre:
        date_str = str(date_filtre)
        historique_db = [
            r for r in historique_db
            if r.get("metadata", {}).get("date", "") == date_str
        ]
    
    if not historique_db:
        st.info("📭 Aucun rapport trouvé. Commencez par créer un rapport !")
        st.caption("💡 L'export CSV et PDF sera disponible dès que vous aurez enregistré des rapports.")
    else:
        st.success(f"📊 {len(historique_db)} rapport(s) trouvé(s)")
        for i, rapport_hist in enumerate(historique_db):
            patient = rapport_hist.get("patient", {})
            metadata = rapport_hist.get("metadata", {})
            db_id = rapport_hist.get("_db_id", i + 1)
            statut = "✅ Validé" if metadata.get("valide") else "📝 Brouillon"
            with st.expander(
                f"📄 #{db_id} — {patient.get('prenom', '')} {patient.get('nom', '')}"
                f" — {metadata.get('date', 'N/A')} {metadata.get('heure', '')} — {statut}"
            ):
                # Affichage structuré
                st.markdown(f"**Patient :** {patient.get('prenom', '')} {patient.get('nom', '')} — {patient.get('chambre', '')}")
                st.markdown(f"**Type :** {metadata.get('type_rapport', 'N/A')} — **Quart :** {metadata.get('quart', 'N/A')}")
                
                if rapport_hist.get("soins"):
                    st.markdown("**Soins :**")
                    for soin in rapport_hist["soins"]:
                        st.write(f"  • {soin}")
                
                if rapport_hist.get("alertes"):
                    st.markdown("**Alertes :**")
                    for a in rapport_hist["alertes"]:
                        st.write(f"  ⚠️ {a}")
                
                if rapport_hist.get("plan"):
                    st.markdown("**Plan :**")
                    for p in rapport_hist["plan"]:
                        st.write(f"  📌 {p}")
                
                st.divider()
                with st.expander("📄 JSON complet"):
                    st.json(rapport_hist)
                
                # Export PDF de ce rapport
                if PDF_EXPORT_AVAILABLE:
                    if st.button("📄 Exporter ce rapport en PDF", key=f"btn_pdf_hist_{db_id}"):
                        pdf_bytes = generer_pdf_rapport(rapport_hist)
                        if pdf_bytes:
                            st.session_state[f"pdf_hist_{db_id}"] = pdf_bytes
                        else:
                            st.error("Échec de la génération du PDF.")
                    if st.session_state.get(f"pdf_hist_{db_id}"):
                        st.download_button(
                            label="⬇️ Télécharger le PDF",
                            data=st.session_state[f"pdf_hist_{db_id}"],
                            file_name=f"nurselog_{patient.get('nom', 'rapport')}_{metadata.get('date', 'date')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_hist_{db_id}",
                        )
                else:
                    st.caption("📥 Export PDF indisponible — installez ReportLab (`pip install reportlab`).")
        
        # Bouton pour export CSV
        st.markdown("---")
        st.subheader("📤 Export des données")
        if st.button("📥 Télécharger l'historique en CSV"):
            try:
                from database import generer_csv_historique
                csv_content = generer_csv_historique(inf_id)
                if csv_content:
                    st.download_button(
                        label="Télécharger le fichier CSV",
                        data=csv_content,
                        file_name=f"nurselog_historique_{inf_id}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Aucun rapport à exporter.")
            except Exception as e:
                st.error(f"Erreur lors de l'export CSV : {e}")
                
        # L'export PDF par rapport est disponible dans chaque fiche ci-dessus.
# ============ PAGE: TABLEAU DE BORD ============
elif page == "📊 Tableau de bord":
    st.markdown("<p class='main-header'>📊 Tableau de bord</p>", unsafe_allow_html=True)
    st.info("Statistiques et métriques de votre activité professionnelle")
    
    # Afficher les stats
    if st.session_state.infirmier_id:
        stats = recuperer_stats(infirmier_id=st.session_state.infirmier_id)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total rapports", stats["total"])
        with col2:
            st.metric("Rapports validés", stats["valides"])
        with col3:
            st.metric("Taux de validation", f"{stats['valides']/max(stats['total'], 1)*100:.1f}%")
        
        # Données historiques pour les graphiques
        historique = recuperer_historique(infirmier_id=st.session_state.infirmier_id, limite=50)
        
        if historique:
            # Créer des données pour les graphiques (rapports par jour)
            dates = {}
            for r in historique:
                date = r.get("metadata", {}).get("date", "")
                if date:
                    if date not in dates:
                        dates[date] = 0
                    dates[date] += 1
            
            # Afficher les rapports par jour
            st.subheader("Rapports par jour")
            if dates:
                import matplotlib.pyplot as plt
                import pandas as pd
                
                # Créer un DataFrame
                df = pd.DataFrame(list(dates.items()), columns=["Date", "Nombre de rapports"])
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.sort_values("Date")
                
                st.bar_chart(df.set_index("Date"))
            else:
                st.info("Aucune donnée disponible pour les graphiques.")
        else:
            st.info("Aucun rapport enregistré. Commencez à documenter !")
    else:
        st.warning("Veuillez vous connecter via les paramètres pour voir vos statistiques.")

# ============ PAGE: PARAMÈTRES ============
elif page == "⚙️ Paramètres":

    st.markdown("<p class='main-header'>⚙️ Paramètres</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👤 Profil Infirmier")
        st.info("Vos identifiants sont utilisés pour lier les rapports à votre profil.")
        
        nom_infirmier = st.text_input("Votre nom complet", placeholder="ex: Jean Dupont", key="param_nom")
        num_infirmier = st.text_input("Numéro d'identification", placeholder="ex: INF-12345", key="param_num")
        etablissement = st.text_input("Établissement", placeholder="ex: CHU Bruxelles / Infirmier libéral", key="param_etab")
        langue_par_defaut = st.selectbox("Langue par défaut", ["Français", "Néerlandais", "Bilingue"], key="param_langue")
        
        if st.button("💾 Enregistrer mon profil", type="primary"):
            if not nom_infirmier or not num_infirmier:
                st.error("⚠️ Le nom et le numéro d'identification sont obligatoires.")
            else:
                try:
                    inf_id = sauvegarder_infirmier(nom_infirmier, num_infirmier, etablissement, langue_par_defaut)
                    st.session_state.infirmier_id = inf_id
                    st.success(f"✅ Profil enregistré ! ID: {inf_id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement : {e}")
        
        # Afficher le profil actuel
        if st.session_state.infirmier_id:
            st.divider()
            st.success(f"👤 Profil actif : ID #{st.session_state.infirmier_id}")
    
    with col2:
        st.markdown("### 🔒 Données & Confidentialité")
        st.info("📍 Les données sont stockées localement (SQLite)")
        st.info("📍 Aucun envoi vers des serveurs externes")
        st.info("📍 Conçu pour une future conformité RGPD/AI Act")
        
        st.markdown("### 🎙️ Reconnaissance vocale")
        _statut = VOIX_STATUT
        if _statut["backend"] == "openai":
            st.success("✅ Backend actif : **API OpenAI**")
        elif _statut["backend"] == "local":
            st.success("✅ Backend actif : **Whisper local** (100% RGPD)")
        else:
            st.warning("⚠️ Aucun backend actif")
            if _statut["api_key"] and not _statut["openai_installe"]:
                st.caption("→ Installez le package : `pip install openai`")
            elif not _statut["api_key"]:
                st.caption("→ Définissez `OPENAI_API_KEY` ou installez `openai-whisper` (local)")

        prefs = st.session_state.voix_prefs
        col_l, col_m = st.columns(2)
        with col_l:
            nouvelle_langue = st.selectbox(
                "Langue de dictée",
                ["Auto", "Français", "Néerlandais"],
                index=["Auto", "Français", "Néerlandais"].index(prefs["langue"]),
                key="voix_langue",
                help="Indice de langue transmis à Whisper pour une meilleure précision",
            )
        with col_m:
            if _statut["backend"] == "openai":
                nouveau_model = st.selectbox(
                    "Modèle de transcription",
                    list(_statut["modeles"]),
                    index=_statut["modeles"].index(prefs["model"]) if prefs["model"] in _statut["modeles"] else 0,
                    key="voix_model",
                    help="gpt-4o-transcribe est le plus précis ; whisper-1 le plus rapide",
                )
                nouveau_model_local = prefs.get("model_local", "base")
                st.caption(f"Repli local (si API indisponible) : `{nouveau_model_local}`")
            else:
                nouveau_model = prefs["model"]
                nouveau_model_local = st.selectbox(
                    "Taille du modèle local",
                    list(_statut["modeles_locaux"]),
                    index=_statut["modeles_locaux"].index(prefs.get("model_local", "base"))
                    if prefs.get("model_local") in _statut["modeles_locaux"] else 1,
                    key="voix_model_local",
                    help=(
                        "tiny : le plus rapide (~39 Mo) — base : équilibré (~142 Mo) — "
                        "small : le plus précis (~466 Mo). "
                        "Chargé une seule fois, puis mis en cache."
                    ),
                )

        if (
            nouvelle_langue != prefs["langue"]
            or nouveau_model != prefs["model"]
            or nouveau_model_local != prefs.get("model_local", "base")
        ):
            if st.button("💾 Enregistrer les préférences vocales"):
                st.session_state.voix_prefs = {
                    "langue": nouvelle_langue,
                    "model": nouveau_model,
                    "model_local": nouveau_model_local,
                }
                st.success("✅ Préférences vocales enregistrées")

        st.markdown("### 📊 Intégrations")
        st.markdown('<span class="badge-bientot">🔧 Intégration eHealth/SumEHR — Bientôt disponible</span>', unsafe_allow_html=True)
        st.markdown('<span class="badge-bientot">🔧 Export FHIR/HL7 — Bientôt disponible</span>', unsafe_allow_html=True)
        
        st.markdown("### 🗑️ Données")
        if st.session_state.infirmier_id:
            if st.button("🗑️ Supprimer mon brouillon en cours"):
                try:
                    supprimer_brouillon(st.session_state.infirmier_id)
                    st.session_state.dictee_draft = ""
                    st.success("Brouillon supprimé.")
                except Exception as e:
                    st.error(f"Erreur : {e}")

# ============ PAGE: À PROPOS ============
elif page == "ℹ️ À propos":
    st.markdown("<p class='main-header'>ℹ️ À propos de NurseLog AI</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏥 Qu'est-ce que NurseLog AI ?")
        st.info("""
**NurseLog AI** est le premier assistant de documentation clinique 
par IA conçu spécifiquement pour les **infirmiers belges**.

L'outil transforme votre parole naturelle en rapports de soins 
structurés, complets et conformes aux standards belges.
        """)
        
        st.markdown("### 🎯 Objectif")
        st.success("""
Réduire de **70%** le temps passé en documentation 
administrative pour que les infirmiers puissent se 
concentrer sur l'essentiel : **leurs patients**.
        """)
        
        st.markdown("### ⚙️ Moteur actuel")
        st.warning("""
**Important :** Le moteur actuel est basé sur des **règles regex et mots-clés**, 
pas sur un LLM. Il fonctionne 100% localement sans dépendance externe.

La Phase 1.5 (Whisper + LLM local) est en développement.
        """)
    
    with col2:
        st.markdown("### 📊 Fonctionnalités")
        
        features = [
            ("🎙️ Dictée Rapide", "Transformation texte → rapport structuré"),
            ("📝 Rapport Manuel", "Saisie structurée directe (sans regex)"),
            ("📋 Historique", "Recherche et filtrage des rapports"),
            ("📥 Export PDF", "Génération PDF avec ReportLab"),
            ("💾 Brouillons", "Sauvegarde automatique de la dictée en cours"),
            ("🔒 Local", "Aucune donnée envoyée à l'extérieur"),
        ]
        
        for title, desc in features:
            st.markdown(f"**{title}** : {desc}")
        
        st.markdown("### 🔒 Conformité")
        st.info("""
- 📍 Stockage local (pas d'envoi externe)
- 📍 Architecture conçue pour RGPD / AI Act
- 📍 Intégration eHealth/SumEHR planifiée (Phase 3)
- 📍 Chiffrement en transit & au repos (Phase 2)
""")

# ============ AFFICHAGE DU RAPPORT GÉNÉRÉ ============
# N'afficher que si la page d'origine correspond à la page active
if st.session_state.rapport and st.session_state.rapport_origin_page == page:
    st.markdown("---")
    st.markdown("<p class='main-header'>📋 Rapport Généré</p>", unsafe_allow_html=True)
    
    rapport = st.session_state.rapport
    
    # En-tête du rapport
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**👤 Patient :** {rapport.get('patient', {}).get('nom', 'N/A')} {rapport.get('patient', {}).get('prenom', '')}")
    with col2:
        st.markdown(f"**📍 Lieu :** {rapport.get('patient', {}).get('chambre', 'N/A')}")
    with col3:
        st.markdown(f"**📅 Date :** {rapport.get('metadata', {}).get('date', 'N/A')}")
    
    st.divider()
    
    # Sections du rapport
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🩺 Évaluation Clinique")
        if 'evaluation' in rapport:
            for key, value in rapport['evaluation'].items():
                if value:
                    st.markdown(f"**{key}:** {value}")
        
        st.markdown("### 📝 Soins Réalisés")
        if rapport.get('soins'):
            for soin in rapport['soins']:
                st.success(f"✅ {soin}")
        else:
            st.info("Aucun soin documenté")
    
    with col2:
        st.markdown("### ⚠️ Alertes")
        if rapport.get('alertes'):
            for alerte in rapport['alertes']:
                st.warning(f"⚠️ {alerte}")
        else:
            st.success("✅ Aucune alerte")
        
        st.markdown("### 📅 Plan de Soins")
        if rapport.get('plan'):
            for action in rapport['plan']:
                st.info(f"📌 {action}")
        else:
            st.info("Aucun plan défini")
    
    st.divider()
    
    # Codes NAA
    if rapport.get('codes_naa'):
        st.markdown("### 💰 Codes NAA (Facturation)")
        for code in rapport['codes_naa']:
            code_text = f"Code: {code.get('code', 'N/A')} | {code.get('nom', '')} | Source: {code.get('source', 'N/A')}"
            st.code(code_text)
    
    # Médicaments
    if rapport.get('medicaments'):
        st.markdown("### 💊 Médicaments")
        for med in rapport['medicaments']:
            st.write(f"  • {med.get('nom', 'N/A')} — {med.get('dose', '')} {med.get('unite', '')}")
    
    st.divider()
    
    # ============ VALIDATION & SIGNATURE ============
    st.markdown("### ✍️ Validation & Signature")
    
    if not st.session_state.validated:
        # Warnings de validation AVANT signature
        est_valide, warnings = engine.valider_rapport(rapport)
        if warnings:
            st.markdown("#### 🔍 Vérification avant signature")
            for w in warnings:
                st.warning(w)
            st.info("⚠️ Ces éléments sont manquants. Vous pouvez quand même signer, mais le rapport sera incomplet.")
        
        st.markdown("---")
        st.info("🔍 Vérifiez attentivement le rapport avant validation. **L'IA ne remplace pas votre jugement clinique.**")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("❌ Modifier", type="secondary"):
                # Le brouillon de dictée est déjà conservé dans st.session_state.dictee_draft
                st.session_state.rapport = None
                st.session_state.rapport_origin_page = None
                st.rerun()
        
        with col2:
            confirm_signature = st.checkbox("✅ Je certifie avoir vérifié ce rapport et sa justesse clinique")
            if confirm_signature and st.button("🖊️ Valider & Signer", type="primary"):
                # Vérification finale
                erreurs_bloquantes = []
                if not rapport.get('patient', {}).get('nom'):
                    erreurs_bloquantes.append("Nom du patient manquant")
                
                if erreurs_bloquantes:
                    st.error("❌ Impossible de signer — corrigez les éléments suivants :")
                    for erreur in erreurs_bloquantes:
                        st.write(f"  • {erreur}")
                else:
                    st.session_state.validated = True
                    rapport['metadata']['valide'] = True
                    rapport['metadata']['signature_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Sauvegarder en base SQLite
                    try:
                        inf_id = st.session_state.infirmier_id
                        if inf_id is None:
                            st.warning("⚠️ Aucun profil infirmier connecté. Le rapport sera enregistré sans lien.")
                            inf_id = 1  # fallback
                        sauvegarder_rapport(inf_id, rapport)
                        
                        # Supprimer le brouillon après validation
                        if st.session_state.infirmier_id:
                            supprimer_brouillon(st.session_state.infirmier_id)
                        st.session_state.dictee_draft = ""
                        
                        st.success("✅ Rapport validé et signé électroniquement !")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la sauvegarde : {e}")
                        st.warning("Le rapport n'a PAS été enregistré. Veuillez réessayer.")
    
    else:
        st.success("✅ **Rapport validé et signé**")
        st.markdown(f"📅 Signé le : {rapport.get('metadata', {}).get('signature_date', 'N/A')}")
        
        # Options post-validation
        col1, col2 = st.columns(2)
        
        with col1:
            if PDF_EXPORT_AVAILABLE:
                if st.button("📥 Exporter en PDF", type="primary"):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file_path = tmp_file.name
                        
                        success = exporter_pdf_rapport(rapport, tmp_file_path)
                        
                        if success:
                            with open(tmp_file_path, "rb") as f:
                                st.download_button(
                                    label="⬇️ Télécharger le PDF",
                                    data=f.read(),
                                    file_name=f"rapport_{rapport.get('metadata', {}).get('date', 'date')}.pdf",
                                    mime="application/pdf"
                                )
                            os.unlink(tmp_file_path)
                            st.success("✅ PDF généré !")
                        else:
                            st.error("Erreur lors de la génération du PDF")
                    except Exception as e:
                        st.error(f"Erreur lors de l'export PDF : {e}")
            else:
                st.markdown('<span class="badge-bientot">📥 Export PDF — Installez ReportLab</span>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<span class="badge-bientot">📤 Export vers SIH — Bientôt disponible</span>', unsafe_allow_html=True)
        
        st.divider()
        
        # Nouveau rapport
        if st.button("🆕 Nouveau Rapport", type="primary"):
            st.session_state.rapport = None
            st.session_state.validated = False
            st.session_state.rapport_origin_page = None
            st.session_state.dictee_draft = ""
            st.rerun()

# ============ FOOTER ============
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.8rem;'>
    NurseLog AI v0.2 (Prototype) | Belgium Edition | © 2025
    <br>Conformité RGPD • AI Act • eHealth Belgique
    <br>Moteur : regex/mots-clés (LLM en Phase 1.5)
</div>
""", unsafe_allow_html=True)
