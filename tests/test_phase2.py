"""
Tests Phase 2 — Qualité des rapports générés
=============================================
Couvre :
  - score_completude()
  - Cross-referencing validation (valider_rapport)
  - Extraction médicaments améliorée (voie)
  - SBAr enrichi
  - Plan extraction NL
  - Soins/alertes NL renforcés
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.nurselog_engine import NurseLogEngine


PATIENT_TEST = {
    "nom": "Dupont",
    "prenom": "Jean",
    "date_naissance": "1955-03-15",
    "chambre": "4A-12",
    "numero_dossier": "D-2024-1234"
}


class TestScoreCompletude:
    """Tests du score de complétude"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_rapport_complet_score_eleve(self):
        """Un rapport avec tous les éléments doit avoir un score >= 80."""
        rapport = self.engine.generer_rapport(
            "Patient Dupont chambre 4A-12. Tension 140/90, pouls 88, "
            "température 36.7, SpO2 98%. Pansement plaie réalisé. "
            "Paracétamol 1g IV. Surveillance douleur, réévaluation dans 2h.",
            PATIENT_TEST
        )
        score = self.engine.score_completude(rapport)
        assert score["score"] >= 80
        assert score["complet"] is True
        assert score["incomplet"] is False

    def test_rapport_vide_score_faible(self):
        """Un rapport vide doit avoir un score < 40."""
        rapport = self.engine.generer_rapport("", PATIENT_TEST)
        score = self.engine.score_completude(rapport)
        assert score["score"] < 40
        assert score["incomplet"] is True
        assert score["complet"] is False

    def test_rapport_partiel(self):
        """Un rapport avec quelques éléments doit être partiel."""
        rapport = self.engine.generer_rapport(
            "Tension 130/80. Pansement réalisé.",
            PATIENT_TEST
        )
        score = self.engine.score_completude(rapport)
        assert 0 <= score["score"] <= 100
        # Doit avoir au moins les critères patient + soins
        assert len(score["details"]) == 5

    def test_details_structure(self):
        """Chaque critère doit avoir les bonnes clés."""
        rapport = self.engine.generer_rapport("Tension 120/80", PATIENT_TEST)
        score = self.engine.score_completude(rapport)
        for critere in score["details"]:
            assert "criter" in critere
            assert "ok" in critere
            assert "poids" in critere
            assert "note" in critere

    def test_poids_total_100(self):
        """La somme des poids doit être 100."""
        rapport = self.engine.generer_rapport("Tension 120/80", PATIENT_TEST)
        score = self.engine.score_completude(rapport)
        total_poids = sum(c["poids"] for c in score["details"])
        assert total_poids == 100


