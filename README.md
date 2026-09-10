# 🩺 NurseLog AI

> **Assistant IA pour la documentation clinique infirmière en Belgique**  
> *Transcription vocale → Documentation structurée conforme aux standards belges*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()
[![Tests: 32/32](https://img.shields.io/badge/tests-32%2F32%20passed-brightgreen.svg)]()

---

## 🎯 Qu'est-ce que NurseLog AI ?

NurseLog AI est une application SaaS qui aide les infirmier·e·s belges à gagner du temps sur la documentation clinique grâce à l'IA.

### 4 modules principaux

| Module | Fonction | Bénéfice |
|--------|----------|----------|
| 🎙 **DocuVoice** | Transcription vocale → notes de soin structurées | -70% temps de documentation |
| 🔄 **TransmiShift** | Transmissions de garde intelligentes (SBAr) | Transmissions claires, complètes |
| 📋 **FormuCare** | Génération formulaires NAA & plans de soins | Conformité automatique |
| 📊 **AnalysInsight** | Tableaux de bord indicateurs qualité | Suivi qualité & reporting |

### Public cible
- Infirmier·e·s libéraux (Bruxelles & Wallonie)
- Infirmier·e·s à domicile (soins palliatifs, post-op, chroniques)
- Infirmier·e·s hospitaliers
- Ambulanciers / SMUR

---

## 🚀 Installation

### Prérequis
- **Python 3.10+** ([pyenv](https://github.com/pyenv/pyenv) recommandé)
- **Git**

### Étape 1 — Cloner le projet
```bash
git clone <repo-url>
cd NurseLog-AI
```

### Étape 2 — Environnement virtuel
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### Étape 3 — Installer les dépendances
```bash
pip install -r requirements.txt
```

### Étape 4 — Configuration
```bash
cp .env.example .env
# Éditer .env avec vos clés API
```

### Étape 5 — Lancer l'application
```bash
streamlit run src/app.py
```

L'application sera disponible à `http://localhost:8501`.

---

## 📁 Structure du projet

```
NurseLog-AI/
├── src/                       # Code source principal
│   ├── __init__.py            # Package init
│   ├── app.py                 # Interface Streamlit (UI)
│   ├── nurselog_engine.py     # Moteur IA (extraction, NAA, alertes, SBAr)
│   ├── templates.py           # Templates belges, codes NAA, vocabulaire médical
│   └── database.py            # Persistance SQLite (rapports, profils)
├── tests/                     # Tests unitaires
│   ├── test_engine.py         # Tests moteur + templates
│   └── test_database.py       # Tests SQLite
├── docs/                      # Documentation technique
│   ├── architecture.md
│   ├── api.md
│   └── deployment.md
├── assets/                    # Ressources (images, logos)
├── .env.example               # Modèle de configuration
├── .gitignore
├── requirements.txt           # Dépendances Python
└── README.md
```

---

## 🔧 Architecture technique

```
┌─────────────────────────────────────────────┐
│  Interface Streamlit (app.py)               │
│  ├── Formulaires d'entrée                   │
│  ├── Affichage résultats                    │
│  └── Validation infirmière                  │
├─────────────────────────────────────────────┤
│  Moteur IA (nurselog_engine.py)             │
│  ├── Extraction texte → données structurées │
│  ├── Mapping codes NAA                      │
│  ├── Détection alertes/signes vitaux        │
│  └── Génération SBAr                        │
├─────────────────────────────────────────────┤
│  Templates (templates.py)                   │
│  ├── Codes NAA belges                       │
│  ├── Vocabulaire médical FR/NL              │
│  ├── Échelles d'évaluation (Bristol, etc.)  │
│  └── Plans de soins standards               │
└─────────────────────────────────────────────┘
```

### Stack technique (Phase 1 - Prototype)
- **Python 3.10+**
- **Streamlit** — Interface web
- **SQLite** — Stockage local (persistant)
- **Regex + NLP** — Extraction de données structurées (moteur actuel)
- **pytest** — 32 tests unitaires

### Prochaines étapes (Phase 1.5)
- **Whisper** (OpenAI) — Transcription vocale FR/NL
- **Llama 3** — Analyse NLP & génération de texte
- **Export PDF** — Rapport imprimable

### Stack technique (Phase 2 - Production)
- **FastAPI** — API REST
- **Supabase** — Base de données cloud
- **PostgreSQL** — Stockage structuré
- **Docker** — Conteneurisation
- **AWS/GCP** — Hébergement

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 📅 Roadmap

| Phase | Période | Objectif |
|-------|---------|----------|
| **Phase 0** | Maintenant | ✅ Prototype fonctionnel |
| **Phase 1** | Mois 1-2 | MVP : DocuVoice + TransmiShift |
| **Phase 2** | Mois 3-4 | FormuCare + authentification utilisateurs |
| **Phase 3** | Mois 5-6 | AnalysInsight + intégrations API |
| **Phase 4** | Mois 7-9 | Lancement commercial + conformité RGPD/HDC |

---

## 💰 Financement (Budget €0 → Revenus)

- **Starter Pack** : 7 000€ (subvention Région Bruxelles-Wallonie)
- **Bons plans numériques** : 4 500€ (Wallonie)
- **Incubation** : Space @ulb / UCLouvain Entrepreneurship
- **Modèle SaaS** : 0€ → 299€/mois selon plan

---

## 📄 Licence

MIT — Voir [LICENSE](LICENSE)

---

## 👩‍⚕️ À propos

Conçu par et pour des infirmier·e·s belges. Conforme aux standards de la **Fédération Royale Belge des Infirmiers et Infirmières (FRBII)**.

🇧🇪 Made in Belgium for Belgian nurses
