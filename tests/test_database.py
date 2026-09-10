"""
Tests unitaires — Couche SQLite (database.py)
"""

import sys
import os
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