class TestCrossReferencing:
    """Tests de la validation croisée (logique clinique)"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_douleur_elevee_sans_traitement(self):
        """Douleur >= 7 sans antalgique → warning."""
        rapport = self.engine.generer_rapport(
            "Douleur EVA 8/10. Patient souffre. Surveillance.",
            PATIENT_TEST
        )
        est_valide, warnings = self.engine.valider_rapport(rapport)
        # Doit y avoir un warning sur la douleur non traitée
        warnings_str = " ".join(warnings).lower()
        assert "douleur" in warnings_str or "antalgique" in warnings_str or "traitement" in warnings_str

    def test_fievre_sans_antipyrétique(self):
        """Fièvre >= 38.5 sans antipyrétique → warning."""
        rapport = self.engine.generer_rapport(
            "Température 39.2°C. Patient fébrile. Surveillance.",
            PATIENT_TEST
        )
        est_valide, warnings = self.engine.valider_rapport(rapport)
        warnings_str = " ".join(warnings).lower()
        assert "fièvre" in warnings_str or "antipyrétique" in warnings_str or "paracétamol" in warnings_str

    def test_spo2_basse_sans_oxygene(self):
        """SpO2 < 95 sans oxygénothérapie → warning."""
        rapport = self.engine.generer_rapport(
            "SpO2 91%. Patient dyspnéique. Surveillance.",
            PATIENT_TEST
        )
        est_valide, warnings = self.engine.valider_rapport(rapport)
        warnings_str = " ".join(warnings).lower()
        assert "spo2" in warnings_str or "oxygène" in warnings_str or "oxygen" in warnings_str

    def test_rapport_complet_pas_de_warning_clinique(self):
        """Un rapport complet avec traitements ne doit pas avoir de warnings cliniques."""
        rapport = self.engine.generer_rapport(
            "Douleur EVA 3/10. Paracétamol 1g IV administré. "
            "Température 36.8. SpO2 98%. Tension 120/80. "
            "Pansement réalisé. Surveillance standard.",
            PATIENT_TEST
        )
        est_valide, warnings = self.engine.valider_rapport(rapport)
        # Pas de warning spécifique douleur/fièvre/SpO2
        warnings_str = " ".join(warnings).lower()
        assert "douleur >= 7" not in warnings_str
        assert "fièvre >= 38.5" not in warnings_str


class TestMedicamentsVoie:
    """Tests de l'extraction des médicaments avec voie"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_voie_iv(self):
        """Paracétamol 1g IV → voie = IV."""
        meds = self.engine._extraire_medicaments("Paracétamol 1g IV administré")
        assert len(meds) >= 1
        paracetamol = [m for m in meds if "paracétamol" in m["nom"].lower() or "paracetamol" in m["nom"].lower()]
        assert len(paracetamol) >= 1
        assert paracetamol[0]["voie"] == "IV"

    def test_voie_im(self):
        """Morphine 2mg IM → voie = IM."""
        meds = self.engine._extraire_medicaments("Morphine 2mg IM")
        morphine = [m for m in meds if "morphine" in m["nom"].lower()]
        assert len(morphine) >= 1
        assert morphine[0]["voie"] == "IM"

    def test_voie_sc(self):
        """Insuline 10 UI SC → voie = SC."""
        meds = self.engine._extraire_medicaments("Insuline 10 UI SC")
        insuline = [m for m in meds if "insuline" in m["nom"].lower()]
        assert len(insuline) >= 1
        assert insuline[0]["voie"] == "SC"

    def test_voie_po(self):
        """Ibuprofène 400mg PO → voie = PO."""
        meds = self.engine._extraire_medicaments("Ibuprofène 400mg PO")
        ibuprofene = [m for m in meds if "ibuprofène" in m["nom"].lower() or "ibuprofen" in m["nom"].lower()]
        assert len(ibuprofene) >= 1
        assert ibuprofene[0]["voie"] == "PO"

    def test_sans_voie(self):
        """Médicament sans voie explicite → voie vide."""
        meds = self.engine._extraire_medicaments("Paracétamol 1g")
        paracetamol = [m for m in meds if "paracétamol" in m["nom"].lower() or "paracetamol" in m["nom"].lower()]
        assert len(paracetamol) >= 1
        assert paracetamol[0]["voie"] == ""

    def test_structure_medicament(self):
        """Chaque médicament doit avoir les clés nom, dose, unite, voie."""
        meds = self.engine._extraire_medicaments("Paracétamol 1g IV. Morphine 2mg IM.")
        for med in meds:
            assert "nom" in med
            assert "dose" in med
            assert "unite" in med
            assert "voie" in med


class TestSBArEnrichi:
    """Tests de la génération SBAr enrichie"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_situation_inclut_douleur(self):
        """La situation SBAr doit inclure le score douleur."""
        rapport = self.engine.generer_rapport(
            "Douleur EVA 7/10. Tension 150/95. Pansement réalisé.",
            PATIENT_TEST
        )
        transmissions = rapport.get("transmissions", [])
        assert len(transmissions) >= 1
        situation = transmissions[0].get("S_Situation", "")
        assert "7" in situation or "douleur" in situation.lower()

    def test_contexte_inclut_signes_vitaux(self):
        """Le contexte SBAr doit inclure les signes vitaux."""
        rapport = self.engine.generer_rapport(
            "Tension 140/90, pouls 88, SpO2 97%. Pansement réalisé.",
            PATIENT_TEST
        )
        transmissions = rapport.get("transmissions", [])
        assert len(transmissions) >= 1
        contexte = transmissions[0].get("B_Contexte", "")
        # Doit mentionner au moins un signe vital
        assert "140" in contexte or "tension" in contexte.lower() or "pouls" in contexte.lower()

    def test_appreciation_inclut_soins(self):
        """L'appréciation SBAr doit lister les soins."""
        rapport = self.engine.generer_rapport(
            "Pansement plaie réalisé. Paracétamol 1g IV. Surveillance douleur.",
            PATIENT_TEST
        )
        transmissions = rapport.get("transmissions", [])
        assert len(transmissions) >= 1
        appreciation = transmissions[0].get("A_Appreciation", "")
        assert "pansement" in appreciation.lower() or "soin" in appreciation.lower()


