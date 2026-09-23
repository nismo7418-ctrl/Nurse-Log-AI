"""
NurseLog AI — Couche de persistance SQLite
==========================================
Stockage local des rapports de soins et des profils infirmiers.
Conforme au principe de minimisation des données (RGPD).
"""

import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path

# Surchargeable par variable d'environnement (ex. Docker : /app/data/nurselog.db)
DATABASE_PATH = Path(
    os.environ.get("NURSELOG_DB_PATH", str(Path(__file__).parent / "nurselog.db"))
)


def _get_connection():
    """Retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # Évite « database is locked » si un autre processus (relais audio, export) écrit en parallèle
    conn.execute("PRAGMA busy_timeout=5000")
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

    # Table des brouillons (persistance de dictée en cours)
    # Clé composite : un infirmier peut avoir plusieurs brouillons (un par patient)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brouillons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            infirmier_id INTEGER,
            patient_nom TEXT DEFAULT '',
            patient_prenom TEXT DEFAULT '',
            texte TEXT NOT NULL,
            type_rapport TEXT,
            date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (infirmier_id) REFERENCES infirmiers(id)
        )
    """)

    # Index pour la recherche par infirmier + patient
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_brouillons_infirmier_patient
        ON brouillons(infirmier_id, patient_nom)
    """)

    # Migration : PIN de connexion / confirmation de signature (hashé, jamais en clair)
    colonnes = {row[1] for row in cursor.execute("PRAGMA table_info(infirmiers)")}
    if "pin_hash" not in colonnes:
        cursor.execute("ALTER TABLE infirmiers ADD COLUMN pin_hash TEXT")

    conn.commit()
    conn.close()


# ============================================================================
# PIN par profil (PBKDF2-SHA256 + sel aléatoire, constant-time compare)
# ============================================================================

_PBKDF2_ITÉRATIONS = 200_000


def _hacher_pin(pin: str, sel_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), bytes.fromhex(sel_hex), _PBKDF2_ITÉRATIONS
    ).hex()


def _hasher_pin(pin: str) -> str:
    sel = os.urandom(16).hex()
    return f"{sel}${_hacher_pin(pin, sel)}"


def _verifier_pin_hash(pin: str, hash_stocke: str | None) -> bool:
    if not hash_stocke or "$" not in hash_stocke:
        return False
    sel_hex, hash_hex = hash_stocke.split("$", 1)
    try:
        return hmac.compare_digest(_hacher_pin(pin, sel_hex), hash_hex)
    except (ValueError, TypeError):
        return False


def definir_pin(infirmier_id: int, pin: str) -> None:
    """Définit (ou redéfinit) le PIN d'un profil infirmier."""
    conn = _get_connection()
    conn.execute(
        "UPDATE infirmiers SET pin_hash = ? WHERE id = ?",
        (_hasher_pin(pin), infirmier_id),
    )
    conn.commit()
    conn.close()


def verifier_pin(infirmier_id: int, pin: str) -> bool:
    """Vérifie le PIN fourni contre le hash stocké (False si aucun PIN défini)."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT pin_hash FROM infirmiers WHERE id = ?", (infirmier_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return False
    return _verifier_pin_hash(pin, row["pin_hash"])


def pin_defini(infirmier_id: int) -> bool:
    """True si le profil a un PIN actif."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT pin_hash FROM infirmiers WHERE id = ?", (infirmier_id,)
    ).fetchone()
    conn.close()
    return row is not None and row["pin_hash"] is not None


