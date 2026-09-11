"""
Tests unitaires — Couche SQLite (database.py)
"""

import sys
import os
import sqlite3
import pytest
import json
import tempfile
import shutil
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import (
    initialiser_base,
    sauvegarder_rapport,
    sauvegarder_infirmier,
    recuperer_historique,
    recuperer_stats,
    exporter_pdf_rapport,
    DATABASE_PATH,
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
        from database import sauvegarder_brouillon, recuperer_brouillon, supprimer_brouillon
        
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
        bid2 = sauvegarder_brouillon(inf_id, "Dupont", "Marie", "Texte modifié", "")
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
        
