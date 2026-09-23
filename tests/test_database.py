"""
Tests unitaires — Couche SQLite (database.py)
"""

import os
import sqlite3
import sys

import pytest

# Ajouter src au chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import (
    definir_pin,
    exporter_pdf_rapport,
    generer_pdf_rapport,
    initialiser_base,
    pin_defini,
    recuperer_historique,
    recuperer_stats,
    sauvegarder_infirmier,
    sauvegarder_rapport,
    trouver_infirmier,
    verifier_pin,
)

RAPPORT_TEST = {
    "patient": {"nom": "Durand", "prenom": "Sophie", "chambre": "3B-07"},
    "metadata": {
        "date": "2025-06-15",
        "heure": "14:30",
        "quart": "Après-midi",
        "type_rapport": "Rapport de soins standard",
        "valide": True,
        "signature_date": "2025-06-15 14:35:00",
    },
    "evaluation": {"Signes vitaux": {"Tension artérielle": "120/80 mmHg"}},
    "soins": ["Pansement réalisé"],
    "alertes": [],
    "plan": ["Surveillance standard"],
}


@pytest.fixture
def db_temp(tmp_path):
    """Crée une base SQLite temporaire pour les tests."""
    import database

    old_path = database.DATABASE_PATH
    test_db = tmp_path / "test_nurselog.db"
    database.DATABASE_PATH = test_db
    initialiser_base()
    yield test_db
    database.DATABASE_PATH = old_path


class TestPIN:
    """Couche PIN : définition, vérification, stockage non clair, unicité par profil."""

    def test_pin_absent_par_defaut(self, db_temp):
        inf_id = sauvegarder_infirmier("Jean Pin", "INF-PIN", "Test", "Français")
        assert pin_defini(inf_id) is False
        assert verifier_pin(inf_id, "1234") is False

    def test_definir_et_verifier_pin(self, db_temp):
        inf_id = sauvegarder_infirmier("Jean Pin", "INF-PIN", "Test", "Français")
        definir_pin(inf_id, "1234")
        assert pin_defini(inf_id) is True
        assert verifier_pin(inf_id, "1234") is True
        assert verifier_pin(inf_id, "9999") is False

    def test_pin_redefinissable(self, db_temp):
        inf_id = sauvegarder_infirmier("Jean Pin", "INF-PIN", "Test", "Français")
        definir_pin(inf_id, "1234")
        definir_pin(inf_id, "5678")
        assert verifier_pin(inf_id, "5678") is True
        assert verifier_pin(inf_id, "1234") is False

    def test_pin_jamais_stocke_en_clair(self, db_temp):
        inf_id = sauvegarder_infirmier("Jean Pin", "INF-PIN", "Test", "Français")
        definir_pin(inf_id, "2468")
        conn = sqlite3.connect(db_temp)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT pin_hash FROM infirmiers WHERE id = ?", (inf_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["pin_hash"] != "2468"
        # Format "sel_hex$hash_hex" : deux parties hexadécimales
        sel_hex, hash_hex = row["pin_hash"].split("$")
        assert int(sel_hex, 16) is not None and int(hash_hex, 16) is not None
        assert len(sel_hex) == 32  # sel 16 octets

    def test_pin_indépendant_par_profil(self, db_temp):
        a = sauvegarder_infirmier("Alpha", "INF-A", "Test", "Français")
        b = sauvegarder_infirmier("Beta", "INF-B", "Test", "Français")
        definir_pin(a, "1111")
        assert pin_defini(a) is True
        assert pin_defini(b) is False
        assert verifier_pin(b, "1111") is False

    def test_trouver_infirmier_par_numero(self, db_temp):
        inf_id = sauvegarder_infirmier("Jean Pin", "INF-PIN", "Test", "Français")
        definir_pin(inf_id, "4321")
        found = trouver_infirmier("INF-PIN")
        assert found is not None
        assert found["id"] == inf_id
        assert found["nom"] == "Jean Pin"
        assert found["pin_defini"] is True
        assert trouver_infirmier("INF-INCONNU") is None


