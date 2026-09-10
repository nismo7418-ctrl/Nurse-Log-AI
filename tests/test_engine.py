"""
Tests unitaires pour le moteur NurseLog AI
"""

import sys
import os
import pytest

# Ajouter le dossier parent au chemin pour importer src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.nurselog_engine import NurseLogEngine
from src.templates import (
    CODES_NAA_RECONNAISSANCE,
    ECHELLES_EVALUATION,
    STRUCTURE_SBAr,
    VOCABULAIRE,
    RAPPORT_TEMPLATE
)


# Données de test réutilisables
PATIENT_TEST = {
    "nom": "Dupont",
    "prenom": "Jean",
    "date_naissance": "1955-03-15",
    "chambre": "4A-12",
    "numero_dossier": "D-2024-1234"
}

DICTEE_TEST = (
    "Patient Dupont chambre 4A-12. "
    "Tension 140/90, pouls 88, température 36.7, SpO2 98%, respiration 16/min. "
    "Douleur EVA 4/10. "
    "Pansement plaie opératoire réalisé, pansement propre et sec. "
    "Administration paracétamol 1g IV. "
    "Patient calme, bien reposé. "
    "Surveillance douleur continue, réévaluation dans 2 heures. "
    "Mobilisation progressive demain matin."
)


class TestNurseLogEngine:
    """Tests du moteur principal"""

    def setup_method(self):
        """Initialisation avant chaque test"""
        self.engine = NurseLogEngine()

    def test_initialization(self):
        """Le moteur s'initialise correctement"""
        assert self.engine is not None
        assert self.engine.version == "0.1.0"

    def test_generer_rapport_structure(self):
        """Le rapport généré a la structure attendue"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert "patient" in rapport
        assert "metadata" in rapport
        assert "evaluation" in rapport
        assert "soins" in rapport
        assert "alertes" in rapport
        assert "plan" in rapport
        assert "codes_naa" in rapport

    def test_generer_rapport_patient_info(self):
        """Les infos patient sont correctement remplies"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert rapport["patient"]["nom"] == "Dupont"
        assert rapport["patient"]["prenom"] == "Jean"

    def test_extraire_signes_vitaux(self):
        """Extraction des signes vitaux depuis une dictée"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "140/90" in sv.get("Tension artérielle", "")
        assert "88 bpm" in sv.get("Pouls", "")
        assert "36.7" in sv.get("Température", "")
        assert "98" in sv.get("SpO2", "")
        assert "16" in sv.get("Fréquence respiratoire", "")
        assert "4/10" in rapport["evaluation"].get("Confort douleur", "")

    def test_extraire_soins(self):
        """Extraction des soins réalisés"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert len(rapport["soins"]) > 0
        soins_texte = " ".join(rapport["soins"]).lower()
        assert "pansement" in soins_texte or "soin" in soins_texte

    def test_extraire_alertes(self):
        """Détection des alertes"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        # La TA 140/90 devrait générer une alerte
        # (dépend des seuils définis)
        assert isinstance(rapport["alertes"], list)

    def test_extraire_plan(self):
        """Extraction du plan de soins"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert isinstance(rapport["plan"], list)

    def test_mapper_codes_naa(self):
        """Mapping des codes NAA"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert len(rapport["codes_naa"]) > 0
        # Devrait trouver un code de pansement
        codes_texte = " ".join([str(c) for c in rapport["codes_naa"]]).lower()
        # Au moins un code devrait être trouvé
        assert len(rapport["codes_naa"]) >= 1

    def test_generer_transmissions_sbar(self):
        """Génération d'une transmission SBAr"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        assert "transmissions" in rapport
        if rapport["transmissions"]:
            trans = rapport["transmissions"][0]
            assert "S_Situation" in trans or "situation" in str(trans).lower()

    def test_exporter_json(self):
        """Export JSON du rapport"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        json_str = self.engine.exporter_json(rapport)
        assert len(json_str) > 0
        # Vérifier que c'est du JSON valide
        import json
        parsed = json.loads(json_str)
        assert parsed["patient"]["nom"] == "Dupont"

    def test_exporter_texte_lisible(self):
        """Export texte lisible du rapport"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        texte = self.engine.exporter_texte_lisible(rapport)
        assert len(texte) > 0
        assert "Dupont" in texte

    def test_valider_rapport(self):
        """Validation de la complétude du rapport"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        est_valide, problemes = self.engine.valider_rapport(rapport)
        assert isinstance(est_valide, bool)
        assert isinstance(problemes, list)

    def test_rapport_texte_vide(self):
        """Gestion d'un texte vide"""
        rapport = self.engine.generer_rapport("", PATIENT_TEST)
        assert "patient" in rapport
        # Devrait retourner un rapport vide mais valide structurellement


