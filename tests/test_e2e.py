"""
test_e2e.py — Test d'intégration bout-en-bout (E2E)
=====================================================
Valide le workflow complet :
  dictée → génération rapport → scoring → validation → export texte → export JSON

Ce test simule le parcours réel d'une infirmière qui dicte un rapport
de soins et le valide avant export.
"""

import json
import sys
from pathlib import Path

import pytest

# Assurer que src/ est dans le path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nurselog_engine import NurseLogEngine

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def engine():
    return NurseLogEngine()


@pytest.fixture
def patient_data():
    return {
        "nom": "Martin",
        "prenom": "Jean",
        "chambre": "412",
        "date_naissance": "1955-03-14",
        "numero_dossier": "D-2025-0847",
        "quart": "Journée",
        "langue": "Français",
        "type_rapport": "Rapport de soins standard",
    }


@pytest.fixture
def dictee_complete():
    """Dictée réaliste couvrant tous les éléments d'un rapport complet."""
    return (
        "Patient Jean Martin chambre 412. "
        "Tension artérielle 130/85, pouls 78 bpm, température 36.8, "
        "SpO2 97%, fréquence respiratoire 16. "
        "Douleur EVA 3/10. "
        "Pansement réalisé sur plaie jambe droite. "
        "Injection paracétamol 1g IV. "
        "Surveillance standard au quart. "
        "Réévaluation prévue à 14h. "
        "Patient stable, orienté, collaborant."
    )


@pytest.fixture
def dictee_alerte():
    """Dictée avec alertes cliniques (fièvre + douleur sévère)."""
    return (
        "Patient Marie Dubois chambre 203. "
        "Tension 110/70, pouls 95, température 39.2, SpO2 94%. "
        "Douleur EVA 8/10. "
        "Injection morphine 2mg IV. "
        "Alerte médecin pour fièvre et douleur. "
        "Surveillance renforcée toutes les heures. "
        "Oxygénothérapie 2L/min."
    )


@pytest.fixture
def dictee_minimale():
    """Dictée minimale — rapport incomplet."""
    return "Patient stable. Surveillance standard."


# ============================================================
# Tests E2E
# ============================================================

