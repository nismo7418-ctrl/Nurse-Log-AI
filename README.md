# 🏥 NurseLog AI

> **Assistant de documentation infirmière par IA — Belgium Edition**
> Transformez votre dictée naturelle en rapports de soins structurés, conformes aux standards belges (KCE, eHealth, NAA).

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-47%20passing-green)]()
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
| 🎤 **Reconnaissance vocale** | Transcription audio via API Whisper (optionnel) | 🔄 |
| 📤 **Export SIH/FHIR** | Intégration eHealth Belgique | 🔜 Phase 3 |
| 🤖 **LLM local** | Whisper + Llama 3 pour extraction avancée | 🔜 Phase 1.5 |

---

## 🚀 Démarrage rapide

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-org/Nurse-Log-AI.git
cd Nurse-Log-AI

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. (Optionnel) Configurer la reconnaissance vocale
#    Définissez OPENAI_API_KEY dans votre environnement
export OPENAI_API_KEY="sk-..."

# 4. Lancer l'application
streamlit run src/app.py
```

L'application est accessible sur `http://localhost:8501`.

---

## 🏗️ Architecture

```
Nurse-Log-AI/
├── src/
│   ├── app.py              # Interface Streamlit (UI + logique métier)
│   ├── nurselog_engine.py  # Moteur d'extraction (regex + mots-clés)
│   ├── database.py         # Couche SQLite (rapports, profils, brouillons)
│   └── templates.py        # Templates belges (KCE, NAA, SBAr)
├── tests/
│   ├── test_engine.py      # Tests du moteur (35 tests)
│   └── test_database.py    # Tests de la couche DB (13 tests)
├── .streamlit/
│   └── config.toml         # Configuration Streamlit + thème
├── pyproject.toml          # Packaging + tooling (ruff, pytest)
├── requirements.txt        # Dépendances
├── .env.example            # Template de configuration
└── README.md
```

### Moteur d'extraction

Le moteur actuel est basé sur **regex et mots-clés** (pas un LLM) :
- Extraction des signes vitaux (TA, FC, T°, SpO2, EVA, glycémie, FR)
- Détection des soins réalisés (pansement, injection, perfusion, etc.)
- Identification des alertes (chute, fièvre, hémorragie, etc.)
- Mapping automatique des codes NAA belges
- Génération de transmission SBAr

> ⚠️ **Note** : Ce n'est PAS un LLM. La Phase 1.5 intégrera Whisper (transcription) + LLM local (extraction sémantique avancée).

---

## 🧪 Tests

```bash
# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=src --cov-report=term-missing

# Un seul fichier
pytest tests/test_engine.py -v
```

**Statut actuel : 47 passed, 1 skipped (ReportLab optionnel)**

---

## 🔒 Confidentialité & RGPD

- ✅ **100% local** — Aucune donnée ne quitte la machine
- ✅ **SQLite** — Base de données locale, pas de serveur
- ✅ **Minimisation** — Seules les données cliniques nécessaires sont stockées
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
| **1.5** | Whisper + LLM local, multi-langue FR/NL | 🔄 |
| **2.0** | Authentification, chiffrement, multi-poste | 🔜 |
| **3.0** | Intégration eHealth/SumEHR, FHIR/HL7 | 🔜 |

---

## 📄 License

MIT — voir [LICENSE](LICENSE)

---

*NurseLog AI v0.2 — Prototype MVP | Belgium Edition | © 2025*
