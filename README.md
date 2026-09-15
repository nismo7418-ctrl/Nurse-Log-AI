# 🏥 NurseLog AI

> **Assistant de documentation infirmière par IA — Belgium Edition**
> Transformez votre dictée naturelle en rapports de soins structurés, conformes aux standards belges (KCE, eHealth, NAA).

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-148%20passing-green)]()
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-orange)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## ✨ Fonctionnalités

| Fonctionnalité | Description | Statut |
|---|---|---|
| 🎙️ **Dictée Rapide** | Texte libre → rapport structuré (regex + mots-clés) | ✅ |
| 📝 **Rapport Manuel** | Saisie structurée directe, sans parsing regex | ✅ |
| 📋 **Historique** | Recherche par nom, filtre par date, isolation par infirmier | ✅ |
| 📥 **Export PDF** | Génération PDF professionnelle (ReportLab) | ✅ |
| 💾 **Brouillons** | Sauvegarde automatique de la dictée en cours (SQLite) | ✅ |
| 🎤 **Reconnaissance vocale** | Transcription audio (API OpenAI **ou** Whisper local 100% RGPD), indice de langue FR/NL, vocabulaire médical, aperçu avant insertion | ✅ |
| 🎧 **Widget audio temps réel** | Enregistrement navigateur → relay HTTP → transcription, auto-stop 5 min, mode accumulation, pré-écoute | ✅ |
| 📊 **Score de complétude** | Évaluation automatique de la qualité du rapport (signes vitaux, plan, alertes) | ✅ |
| 📤 **Export SIH/FHIR** | Intégration eHealth Belgique | 🔜 Phase 3 |
| 🤖 **LLM local** | Llama 3 pour extraction sémantique avancée | 🔜 Phase 1.5 (à venir) |
| 📊 **Tableau de bord** | Statistiques et métriques détaillées par infirmier | ✅ |
| 📥 **Export CSV** | Export complet des rapports en format CSV | ✅ |
| 📱 **Adaptation mobile** | Interface responsive pour tablette/mobile | ✅ |
| 🔒 **Sécurité renforcée** | Données chiffrées et conformité RGPD | ✅ |

---

## 🚀 Démarrage rapide

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-org/Nurse-Log-AI.git
cd Nurse-Log-AI

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. (Optionnel) Configurer la reconnaissance vocale
#    Option A — API OpenAI (les fichiers audio sont envoyés à OpenAI) :
export OPENAI_API_KEY="sk-..."
#    Option B — Whisper local 100% RGPD (aucune clé, aucune donnée envoyée) :
pip install openai-whisper
#    + ffmpeg (requis par Whisper pour décoder l'audio) :
#      Windows : winget install Gyan.FFmpeg   (ou choco install ffmpeg)
#      macOS   : brew install ffmpeg
#      Linux   : sudo apt install ffmpeg

# 4. Lancer l'application
streamlit run app.py
```

L'application est accessible sur `http://localhost:8501`.

---

## 🏗️ Architecture

### Structure du projet

```
NurseLog AI/
├── app.py                  # Interface utilisateur Streamlit (UI + logique métier)
├── src/                    # Code source principal
│   ├── __init__.py
│   ├── nurselog_engine.py  # Moteur d'extraction (regex + mots-clés), scoring, SBAr
│   ├── database.py         # Couche SQLite (rapports, profils, brouillons, PDF)
│   ├── templates.py        # Templates belges (KCE, NAA, SBAr, vocabulaire médical)
│   ├── audio_relay.py      # Relay HTTP pour POST audio navigateur → Python
│   ├── streaming_components.py  # Widget audio JS (iframe, auto-stop, accumulation)
│   └── logging_config.py   # Logging structuré + audit trail (Phase 3)
├── tests/                  # Tests unitaires et intégration
│   ├── conftest.py         # Fixtures partagées
│   ├── test_engine.py      # Tests du moteur (88 tests)
│   ├── test_database.py    # Tests de la couche DB
│   ├── test_nl_support.py  # Tests du support néerlandais
│   ├── test_phase2.py      # Tests Phase 2 (scoring, cross-ref, SBAr, NL)
│   └── test_audio_relay.py # Tests intégration relay audio (27 tests)
├── assets/                 # Ressources (logos, images)
├── docs/                   # Documentation technique
├── .streamlit/
│   └── config.toml         # Configuration Streamlit + thème
├── .github/
│   └── workflows/
│       └── ci.yml          # Pipeline CI (pytest sur push/PR)
├── Makefile                # Tâches courantes (test, lint, run, clean)
├── pyproject.toml          # Packaging + tooling (ruff, pytest)
├── requirements.txt        # Dépendances
├── .env.example            # Template de configuration
├── Dockerfile              # Build multi-stage
└── README.md
```

