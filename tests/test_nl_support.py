"""
Tests spécifiques pour le support néerlandais
"""

import sys
import os
import pytest

# Ajouter src au chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nurselog_engine import NurseLogEngine


class TestNLSupport:
    """Tests du support néerlandais"""

    def setup_method(self):
        """Initialisation avant chaque test"""
        self.engine = NurseLogEngine()

    def test_bloeddruk_detection(self):
        """Test de la détection de bloeddruk (tension néerlandaise)"""
        dictee = "Bloeddruk 140/90, pols 88"
        patient_data = {
            "nom": "Dupont",
            "prenom": "Jean",
            "chambre": "4A-12",
            "numero_dossier": "D-2024-1234"
        }
        
        rapport = self.engine.generer_rapport(dictee, patient_data)
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "140/90" in sv.get("Tension artérielle", "")

    def test_pols_detection(self):
        """Test de la détection de pols néerlandais"""
        dictee = "Tension 120/80, pols 72"
        patient_data = {
            "nom": "Dupont",
            "prenom": "Jean",
            "chambre": "4A-12",
            "numero_dossier": "D-2024-1234"
        }
        
        rapport = self.engine.generer_rapport(dictee, patient_data)
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "72" in sv.get("Pouls", "")

    def test_wondverzorging_detection(self):
        """Test de la détection de wondverzorging"""
        dictee = "Wondverzorging plaie sacrum réalisé"
        patient_data = {
            "nom": "Dupont",
            "prenom": "Jean",
            "chambre": "4A-12",
            "numero_dossier": "D-2024-1234"
        }
        
        rapport = self.engine.generer_rapport(dictee, patient_data)
        assert len(rapport["soins"]) > 0
        soins_texte = " ".join(rapport["soins"]).lower()
        assert "wondverzorging" in soins_texte or "plaie" in soins_texte

    def test_valrisico_detection(self):
        """Test de la détection de valrisico"""
        dictee = "Patient met valrisico, surveiller la douleur"
        patient_data = {
            "nom": "Dupont",
            "prenom": "Jean",
            "chambre": "4A-12",
            "numero_dossier": "D-2024-1234"
        }
        
        rapport = self.engine.generer_rapport(dictee, patient_data)
        assert len(rapport["alertes"]) > 0
        alertes_texte = " ".join(rapport["alertes"]).lower()
        assert "valrisico" in alertes_texte or "risque" in alertes_texte


if __name__ == "__main__":
    pytest.main([__file__, "-v"])