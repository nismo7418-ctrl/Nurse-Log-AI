# API Reference — NurseLog AI

## NurseLogEngine

### `generer_rapport(dictee: str, patient_data: dict) -> dict`

Génère un rapport structuré complet à partir d'une dictée textuelle libre.

**Paramètres** :
- `dictee` (str) : Texte brut dicté par l'infirmier(e)
- `patient_data` (dict) : Données du patient (nom, prénom, chambre, etc.)

**Retourne** :
```python
{
    "patient": { "nom": "Dupont", "prenom": "Jean", ... },
    "metadata": { "date": "2025-06-15", "heure": "14:30", ... },
    "evaluation": {
        "Signes vitaux": { "Tension artérielle": "140/90 mmHg", ... },
        "Confort douleur": "EVA: 4/10",
        ...
    },
    "soins": ["Pansement réalisé", ...],
    "alertes": ["⚠️ Hypertension", ...],
    "plan": ["Prochain pansement dans 48h", ...],
    "codes_naa": [{"code": "01.011", "nom": "Pansement simple", ...}],
    "medicaments": [{"nom": "Paracétamol", "dose": "1", "unite": "g"}, ...],
    "transmissions": [{"format": "SBAr", "S_Situation": "...", ...}]
}
```

**Exemple** :
```python
engine = NurseLogEngine()
rapport = engine.generer_rapport(
    "Tension 140/90, pouls 88, pansement plaie réalisé, douleur 4/10",
    {"nom": "Dupont", "prenom": "Jean", "chambre": "4A-12"}
)
```

---

### `exporter_json(rapport: dict) -> str`

Exporte un rapport en JSON indenté.

---

### `exporter_texte_lisible(rapport: dict) -> str`

Exporte un rapport en format texte lisible (pour impression ou copie).

---

### `valider_rapport(rapport: dict) -> tuple[bool, list[str]]`

Valide la complétude du rapport et retourne les warnings.

---

## Database (SQLite)

### `initialiser_base()`

Crée les tables `infirmiers` et `rapports` si elles n'existent pas.

---

### `sauvegarder_rapport(infirmier_id: int, rapport: dict) -> int`

Sauvegarde un rapport dans la base et retourne son ID.

---

### `recuperer_historique(infirmier_id: int | None = None, limite: int = 50) -> list[dict]`

Récupère l'historique des rapports (ordonnés par date décroissante).

---

### `recuperer_stats(infirmier_id: int | None = None) -> dict`

Retourne `{"total": int, "valides": int}`.

---

## Templates

### `RAPPORT_TEMPLATE`

Dict vide servant de blueprint pour chaque nouveau rapport.

### `CODES_NAA_RECONNAISSANCE`

Mapping catégorie → liste de codes NAA belges (pansement, injection, perfusion, surveillance, éducation, douleur, soins domicile).

### `VOCABULAIRE`

Glossaire médical bilingue FR/NL (signes vitaux, soins courants, alertes, états généraux).

### `ECHELLES_EVALUATION`

EVA, EN, Morse (chute), Braden (escarre), classification plaie.

### `STRUCTURE_SBAr`

Format de transmission Situation / Contexte / Appréciation / Recommandation.