class TestWorkflowComplet:
    """Workflow complet : dictée → rapport → score → validation → export."""

    def test_dictee_complete_generer_rapport(self, engine, patient_data, dictee_complete):
        """Une dictée complète génère un rapport structuré avec toutes les sections."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)

        # Structure de base
        assert "patient" in rapport
        assert "evaluation" in rapport
        assert "soins" in rapport
        assert "alertes" in rapport
        assert "plan" in rapport
        assert "metadata" in rapport
        assert "transmissions" in rapport

        # Patient correctement rempli
        assert rapport["patient"]["nom"] == "Martin"
        assert rapport["patient"]["prenom"] == "Jean"
        assert rapport["patient"]["chambre"] == "412"

        # Signes vitaux extraits
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "Tension artérielle" in sv
        assert "130" in sv["Tension artérielle"]
        assert "85" in sv["Tension artérielle"]
        assert "Pouls" in sv
        assert "78" in sv["Pouls"]

        # Soins détectés
        soins_texte = " ".join(rapport["soins"]).lower()
        assert "pansement" in soins_texte

        # Plan présent
        assert len(rapport["plan"]) > 0

    def test_dictee_complete_score_completude(self, engine, patient_data, dictee_complete):
        """Un rapport complet obtient un score élevé (≥ 70%)."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)
        score = engine.score_completude(rapport)

        assert score["score"] >= 70, f"Score trop bas: {score['score']}%"
        assert score["complet"] is True or score["score"] >= 80

    def test_dictee_complete_validation(self, engine, patient_data, dictee_complete):
        """Un rapport complet passe la validation sans erreurs bloquantes."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)
        est_valide, warnings = engine.valider_rapport(rapport)

        # Le rapport doit être valide (pas d'erreurs bloquantes)
        assert est_valide is True, f"Rapport non valide: {warnings}"

    def test_dictee_complete_export_texte(self, engine, patient_data, dictee_complete):
        """L'export texte lisible contient les sections clés."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)
        texte = engine.exporter_texte_lisible(rapport)

        assert "RAPPORT DE SOINS" in texte
        assert "Martin" in texte
        assert "Jean" in texte
        assert "412" in texte
        assert "NURSELOG AI" in texte

    def test_dictee_complete_export_json(self, engine, patient_data, dictee_complete):
        """L'export JSON est valide et contient toutes les sections."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)
        json_str = engine.exporter_json(rapport)

        # JSON valide
        parsed = json.loads(json_str)
        assert "patient" in parsed
        assert "evaluation" in parsed
        assert "soins" in parsed
        assert "plan" in parsed
        assert "metadata" in parsed

    def test_workflow_complet_de_bout_en_bout(self, engine, patient_data, dictee_complete):
        """Workflow complet : dictée → rapport → score → validation → exports."""
        # 1. Génération
        rapport = engine.generer_rapport(dictee_complete, patient_data)
        assert rapport is not None

        # 2. Scoring
        score = engine.score_completude(rapport)
        assert score["score"] >= 70

        # 3. Validation
        est_valide, warnings = engine.valider_rapport(rapport)
        assert est_valide is True

        # 4. Export texte
        texte = engine.exporter_texte_lisible(rapport)
        assert len(texte) > 100

        # 5. Export JSON
        json_str = engine.exporter_json(rapport)
        parsed = json.loads(json_str)
        assert parsed["patient"]["nom"] == "Martin"

    def test_workflow_export_fichier(self, engine, patient_data, dictee_complete, tmp_path):
        """Le rapport peut être sauvegardé dans un fichier."""
        rapport = engine.generer_rapport(dictee_complete, patient_data)

        # Export JSON → fichier
        json_file = tmp_path / "rapport.json"
        json_file.write_text(engine.exporter_json(rapport), encoding="utf-8")
        assert json_file.exists()
        assert json.loads(json_file.read_text(encoding="utf-8"))["patient"]["nom"] == "Martin"

        # Export texte → fichier
        texte_file = tmp_path / "rapport.txt"
        texte_file.write_text(engine.exporter_texte_lisible(rapport), encoding="utf-8")
        assert texte_file.exists()
        assert "Martin" in texte_file.read_text(encoding="utf-8")


class TestWorkflowAvecAlertes:
    """Workflow avec alertes cliniques — validation doit détecter les incohérences."""

    def test_fievre_sans_traitement(self, engine, patient_data, dictee_alerte):
        """Fièvre 39.2 + douleur 8/10 avec traitement → validation OK."""
        rapport = engine.generer_rapport(dictee_alerte, patient_data)
        est_valide, warnings = engine.valider_rapport(rapport)

        # Le rapport contient morphine (antalgique) → pas d'alerte douleur
        # Il contient "surveillance renforcée" → pas d'alerte fièvre
        # Il contient "oxygen"/"oxygénation" → pas d'alerte SpO2
        alertes_critiques = [w for w in warnings if "\U0001f534" in w]
        assert len(alertes_critiques) == 0, f"Alertes critiques inattendues: {alertes_critiques}"

    def test_fievre_detectee(self, engine, patient_data, dictee_alerte):
        """La fièvre 39.2 est correctement extraite."""
        rapport = engine.generer_rapport(dictee_alerte, patient_data)
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "Température" in sv
        assert "39" in sv["Température"]

    def test_douleur_severe_detectee(self, engine, patient_data, dictee_alerte):
        """La douleur 8/10 est correctement extraite."""
        rapport = engine.generer_rapport(dictee_alerte, patient_data)
        douleur = rapport["evaluation"].get("Confort douleur", "")
        assert "8" in douleur

    def test_medicament_detecte(self, engine, patient_data, dictee_alerte):
        """La morphine est détectée comme médicament."""
        rapport = engine.generer_rapport(dictee_alerte, patient_data)
        meds = rapport.get("medicaments", [])
        noms = " ".join(m.get("nom", "").lower() for m in meds)
        assert "morphine" in noms


class TestWorkflowMinimale:
    """Workflow avec dictée minimale — rapport incomplet."""

    def test_rapport_minimal_score_bas(self, engine, patient_data, dictee_minimale):
        """Une dictée minimale produit un score bas."""
        rapport = engine.generer_rapport(dictee_minimale, patient_data)
        score = engine.score_completude(rapport)

        # Score doit être inférieur à celui d'un rapport complet
        assert score["score"] < 80

    def test_rapport_minimal_validation_warnings(self, engine, patient_data, dictee_minimale):
        """Une dictée minimale génère des warnings de validation."""
        rapport = engine.generer_rapport(dictee_minimale, patient_data)
        est_valide, warnings = engine.valider_rapport(rapport)

        # Doit avoir des warnings (pas de signes vitaux, pas de soins)
        assert len(warnings) > 0

    def test_rapport_minimal_export_fonctionne(self, engine, patient_data, dictee_minimale):
        """Même un rapport minimal peut être exporté."""
        rapport = engine.generer_rapport(dictee_minimale, patient_data)
        texte = engine.exporter_texte_lisible(rapport)
        assert "Martin" in texte
        json_str = engine.exporter_json(rapport)
        assert json.loads(json_str) is not None


class TestWorkflowMultilingue:
    """Workflow en néerlandais."""

    def test_dictee_neerlandaise(self, engine):
        """Une dictée en néerlandais fonctionne."""
        patient_nl = {
            "nom": "Janssens",
            "prenom": "Pieter",
            "chambre": "305",
            "quart": "Nacht",
            "langue": "Nederlands",
            "type_rapport": "Verpleegkundig rapport",
        }
        dictee_nl = (
            "Patiënt Pieter Janssens kamer 305. "
            "Bloeddruk 120/80, pols 72 bpm, temperatuur 36.5, "
            "SpO2 98%. "
            "Wondzorg uitgevoerd. "
            "Paracetamol 1g IV toegediend. "
            "Standaard monitoring. "
            "Patiënt stabiel."
        )

        rapport = engine.generer_rapport(dictee_nl, patient_nl)

        assert rapport["patient"]["nom"] == "Janssens"
        assert rapport["patient"]["chambre"] == "305"
        sv = rapport["evaluation"]["Signes vitaux"]
        assert "Tension artérielle" in sv or "bloeddruk" in str(sv).lower()

    def test_dictee_neerlandaise_export(self, engine):
        """L'export fonctionne aussi en néerlandais."""
        patient_nl = {
            "nom": "Peeters",
            "prenom": "An",
            "chambre": "210",
            "quart": "Nacht",
            "langue": "Nederlands",
        }
        dictee_nl = "Patiënt stabiel. Bloeddruk 115/75. Pols 68. Wondzorg."

        rapport = engine.generer_rapport(dictee_nl, patient_nl)
        texte = engine.exporter_texte_lisible(rapport)
        assert "Peeters" in texte
        json_str = engine.exporter_json(rapport)
        assert json.loads(json_str)["patient"]["nom"] == "Peeters"


class TestLoggingIntegration:
    """Vérifie que le module de logging fonctionne dans le workflow."""

    def test_get_logger(self):
        """Le logger est accessible et fonctionnel."""
        from logging_config import get_logger
        logger = get_logger("test_e2e")
        assert logger.name == "nurselog.test_e2e"
        # Peut logger sans erreur
        logger.info("test message", extra={"patient_id": "P-001"})

    def test_audit_log(self):
        """L'audit trail enregistre les événements."""
        from logging_config import audit_log
        event_id = audit_log("rapport_cree", infirmier="Marie", patient="Jean", rapport_id="R-001")
        assert event_id  # UUID non vide

    def test_timed_context(self):
        """Le context manager timed fonctionne."""
        from logging_config import get_logger, timed
        logger = get_logger("test_timed")
        with timed("operation_teste", logger=logger):
            pass  # Opération simulée