class TestPlanNL:
    """Tests de l'extraction du plan en néerlandais"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_plan_volgende(self):
        """'Volgende controle morgen' doit être détecté comme plan."""
        plan = self.engine._extraire_plan("Volgende controle morgen om 9u")
        assert len(plan) >= 1

    def test_plan_herbeoordeling(self):
        """'Herbeoordeling nodig' doit être détecté comme plan."""
        plan = self.engine._extraire_plan("Herbeoordeling nodig binnen 24 uur")
        assert len(plan) >= 1

    def test_plan_morgen(self):
        """'Morgen opnieuw controleren' doit être détecté comme plan."""
        plan = self.engine._extraire_plan("Morgen opnieuw controleren")
        assert len(plan) >= 1

    def test_plan_controle(self):
        """'Controle dans 4h' doit être détecté comme plan."""
        plan = self.engine._extraire_plan("Controle dans 4h")
        assert len(plan) >= 1


class TestSoinsNL:
    """Tests du support néerlandais renforcé pour les soins"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_wondverpleging(self):
        """'Wondverpleging uitgevoerd' doit être détecté."""
        soins = self.engine._extraire_soins("Wondverpleging uitgevoerd")
        assert len(soins) >= 1

    def test_inwendig(self):
        """'Inwendig injectie' doit être détecté."""
        soins = self.engine._extraire_soins("Inwendig injectie gegeven")
        assert len(soins) >= 1

    def test_persoonlijke_verzorging(self):
        """'Persoonlijke verzorging' doit être détecté."""
        soins = self.engine._extraire_soins("Persoonlijke verzorging uitgevoerd")
        assert len(soins) >= 1

    def test_pijnmeting(self):
        """'Pijnmeting gedaan' doit être détecté."""
        soins = self.engine._extraire_soins("Pijnmeting gedaan, EVA 5/10")
        assert len(soins) >= 1

    def test_bloeddruk(self):
        """'Bloeddruk gemeten' doit être détecté."""
        soins = self.engine._extraire_soins("Bloeddruk gemeten: 130/85")
        assert len(soins) >= 1


class TestAlertesNL:
    """Tests du support néerlandais renforcé pour les alertes"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_valrisico(self):
        """'Valrisico' doit déclencher une alerte."""
        alertes = self.engine._extraire_alertes("Patient heeft valrisico")
        assert any("chute" in a.lower() or "val" in a.lower() for a in alertes)

    def test_ademnood(self):
        """'Ademnood' doit déclencher une alerte."""
        alertes = self.engine._extraire_alertes("Patient heeft ademnood")
        assert any("respiratoire" in a.lower() or "détresse" in a.lower() for a in alertes)

    def test_verwardheid(self):
        """'Verwardheid' doit déclencher une alerte."""
        alertes = self.engine._extraire_alertes("Patient toont verwardheid")
        assert any("confusion" in a.lower() or "délire" in a.lower() for a in alertes)

    def test_anticoagulans(self):
        """'Anticoagulans' doit déclencher une alerte."""
        alertes = self.engine._extraire_alertes("Patient gebruikt anticoagulans")
        assert any("anticoagulant" in a.lower() or "hémorragique" in a.lower() for a in alertes)


class TestExporterTexteLisible:
    """Tests de l'export texte lisible avec voie"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_export_inclut_medicaments(self):
        """L'export doit inclure la section médicaments."""
        rapport = self.engine.generer_rapport(
            "Paracétamol 1g IV. Pansement réalisé.",
            PATIENT_TEST
        )
        texte = self.engine.exporter_texte_lisible(rapport)
        assert "MÉDICAMENTS" in texte or "Médicaments" in texte

    def test_export_inclut_voie(self):
        """L'export doit inclure la voie d'administration."""
        rapport = self.engine.generer_rapport(
            "Paracétamol 1g IV. Pansement réalisé.",
            PATIENT_TEST
        )
        texte = self.engine.exporter_texte_lisible(rapport)
        # La voie IV doit apparaître
        assert "IV" in texte