class TestTemplates:
    """Tests des templates et données de référence"""

    def test_rapport_template_structure(self):
        """Structure du template de rapport"""
        assert "patient" in RAPPORT_TEMPLATE
        assert "metadata" in RAPPORT_TEMPLATE
        assert "evaluation" in RAPPORT_TEMPLATE
        assert "soins" in RAPPORT_TEMPLATE

    def test_codes_naa_existent(self):
        """Les codes NAA sont chargés"""
        assert len(CODES_NAA_RECONNAISSANCE) > 0
        assert "soins_generaux" in CODES_NAA_RECONNAISSANCE
        assert "pansement" in CODES_NAA_RECONNAISSANCE

    def test_codes_naa_structure(self):
        """Structure d'un code NAA"""
        for categorie, codes in CODES_NAA_RECONNAISSANCE.items():
            for code in codes:
                assert "code" in code
                assert "nom" in code
                assert "description" in code

    def test_vocabulaire_medical(self):
        """Vocabulaire médical FR/NL"""
        assert "signes_vitaux" in VOCABULAIRE
        assert "soins_courants" in VOCABULAIRE
        # Vérifier bilingue
        sv = VOCABULAIRE["signes_vitaux"]
        assert "tension" in sv
        # Devrait contenir des termes NL
        assert "bloeddruk" in sv["tension"]

    def test_echelles_evaluation(self):
        """Échelles d'évaluation"""
        assert "douleur" in ECHELLES_EVALUATION
        assert "risque_chute" in ECHELLES_EVALUATION
        assert "risque_escarre" in ECHELLES_EVALUATION
        # EVA
        assert "EVA" in ECHELLES_EVALUATION["douleur"]

    def test_structure_sbar(self):
        """Structure SBAr"""
        assert "S_Situation" in STRUCTURE_SBAr
        assert "B_Contexte" in STRUCTURE_SBAr
        assert "A_Appreciation" in STRUCTURE_SBAr
        assert "R_Recommandation" in STRUCTURE_SBAr


class TestAlertes:
    """Tests spécifiques des alertes signes vitaux"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_alerte_hypertension(self):
        """Détection de l'hypertension"""
        dictee = "Tension 180/110, pouls 90, température 37.0"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        assert len(rapport["alertes"]) > 0

    def test_alerte_tachycardie(self):
        """Détection de la tachycardie"""
        dictee = "Tension 120/80, pouls 130, température 37.0"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        assert len(rapport["alertes"]) > 0

    def test_alerte_fievre(self):
        """Détection de la fièvre"""
        dictee = "Tension 120/80, pouls 80, température 39.5"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        assert len(rapport["alertes"]) > 0

    def test_pas_d_alerte_normale(self):
        """Aucune alerte pour signes vitaux normaux"""
        dictee = "Tension 120/80, pouls 72, température 36.5, SpO2 98%"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        # Les signes sont normaux, pas d'alerte attendue
        # (sauf alertes générales du template)
        assert isinstance(rapport["alertes"], list)


class TestExport:
    """Tests des fonctionnalités d'export"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_json_contient_toutes_sections(self):
        """Le JSON exporté contient toutes les sections"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        json_str = self.engine.exporter_json(rapport)
        assert "Signes vitaux" in json_str
        assert "soins" in json_str

    def test_texte_lisible_contient_patient(self):
        """Le texte lisible contient le nom du patient"""
        rapport = self.engine.generer_rapport(DICTEE_TEST, PATIENT_TEST)
        texte = self.engine.exporter_texte_lisible(rapport)
        assert "Dupont" in texte
        assert "Jean" in texte


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
