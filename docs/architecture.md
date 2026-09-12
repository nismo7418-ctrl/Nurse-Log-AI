# Architecture NurseLog AI

## Vue d'ensemble

NurseLog AI suit une architecture en 3 couches :

```
┌──────────────────────────────────────────────────┐
│  COUCHE PRÉSENTATION (UI)                         │
│  ┌────────────────────────────────────────────┐  │
│  │  Streamlit (app.py)                        │  │
│  │  - Formulaires d'entrée                    │  │
│  │  - Affichage résultats                     │  │
│  │  - Navigation multi-modules                │  │
│  │  - Validation infirmière                   │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  COUCHE LOGIQUE (Business)                        │
│  ┌────────────────────────────────────────────┐  │
│  │  NurseLog Engine (nurselog_engine.py)      │  │
│  │  - Extraction NLP                          │  │
│  │  - Mapping NAA                             │  │
│  │  - Détection alertes                       │  │
│  │  - Génération SBAr                         │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │  Templates (templates.py)                  │  │
│  │  - Codes NAA belges                        │  │
│  │  - Vocabulaire médical FR/NL               │  │
│  │  - Échelles d'évaluation                   │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  COUCHE DONNÉES (Stockage)                        │
│  ┌────────────────────────────────────────────┐  │
│  │  SQLite (dev) → PostgreSQL (prod)          │  │
│  │  - Patients                                │  │
│  │  - Notes de soin                           │  │
│  │  - Audits                                  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Module par module

### 1. `app.py` — Interface utilisateur

**Rôle** : Point d'entrée Streamlit

**Responsabilités** :
- Navigation entre les 4 modules (DocuVoice, TransmiShift, FormuCare, AnalysInsight)
- Formulaires d'entrée de données
- Affichage des résultats du moteur IA
- Bouton de validation infirmière
- Export PDF (phase 2)

**Dépendances** : `streamlit`, `nurselog_engine`, `templates`

### 2. `nurselog_engine.py` — Moteur IA

**Rôle** : Intelligence de l'application

**Fonctions principales** :
- `extract_vital_signs(text)` → Dict[signe_vital, valeur]
- `map_naa_codes(text)` → List[code_NAA]
- `detect_alerts(vital_signs)` → List[Alerte]
- `generate_sbar(data)` → str (texte SBAr structuré)
- `generate_care_notes(text)` → str (notes structurées)

**Algorithmes** :
- Extraction par regex + NLP (phase 1)
- Whisper (API OpenAI ou local 100% RGPD) pour transcription vocale (phase 1)
  - Le backend local (`openai-whisper`) requiert `ffmpeg` dans le PATH
    (ou détecté automatiquement : winget, scoop, Homebrew —
    voir `NurseLogEngine._chercher_ffmpeg()` / `_assurer_ffmpeg()`)
- Llama 3 pour génération de texte (phase 1)
- Fine-tuning modèles médicaux (phase 3)

### 3. `templates.py` — Données de référence

**Rôle** : Base de connaissance belge

**Contenu** :
- **Codes NAA** : Nomenclature des Actes Infirmiers (Belgique)
- **Vocabulaire médical** : FR/NL bilingue
- **Échelles d'évaluation** : Bristol, Braden, Douleur (EVA), etc.
- **Plans de soins** : Templates standards belges
- **Plages normales** : Signes vitaux par tranche d'âge

### 4. `database.py` — Persistance SQLite

**Rôle** : Stockage local des rapports et profils

**Tables** :
- `infirmiers` — Profils utilisateurs (nom, numéro, établissement)
- `rapports` — Rapports de soins (données JSON, validation, signature)

**Fonctions** :
- `initialiser_base()` — Création des tables au premier import
- `sauvegarder_rapport()` — Insert + index sur date et infirmier
- `recuperer_historique()` — Lecture paginée (50 par défaut)
- `recuperer_stats()` — Compteurs total / valides

## Flux de données typique

```
1. Infirmière dicte ou saisit → "Patient Dupont, PA 140/90, FC 88,
   pansement plaie, douleur 4/10"

2. app.py reçoit le texte
   ↓
3. nurselog_engine.extract_vital_signs() → {"PA": "140/90", "FC": 88}
   ↓
4. nurselog_engine.detect_alerts() → ["PA élevée: 140/90"]
   ↓
5. nurselog_engine.map_naa_codes() → ["NAA-220: Pansement"]
   ↓
6. nurselog_engine.generate_care_notes() → Note structurée
   ↓
7. app.py affiche le résultat avec validation infirmière
```

## Sécurité & Conformité

### Phase 1 (Prototype — actuel)
- Stockage local SQLite (`src/nurselog.db`)
- Aucun envoi vers des serveurs externes
- Validation infirmière obligatoire avant signature
- Pas de PII stockée hors session

### Phase 2 (Pré-production)
- Chiffrement AES-256 au repos
- TLS 1.3 en transit
- Hébergement UE (Frankfurt/Amsterdam)
- Audit RGPD

### Phase 3 (Production)
- Certification HDC (Haute Autorité Santé Belgique)
- Certification ISO 27001
- Hébergement HDS (Health Data Hosting)
- Logs d'audit complets

## Scalabilité

### Phase 1-2 (Monolithe)
- Single-instance Streamlit
- SQLite local

### Phase 3 (Microservices)
```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  API     │    │ Workers   │    │ Queue    │
│  Gateway │───→│ (Celery)  │───→│ (Redis)  │
└──────────┘    └──────────┘    └──────────┘
      │               │                │
      v               v                v
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Auth    │    │ DB       │    │ Storage  │
│  Service │    │ (PGSQL)  │    │ (S3)     │
└──────────┘    └──────────┘    └──────────┘
```

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `APP_LANG` | Langue par défaut | `fr` |
| `DEBUG` | Mode debug | `false` |
| `LOG_LEVEL` | Niveau de logging | `INFO` |
| `OPENAI_API_KEY` | Clé API OpenAI | - |
| `DATABASE_URL` | URL base de données | `sqlite:///nurselog.db` |