def trouver_infirmier(numero: str) -> dict | None:
    """Retourne {id, nom, pin_defini} pour un numéro d'identification."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT id, nom, pin_hash FROM infirmiers WHERE numero_identification = ?",
        (numero,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "nom": row["nom"],
        "pin_defini": row["pin_hash"] is not None,
    }


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


def _like_escape(term: str) -> str:
    """Échappe les caractères spéciaux LIKE (% _ \\) pour une recherche littérale."""
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def rechercher_rapports(
    infirmier_id: int | None = None,
    nom: str | None = None,
    date: str | None = None,
    limite: int = 100,
) -> list[dict]:
    """
    Recherche des rapports avec filtrage côté base (SQL).

    - infirmier_id : restreint à ce profil (None = tous)
    - nom          : sous-chaîne littérale dans nom/prénom patient (LIKE échappé)
    - date         : correspondance exacte sur date_rapport (format YYYY-MM-DD)
    - limite       : nombre maximum de rapports retournés

    Remplace le filtrage côté client qui ne voyait que les `limite` premiers rapports.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    conditions: list[str] = []
    params: list = []

    if infirmier_id:
        conditions.append("infirmier_id = ?")
        params.append(infirmier_id)
    if nom:
        like = f"%{_like_escape(nom.strip())}%"
        conditions.append("(patient_nom LIKE ? ESCAPE '\\' OR patient_prenom LIKE ? ESCAPE '\\')")
        params.extend([like, like])
    if date:
        conditions.append("date_rapport = ?")
        params.append(date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cursor.execute(
        f"SELECT * FROM rapports {where} ORDER BY date_creation DESC LIMIT ?",
        [*params, limite],
    )

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
# initialiser_base()  # Désactivé pour éviter les effets de bord dans le déploiement


def sauvegarder_brouillon(infirmier_id: int, patient_nom: str, patient_prenom: str, texte: str, type_rapport: str = "") -> int:
    """
    Sauvegarde ou met à jour un brouillon de dictée.
    Un brouillon est identifié par (infirmier_id, patient_nom).
    Retourne l'ID du brouillon.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    # Vérifier si un brouillon existe déjà pour cet infirmier + patient
    cursor.execute(
        "SELECT id FROM brouillons WHERE infirmier_id = ? AND patient_nom = ? LIMIT 1",
        (infirmier_id, patient_nom)
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE brouillons
            SET patient_prenom = ?, texte = ?, type_rapport = ?, date_maj = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (patient_prenom, texte, type_rapport, existing["id"]))
        brouillon_id = existing["id"]
    else:
        cursor.execute("""
            INSERT INTO brouillons (infirmier_id, patient_nom, patient_prenom, texte, type_rapport)
            VALUES (?, ?, ?, ?, ?)
        """, (infirmier_id, patient_nom, patient_prenom, texte, type_rapport))
        brouillon_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return brouillon_id


def recuperer_brouillon(infirmier_id: int, patient_nom: str = "") -> dict | None:
    """
    Récupère le dernier brouillon pour un infirmier (optionnellement filtré par patient).
    Si patient_nom est fourni, retourne le brouillon pour ce patient.
    Sinon, retourne le brouillon le plus récent.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    if patient_nom:
        cursor.execute(
            "SELECT * FROM brouillons WHERE infirmier_id = ? AND patient_nom = ? ORDER BY date_maj DESC LIMIT 1",
            (infirmier_id, patient_nom)
        )
    else:
        cursor.execute(
            "SELECT * FROM brouillons WHERE infirmier_id = ? ORDER BY date_maj DESC LIMIT 1",
            (infirmier_id,)
        )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "patient_nom": row["patient_nom"],
        "patient_prenom": row["patient_prenom"],
        "texte": row["texte"],
        "type_rapport": row["type_rapport"],
        "date_maj": row["date_maj"],
    }


def recuperer_brouillon_cible(infirmier_id: int, patient_nom: str = "") -> dict | None:
    """
    Retourne le brouillon ciblé pour la page de dictée :
    - si patient_nom est fourni, le brouillon de CE patient (isolation par patient) ;
    - sinon le brouillon le plus récent du profil (comportement d'origine).
    """
    patient_nom = (patient_nom or "").strip()
    brouillon = recuperer_brouillon(infirmier_id, patient_nom)
    if brouillon is None and patient_nom:
        # Pas encore de brouillon pour ce patient : revenir au plus récent
        brouillon = recuperer_brouillon(infirmier_id)
    return brouillon