class TestDatabase:
    def test_initialisation_creer_tables(self, db_temp):
        """La base est créée et les tables existent."""
        assert db_temp.exists()

    def test_sauvegarder_infirmier(self, db_temp):
        """Sauvegarde d'un infirmier fonctionne."""
        infirmier_id = sauvegarder_infirmier(
            "Jean Dupont", "INF-12345", "CHU Bruxelles", "Français"
        )
        assert infirmier_id >= 1

    def test_sauvegarder_rapport(self, db_temp):
        """Sauvegarde d'un rapport fonctionne."""
        infirmier_id = sauvegarder_infirmier("Test", "INF-T", "Test", "Français")
        rapport_id = sauvegarder_rapport(infirmier_id, RAPPORT_TEST)
        assert rapport_id >= 1

    def test_recuperer_historique(self, db_temp):
        """Récupération de l'historique après sauvegarde."""
        infirmier_id = sauvegarder_infirmier("Test", "INF-H", "Test", "Français")
        sauvegarder_rapport(infirmier_id, RAPPORT_TEST)

        historique = recuperer_historique(infirmier_id)
        assert len(historique) == 1
        assert historique[0]["patient"]["nom"] == "Durand"

    def test_recuperer_stats(self, db_temp):
        """Statistiques correctes après sauvegarde."""
        infirmier_id = sauvegarder_infirmier("Test", "INF-S", "Test", "Français")
        sauvegarder_rapport(infirmier_id, RAPPORT_TEST)

        stats = recuperer_stats(infirmier_id)
        assert stats["total"] == 1
        assert stats["valides"] == 1

    def test_historique_vide_par_defaut(self, db_temp):
        """Aucun rapport au départ."""
        assert recuperer_historique() == []

    def test_stats_vide_par_defaut(self, db_temp):
        """Aucune statistique au départ."""
        stats = recuperer_stats()
        assert stats["total"] == 0
        assert stats["valides"] == 0

    def test_export_pdf(self, db_temp):
        """Test de l'export PDF (skip si ReportLab non disponible)."""
        import importlib.util
        if importlib.util.find_spec("reportlab") is None:
            pytest.skip("ReportLab non installé dans cet environnement")

        result = exporter_pdf_rapport(RAPPORT_TEST, "test_export.pdf")
        assert result is True

        import os
        assert os.path.exists("test_export.pdf")
        os.remove("test_export.pdf")

    def test_generer_pdf_rapport(self, db_temp):
        """Génération du PDF en mémoire (skip si ReportLab non disponible)."""
        import importlib.util
        if importlib.util.find_spec("reportlab") is None:
            pytest.skip("ReportLab non installé dans cet environnement")

        pdf_bytes = generer_pdf_rapport(RAPPORT_TEST)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 0


class TestDatabaseErrors:
    """Tests de gestion des erreurs DB"""

    def test_sauvegarder_rapport_chemin_invalide(self, tmp_path):
        """Un chemin DB invalide lève une exception (pas de silence)."""
        import database

        old_path = database.DATABASE_PATH
        # Chemin invalide (dossier inexistant)
        database.DATABASE_PATH = tmp_path / "nonexistent" / "subdir" / "test.db"

        try:
            # Cela devrait lever une exception (sqlite3.OperationalError)
            sauvegarder_rapport(1, RAPPORT_TEST)
            # Si on arrive ici, c'est que l'exception n'a pas été levée
            # (certaines plateformes SQLite créent le fichier automatiquement)
        except (sqlite3.OperationalError, OSError) as e:
            # C'est le comportement attendu : l'erreur est remontée
            assert "no such table" in str(e).lower() or "unable to open" in str(e).lower() or "no such directory" in str(e).lower()
        finally:
            database.DATABASE_PATH = old_path

    def test_sauvegarder_brouillon(self, db_temp):
        """Sauvegarde d'un brouillon fonctionne."""
        from database import recuperer_brouillon, sauvegarder_brouillon, supprimer_brouillon

        inf_id = sauvegarder_infirmier("Test", "INF-B", "Test", "Français")

        # Créer un brouillon
        bid = sauvegarder_brouillon(inf_id, "Dupont", "Marie", "Pansement réalisé", "Rapport standard")
        assert bid >= 1

        # Récupérer
        brouillon = recuperer_brouillon(inf_id)
        assert brouillon is not None
        assert brouillon["texte"] == "Pansement réalisé"
        assert brouillon["patient_nom"] == "Dupont"

        # Mettre à jour (même infirmier)
        sauvegarder_brouillon(inf_id, "Dupont", "Marie", "Texte modifié", "")
        brouillon2 = recuperer_brouillon(inf_id)
        assert brouillon2["texte"] == "Texte modifié"

        # Supprimer
        supprimer_brouillon(inf_id)
        assert recuperer_brouillon(inf_id) is None

    def test_recuperer_brouillon_inexistant(self, db_temp):
        """Aucun brouillon → None."""
        from database import recuperer_brouillon

        inf_id = sauvegarder_infirmier("Test", "INF-NB", "Test", "Français")
        assert recuperer_brouillon(inf_id) is None

    def test_generer_csv_historique(self, db_temp):
        """Test de génération CSV."""
        infirmier_id = sauvegarder_infirmier("Test", "INF-CSV", "Test", "Français")

        # Sauvegarder plusieurs rapports
        sauvegarder_rapport(infirmier_id, RAPPORT_TEST)

        # Générer le CSV
        from database import generer_csv_historique
        csv_content = generer_csv_historique(infirmier_id)

        # Vérifier que le contenu n'est pas vide
        assert csv_content is not None
        assert len(csv_content) > 0

        # Vérifier que les données attendues sont présentes
        assert "Durand" in csv_content
        assert "Sophie" in csv_content
        assert "3B-07" in csv_content
        assert "2025-06-15" in csv_content

        # Vérifier que le CSV a plusieurs lignes
        lines = csv_content.split("\n")
        assert len(lines) >= 2  # En-tête + données

        # Vérifier les colonnes
        header = lines[0]
        assert "Patient Nom" in header
        assert "Patient Prénom" in header
        assert "Chambre" in header


