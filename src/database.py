"""
NurseLog AI — Couche de persistance SQLite
==========================================
Stockage local des rapports de soins et des profils infirmiers.
Conforme au principe de minimisation des données (RGPD).
"""

import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "nurselog.db"


def _get_connection():
    """Retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialiser_base():
    """Crée les tables si elles n'existent pas."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS infirmiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            numero_identification TEXT UNIQUE,
            etablissement TEXT,
            langue_preferée TEXT DEFAULT 'Français',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rapports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            infirmier_id INTEGER,
            patient_nom TEXT,
            patient_prenom TEXT,
            chambre TEXT,
            date_rapport TEXT,
            heure_rapport TEXT,
            quart TEXT,
            type_rapport TEXT,
            donnees_json TEXT NOT NULL,
            valide INTEGER DEFAULT 0,
            signature_date TEXT,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (infirmier_id) REFERENCES infirmiers(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rapports_infirmier
        ON rapports(infirmier_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rapports_date
        ON rapports(date_rapport)
    """)

    conn.commit()
    conn.close()


def sauvegarder_rapport(infirmier_id: int, rapport: dict) -> int:
    """Sauvegarde un rapport dans la base et retourne son ID."""
    conn = _get_connection()
    cursor = conn.cursor()

    donnees_json = json.dumps(rapport, ensure_ascii=False)
    metadata = rapport.get("metadata", {})

    cursor.execute("""
        INSERT INTO rapports (
            infirmier_id, patient_nom, patient_prenom, chambre,
            date_rapport, heure_rapport, quart, type_rapport,
            donnees_json, valide, signature_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        infirmier_id,
        rapport.get("patient", {}).get("nom", ""),
        rapport.get("patient", {}).get("prenom", ""),
        rapport.get("patient", {}).get("chambre", ""),
        metadata.get("date", ""),
        metadata.get("heure", ""),
        metadata.get("quart", ""),
        metadata.get("type_rapport", ""),
        donnees_json,
        1 if metadata.get("valide") else 0,
        metadata.get("signature_date", ""),
    ))

    rapport_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rapport_id


def recuperer_historique(infirmier_id: int | None = None, limite: int = 50) -> list[dict]:
    """
    Récupère l'historique des rapports.
    Si infirmier_id est None, retourne tous les rapports.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    if infirmier_id:
        cursor.execute("""
            SELECT * FROM rapports
            WHERE infirmier_id = ?
            ORDER BY date_creation DESC
            LIMIT ?
        """, (infirmier_id, limite))
    else:
        cursor.execute("""
            SELECT * FROM rapports
            ORDER BY date_creation DESC
            LIMIT ?
        """, (limite,))

    rapports = []
    for row in cursor.fetchall():
        rapport_data = json.loads(row["donnees_json"])
        rapport_data["_db_id"] = row["id"]
        rapport_data["_date_creation"] = row["date_creation"]
        rapports.append(rapport_data)

    conn.close()
    return rapports


def sauvegarder_infirmier(nom: str, numero: str, etablissement: str, langue: str) -> int:
    """Sauvegarde ou met à jour un profil infirmier."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Vérifier si l'infirmier existe déjà
    cursor.execute("SELECT id FROM infirmiers WHERE numero_identification = ?", (numero,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE infirmiers SET nom = ?, etablissement = ?, langue_preferée = ?
            WHERE numero_identification = ?
        """, (nom, etablissement, langue, numero))
        infirmier_id = existing["id"]
    else:
        cursor.execute("""
            INSERT INTO infirmiers (nom, numero_identification, etablissement, langue_preferée)
            VALUES (?, ?, ?, ?)
        """, (nom, numero, etablissement, langue))
        infirmier_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return infirmier_id


def recuperer_stats(infirmier_id: int | None = None) -> dict:
    """Retourne des statistiques de base."""
    conn = _get_connection()
    cursor = conn.cursor()

    if infirmier_id:
        cursor.execute("SELECT COUNT(*) as total FROM rapports WHERE infirmier_id = ?", (infirmier_id,))
    else:
        cursor.execute("SELECT COUNT(*) as total FROM rapports")
    total_row = cursor.fetchone()
    total = total_row["total"] if total_row else 0

    if infirmier_id:
        cursor.execute(
            "SELECT COUNT(*) as valides FROM rapports WHERE infirmier_id = ? AND valide = 1",
            (infirmier_id,)
        )
    else:
        cursor.execute("SELECT COUNT(*) as valides FROM rapports WHERE valide = 1")
    valides_row = cursor.fetchone()
    valides = valides_row["valides"] if valides_row else 0

    conn.close()
    return {"total": total, "valides": valides}


# Initialiser la base au premier import
initialiser_base()