def recuperer_tous_brouillons(infirmier_id: int) -> list[dict]:
    """Récupère TOUS les brouillons d'un infirmier (multi-patients)."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM brouillons WHERE infirmier_id = ? ORDER BY date_maj DESC",
        (infirmier_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "patient_nom": row["patient_nom"],
            "patient_prenom": row["patient_prenom"],
            "texte": row["texte"],
            "type_rapport": row["type_rapport"],
            "date_maj": row["date_maj"],
        }
        for row in rows
    ]


def supprimer_brouillon(infirmier_id: int, patient_nom: str = "") -> None:
    """Supprime un brouillon (optionnellement filtré par patient)."""
    conn = _get_connection()
    cursor = conn.cursor()
    if patient_nom:
        cursor.execute(
            "DELETE FROM brouillons WHERE infirmier_id = ? AND patient_nom = ?",
            (infirmier_id, patient_nom)
        )
    else:
        cursor.execute("DELETE FROM brouillons WHERE infirmier_id = ?", (infirmier_id,))
    conn.commit()
    conn.close()


def exporter_pdf_rapport(rapport: dict, chemin_fichier: str):
    """
    Exporte un rapport en PDF avec ReportLab.
    Génère un document PDF conforme aux standards infirmiers.
    """
    try:
        # Vérifier si ReportLab est disponible
        import importlib.util
        reportlab_spec = importlib.util.find_spec("reportlab")
        if reportlab_spec is None:
            print("ReportLab non disponible. Impossible d'exporter en PDF.")
            return False

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        # Créer le document PDF
        doc = SimpleDocTemplate(chemin_fichier, pagesize=letter)
        styles = getSampleStyleSheet()

        # Style personnalisé pour les titres
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            alignment=1,  # Centré
        )

        # Style pour les sections
        section_style = ParagraphStyle(
            'Section',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=6,
        )

        # Contenu du document
        story = []

        # Titre principal
        story.append(Paragraph("Rapport de Soins Infirmier", title_style))
        story.append(Spacer(1, 12))

        # Informations patient
        patient = rapport.get('patient', {})
        metadata = rapport.get('metadata', {})

        story.append(Paragraph("Informations Patient", section_style))

        # Tableau des informations patient
        patient_data = [
            ["Nom", patient.get('nom', 'N/A')],
            ["Prénom", patient.get('prenom', 'N/A')],
            ["Chambre/Lieu", patient.get('chambre', 'N/A')],
            ["Date", metadata.get('date', 'N/A')],
            ["Heure", metadata.get('heure', 'N/A')],
            ["Quart", metadata.get('quart', 'N/A')],
        ]

        patient_table = Table(patient_data)
        patient_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica')
        ]))
        story.append(patient_table)
        story.append(Spacer(1, 12))

        # Évaluation clinique
        if 'evaluation' in rapport:
            story.append(Paragraph("Évaluation Clinique", section_style))
            for key, value in rapport['evaluation'].items():
                story.append(Paragraph(f"{key}: {value}", styles['Normal']))
            story.append(Spacer(1, 12))

        # Soins réalisés
        if 'soins' in rapport:
            story.append(Paragraph("Soins Réalisés", section_style))
            for soin in rapport['soins']:
                story.append(Paragraph(f"• {soin}", styles['Normal']))
            story.append(Spacer(1, 12))

        # Alertes
        if 'alertes' in rapport and rapport['alertes']:
            story.append(Paragraph("Alertes", section_style))
            for alerte in rapport['alertes']:
                story.append(Paragraph(f"⚠️ {alerte}", styles['Normal']))
        else:
            story.append(Paragraph("Alertes", section_style))
            story.append(Paragraph("Aucune alerte", styles['Normal']))
        story.append(Spacer(1, 12))

        # Plan de soins
        if 'plan' in rapport:
            story.append(Paragraph("Plan de Soins", section_style))
            for action in rapport['plan']:
                story.append(Paragraph(f"📌 {action}", styles['Normal']))
            story.append(Spacer(1, 12))

        # Codes NAA
        if 'codes_naa' in rapport and rapport['codes_naa']:
            story.append(Paragraph("Codes NAA (Facturation)", section_style))
            for code in rapport['codes_naa']:
                code_text = f"Code: {code.get('code', 'N/A')} | {code.get('nom', '')} | Source: {code.get('source', 'N/A')}"
                story.append(Paragraph(code_text, styles['Normal']))

        # Signature
        story.append(Spacer(1, 24))
        story.append(Paragraph("Signature", section_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Nom : _________________________", styles['Normal']))
        story.append(Paragraph("Date : _________________________", styles['Normal']))

        # Générer le PDF
        doc.build(story)
        return True
    except Exception as e:
        print(f"Erreur lors de l'export PDF: {e}")
        return False


def generer_pdf_rapport(rapport: dict) -> bytes | None:
    """
    Génère le PDF d'un rapport en mémoire (bytes), pour téléchargement direct.
    Réutilise `exporter_pdf_rapport()` via un fichier temporaire.
    Retourne None si ReportLab n'est pas disponible ou en cas d'erreur.
    """
    import os
    import tempfile

    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
    except Exception:
        return None

    try:
        if not exporter_pdf_rapport(rapport, tmp_path):
            return None
        with open(tmp_path, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def generer_csv_historique(infirmier_id: int | None = None) -> str:
    """
    Génère le contenu CSV de l'historique des rapports (en mémoire).
    Retourne une chaîne vide si aucun rapport.
    Utilise l'encodage UTF-8 avec BOM (compatible Excel FR/NL).
    """
    import csv
    import io

    rapports = recuperer_historique(infirmier_id=infirmier_id, limite=500)

    if not rapports:
        return ""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Date", "Heure", "Quart", "Type",
        "Patient Nom", "Patient Prénom", "Chambre", "N° Dossier",
        "Soins (nb)", "Alertes (nb)", "Plan (nb)", "Validé", "Signature Date"
    ])

    for r in rapports:
        patient = r.get("patient", {})
        metadata = r.get("metadata", {})
        writer.writerow([
            r.get("_db_id", ""),
            metadata.get("date", ""),
            metadata.get("heure", ""),
            metadata.get("quart", ""),
            metadata.get("type_rapport", ""),
            patient.get("nom", ""),
            patient.get("prenom", ""),
            patient.get("chambre", ""),
            patient.get("numero_dossier", ""),
            len(r.get("soins", [])),
            len(r.get("alertes", [])),
            len(r.get("plan", [])),
            "Oui" if metadata.get("valide") else "Non",
            metadata.get("signature_date", ""),
        ])

    return buffer.getvalue()


def exporter_csv_historique(infirmier_id: int | None = None, chemin_fichier: str = "historique.csv") -> bool:
    """
    Exporte l'historique des rapports en CSV (fichier sur disque).
    Utile pour les statistiques et l'analyse.
    """
    contenu = generer_csv_historique(infirmier_id)
    if not contenu:
        return False
    try:
        with open(chemin_fichier, "w", newline="", encoding="utf-8-sig") as f:
            f.write(contenu)
        return True
    except Exception as e:
        print(f"Erreur lors de l'export CSV: {e}")
        return False