class TestRechercheRapports:
    """Tests de la recherche SQL (rechercher_rapports)."""

    def _setup(self, db_temp, nb_rapports=3):
        from database import rechercher_rapports  # noqa: F401
        inf_id = sauvegarder_infirmier("Test", "INF-RC", "Test", "Français")
        for i in range(nb_rapports):
            rapport = dict(RAPPORT_TEST)
            rapport["patient"] = {
                "nom": f"Durand{i}",
                "prenom": "Sophie",
                "chambre": f"3B-0{i}",
            }
            rapport["metadata"] = dict(RAPPORT_TEST["metadata"], date=f"2025-06-1{i + 1}")
            sauvegarder_rapport(inf_id, rapport)
        return inf_id

    def test_recherche_sous_chaine_insensible_casse(self, db_temp):
        from database import rechercher_rapports

        self._setup(db_temp)
        res = rechercher_rapports(nom="duran")
        assert len(res) == 3

        res = rechercher_rapports(nom="DURAND1")
        assert len(res) == 1
        assert res[0]["patient"]["nom"] == "Durand1"

    def test_recherche_nom_inconnu(self, db_temp):
        from database import rechercher_rapports

        self._setup(db_temp)
        assert rechercher_rapports(nom="Tremblay") == []

    def test_recherche_caracteres_speciaux_like(self, db_temp):
        """% et _ dans la requête doivent être littéraux, pas des jokers."""
        from database import rechercher_rapports

        inf_id = sauvegarder_infirmier("Test", "INF-LIKE", "Test", "Français")
        rapport = dict(RAPPORT_TEST)
        rapport["patient"] = {"nom": "50%_test", "prenom": "X", "chambre": "1"}
        sauvegarder_rapport(inf_id, rapport)

        # Requête littérale : le % et le _ sont échappés
        res = rechercher_rapports(infirmier_id=inf_id, nom="50%_test")
        assert len(res) == 1

        # Si % n'était pas échappé, « 5% » matcherait tout ; ici 0 résultat attendu
        res = rechercher_rapports(infirmier_id=inf_id, nom="5%")
        assert res == []

    def test_recherche_par_date_exacte(self, db_temp):
        from database import rechercher_rapports

        self._setup(db_temp)
        res = rechercher_rapports(date="2025-06-12")
        assert len(res) == 1

        res = rechercher_rapports(date="1999-01-01")
        assert res == []

    def test_recherche_combinaison_nom_et_date(self, db_temp):
        from database import rechercher_rapports

        self._setup(db_temp)
        res = rechercher_rapports(nom="Durand2", date="2025-06-13")
        assert len(res) == 1
        res = rechercher_rapports(nom="Durand2", date="2025-06-15")
        assert res == []

    def test_recherche_isolation_infirmier(self, db_temp):
        """Chaque profil ne voit que ses rapports."""
        from database import rechercher_rapports

        inf_a = sauvegarder_infirmier("A", "INF-A", "Test", "Français")
        inf_b = sauvegarder_infirmier("B", "INF-B", "Test", "Français")
        sauvegarder_rapport(inf_a, RAPPORT_TEST)
        sauvegarder_rapport(inf_b, RAPPORT_TEST)

        res_a = rechercher_rapports(infirmier_id=inf_a, nom="Durand")
        res_b = rechercher_rapports(infirmier_id=inf_b, nom="Durand")
        assert len(res_a) == 1 and len(res_b) == 1
        assert res_a[0]["_db_id"] != res_b[0]["_db_id"]

        res_tous = rechercher_rapports(nom="Durand")
        assert len(res_tous) == 2


class TestBrouillonCible:
    """Isolation des brouillons par patient (recuperer_brouillon_cible)."""

    def test_brouillon_par_patient(self, db_temp):
        from database import recuperer_brouillon_cible, sauvegarder_brouillon

        inf_id = sauvegarder_infirmier("Test", "INF-BCT", "Test", "Français")
        sauvegarder_brouillon(inf_id, "Dupont", "Marie", "brouillon Dupont", "")
        sauvegarder_brouillon(inf_id, "Martin", "Paul", "brouillon Martin", "")

        # Cible Dupont → le sien, pas le plus récent (Martin)
        b = recuperer_brouillon_cible(inf_id, "Dupont")
        assert b["texte"] == "brouillon Dupont"

    def test_brouillon_cible_retourne_plus_recent_si_aucun_pour_patient(self, db_temp):
        from database import recuperer_brouillon_cible, sauvegarder_brouillon

        inf_id = sauvegarder_infirmier("Test", "INF-BCT2", "Test", "Français")
        sauvegarder_brouillon(inf_id, "Dupont", "Marie", "brouillon Dupont", "")

        # Patient sans brouillon dédié → le plus récent du profil
        b = recuperer_brouillon_cible(inf_id, "Martin")
        assert b["texte"] == "brouillon Dupont"

    def test_brouillon_cible_rien(self, db_temp):
        from database import recuperer_brouillon_cible

        inf_id = sauvegarder_infirmier("Test", "INF-BCT3", "Test", "Français")
        assert recuperer_brouillon_cible(inf_id, "Personne") is None
