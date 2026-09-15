# Dictée vocale — Architecture

## Principe

Capture audio directement dans le navigateur (Web Audio API / MediaRecorder),
envoi au serveur local via HTTP POST, transcription par Whisper (local ou API OpenAI).

**Local-first / RGPD** : l'audio ne quitte jamais la machine (sauf choix explicite de l'API OpenAI).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `src/audio_relay.py` | Serveur HTTP local (stdlib, thread-safe, singleton) — reçoit le blob audio |
| `src/streaming_components.py` | Composant Streamlit : widget JS + boutons + transcription |
| `app.py` | Appelle `afficher_module_micro()` dans la section "Enregistrement vocal" |

## Flux

```
┌─────────────────────────────────────────────────────────────────┐
│  Navigateur (iframe Streamlit)                                   │
│                                                                 │
│  1. getUserMedia({audio}) → MediaRecorder.start()               │
│  2. MediaRecorder.stop() → Blob                                 │
│  3. fetch(RELAY_URL + "/audio", {method: "POST", body: blob})   │
└────────────────────────────────┬────────────────────────────────┘
                                 │  HTTP POST (127.0.0.1:port_aléatoire)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  audio_relay.py (thread daemon, stdlib http.server)             │
│                                                                 │
│  - Écrit le blob dans un fichier temporaire                     │
│  - Expose relay.get_latest_recording() → {path, taille, mime}   │
└────────────────────────────────┬────────────────────────────────┘
                                 │  (appel Python, même processus)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  streaming_components.py                                        │
│                                                                 │
│  - Lit le fichier temporaire                                    │
│  - Appelle NurseLogEngine.transcrire_audio()                    │
│  - Affiche le transcript + boutons "Ajouter" / "Remplacer"      │
└─────────────────────────────────────────────────────────────────┘
```

## Démarrage

Aucun serveur à lancer séparément. Le relay démarre automatiquement (thread daemon)
au premier appel de `get_audio_relay()` dans le processus Streamlit.

```bash
streamlit run app.py
```

## Dépendances

- **Aucune dépendance supplémentaire** pour le relay (stdlib Python uniquement)
- Transcription : `openai` (API) **ou** `openai-whisper` + `ffmpeg` (local)

## Sécurité

- Relay borné sur `127.0.0.1` → inaccessible depuis le réseau
- Port aléatoire (système) → pas de conflit
- Fichiers temporaires supprimés après lecture
- CORS restreint (headers présents mais le relay n'est accessible qu'en local)