### Technologies utilisées

- **Python 3.10+** : Langage principal
- **Streamlit** : Interface utilisateur interactive
- **SQLite** : Stockage local des données
- **ReportLab** : Génération PDF professionnelle
- **OpenAI Whisper** : Reconnaissance vocale (API, ou local 100% RGPD via `openai-whisper` + `ffmpeg`)
- **Pandas** : Export CSV et analyse de données
- **Ruff** : Linting et formatting
- **pytest** : Tests unitaires et intégration

### Principes de conception

1. **Conformité RGPD** : Aucune donnée envoyée à l'extérieur
2. **Minimalisation des données** : Seulement les données nécessaires sont stockées
3. **Sécurité des données** : Données sensibles chiffrées
4. **Local-first** : Application fonctionne sans connexion
5. **Responsive design** : Adaptation mobile/tablette
6. **Tests unitaires** : 148 tests couvrant la logique métier
7. **Documentation complète** : Pour chaque composant
8. **CI/CD** : Pipeline GitHub Actions sur chaque push/PR

---

## 🧪 Tests

```bash
# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=src --cov-report=term-missing

# Un seul fichier
pytest tests/test_engine.py -v

# Via Makefile
make test
```

**Statut actuel : 148 passed, 0 failed**

### Répartition des tests

| Fichier | Tests | Couverture |
|---|---|---|
| `test_engine.py` | 88 | Extraction, regex, scoring, SBAr, NL |
| `test_phase2.py` | 27 | Scoring, cross-ref, voie médicamenteuse, NL |
| `test_audio_relay.py` | 27 | Relay HTTP, POST, polling, timeout |
| `test_database.py` | 4 | CRUD, brouillons, profils |
| `test_nl_support.py` | 2 | Support néerlandais |

---

## 🔒 Confidentialité & RGPD

- ✅ **100% local** — Aucune donnée ne quitte la machine
- ✅ **SQLite** — Base de données locale, pas de serveur
- ✅ **Minimisation** — Seules les données cliniques nécessaires sont stockées
- ✅ **Audit trail** — Logging structuré des actions infirmières (Phase 3)
- 🔜 **Chiffrement** — Phase 2 (chiffrement au repos)
- 🔜 **eHealth** — Intégration SumEHR (Phase 3)

---

## 📋 Standards belges intégrés

- **KCE** — Recommandations de documentation infirmière
- **eHealth** — Format de données de santé
- **NAA** — Codes de facturation infirmiers belges
- **SBAr** — Structured Briefing for Assessment and Recommendation
- **EVA** — Échelle de cotation de la douleur (0-10)

---

## 🗺️ Feuille de route

| Phase | Contenu | Statut |
|---|---|---|
| **1.0** | MVP : dictée → rapport structuré, SQLite, PDF | ✅ |
| **1.5** | Whisper local, multi-langue FR/NL, widget audio temps réel | ✅ |
| **2.0** | Scoring complétude, cross-ref, NL complet, tests renforcés | ✅ |
| **3.0** | Production : CI, logging, E2E, Makefile, Docker | 🔄 En cours |
| **4.0** | Intégration eHealth/SumEHR, FHIR/HL7, LLM local | 🔜 |

---

## 📄 License

MIT — voir [LICENSE](LICENSE)

---

*NurseLog AI v0.3 — Production Readiness | Belgium Edition | © 2025*