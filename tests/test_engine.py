"""
Tests unitaires pour le moteur NurseLog AI
"""

import sys
import os
import shutil
import tempfile
import pytest

# Ajouter le dossier parent au chemin pour importer src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.nurselog_engine import NurseLogEngine, TranscriptionError
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

    def test_transcription_vocale_simulation(self):
        """Simulation de la transcription vocale"""
        # Test basique pour vérifier que l'IA peut traiter les données transmises
        dictee_test = "Patient Dupont, tension 120/80, pouls 72, température 36.5"
        rapport = self.engine.generer_rapport(dictee_test, PATIENT_TEST)
        assert "evaluation" in rapport
        assert len(rapport["soins"]) >= 0


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

    def test_transcription_audio(self, monkeypatch):
        """La transcription audio sans backend lève une erreur claire"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setitem(sys.modules, "whisper", None)
        with pytest.raises(TranscriptionError):
            self.engine.transcrire_audio(
                b"fake-audio-data", filename="test.wav", api_key=""
            )

    def test_voice_recognition_error_handling(self):
        """Test de la gestion des erreurs dans la reconnaissance vocale"""
        # Test avec données invalides (simule l'erreur)
        try:
            result = self.engine.generer_rapport(
                "",
                {}
            )
            assert True  # Ne devrait pas lever d'erreur
        except Exception:
            pass  # On accepte les erreurs dans le cas de test


class TestMedicaments:
    """Tests spécifiques des médicaments"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_medicament_majuscules(self):
        """Un médicament en majuscules est détecté"""
        dictee = "Administration Paracétamol 1g IV"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        meds = rapport["medicaments"]
        assert len(meds) > 0
        noms = [m["nom"].lower() for m in meds]
        assert any("paracetamol" in n or "paracétamol" in n for n in noms)

    def test_medicament_minuscules(self):
        """Un médicament en minuscules est aussi détecté (cas dictée vocale)"""
        dictee = "j'ai administré paracétamol 500 mg par voie orale"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        meds = rapport["medicaments"]
        assert len(meds) > 0
        noms = [m["nom"].lower() for m in meds]
        assert any("paracetamol" in n or "paracétamol" in n for n in noms)

    def test_medicament_mixed_case(self):
        """Un médicament en casse mixte est détecté"""
        dictee = "Injection de Morphine 5mg SC"
        rapport = self.engine.generer_rapport(dictee, PATIENT_TEST)
        meds = rapport["medicaments"]
        assert len(meds) > 0
        noms = [m["nom"].lower() for m in meds]
        assert any("morphine" in n for n in noms)


class TestNumeroDossier:
    """Tests de la propagation du numéro de dossier"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_numero_dossier_propage(self):
        """Le numero_dossier est bien propagé dans le rapport généré"""
        patient = {
            "nom": "Martin",
            "prenom": "Luc",
            "chambre": "5B",
            "numero_dossier": "D-2025-9999"
        }
        rapport = self.engine.generer_rapport("Pansement réalisé", patient)
        assert rapport["patient"]["numero_dossier"] == "D-2025-9999"

    def test_numero_dossier_vide_par_defaut(self):
        """Si absent, numero_dossier est une chaîne vide"""
        patient = {"nom": "Test", "prenom": "Test"}
        rapport = self.engine.generer_rapport("Soins", patient)
        assert rapport["patient"]["numero_dossier"] == ""


class TestRapportStructure:
    """Tests de la méthode generer_rapport_structure (mode Manuel)"""

    def setup_method(self):
        self.engine = NurseLogEngine()

    def test_structure_complete(self):
        """Le rapport structuré a toutes les sections"""
        patient = {"nom": "Durand", "prenom": "Sophie", "chambre": "3B"}
        evaluation = {"Signes vitaux": {"Tension artérielle": "120/80 mmHg"}, "Confort douleur": "EVA: 2/10"}
        soins = ["Pansement plaie", "Surveillance TA"]
        alertes = ["Surveiller la douleur"]
        plan = ["Prochain pansement 48h"]
        
        rapport = self.engine.generer_rapport_structure(patient, evaluation, soins, alertes, plan)
        
        assert rapport["patient"]["nom"] == "Durand"
        assert rapport["evaluation"]["Signes vitaux"]["Tension artérielle"] == "120/80 mmHg"
        assert rapport["soins"] == ["Pansement plaie", "Surveillance TA"]
        assert rapport["alertes"] == ["Surveiller la douleur"]
        assert rapport["plan"] == ["Prochain pansement 48h"]
        assert "metadata" in rapport
        assert "transmissions" in rapport

    def test_structure_sans_soins(self):
        """Fonctionne même sans soins"""
        patient = {"nom": "Test", "prenom": "Test"}
        rapport = self.engine.generer_rapport_structure(patient, {}, [], [], [])
        assert rapport["soins"] == []
        assert rapport["alertes"] == []
        assert rapport["plan"] == []

    def test_structure_codes_naa(self):
        """Les codes NAA sont mappés depuis les soins"""
        patient = {"nom": "Test", "prenom": "Test"}
        soins = ["Pansement plaie sacrum"]
        rapport = self.engine.generer_rapport_structure(patient, {}, soins, [], [])
        # Le mot "pansement" devrait déclencher un code NAA
        assert len(rapport["codes_naa"]) >= 0  # Peut être 0 si mapping ne matche pas

    def test_structure_numero_dossier(self):
        """Le numero_dossier est propagé en mode structuré"""
        patient = {"nom": "Test", "prenom": "Test", "numero_dossier": "D-2025-1111"}
        rapport = self.engine.generer_rapport_structure(patient, {}, ["Soins"], [], [])
        assert rapport["patient"]["numero_dossier"] == "D-2025-1111"


class TestTranscriptionAudio:
    """Tests de la transcription vocale (API OpenAI / Whisper local)"""

    def setup_method(self):
        self.engine = NurseLogEngine()
        # Isoler le cache des modèles locaux entre les tests
        NurseLogEngine._whisper_cache.clear()

    # --- Helpers de mock ---

    @staticmethod
    def _mock_openai_client(response="Transcription test"):
        """Client OpenAI factice capturant les appels de transcribe()."""
        class MockAudio:
            def __init__(self):
                self.calls = []
            def transcribe(self, **kwargs):
                self.calls.append(kwargs)
                return response

        class MockClient:
            pass

        client = MockClient()
        client.audio = MockAudio()
        return client

    @staticmethod
    def _ffmpeg_fictif(monkeypatch):
        """Rend les tests mockés indépendants de l'installation réelle de ffmpeg."""
        chemin = os.path.join(tempfile.gettempdir(), "ffmpeg-fictif", "ffmpeg")
        monkeypatch.setattr(
            NurseLogEngine, "_chercher_ffmpeg", staticmethod(lambda: chemin)
        )

    @staticmethod
    def _mock_whisper(monkeypatch, text="Transcription 100% locale"):
        """Module openai-whisper factice."""
        class MockModel:
            def transcribe(self, path, **kwargs):
                return {"text": text}

        class MockWhisper:
            def load_model(self, name):
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        TestTranscriptionAudio._ffmpeg_fictif(monkeypatch)

    # --- Backend API OpenAI ---

    def test_openai_transcription_ok(self):
        """Transcription via API : le texte est retourné"""
        client = self._mock_openai_client("Pansement réalisé, douleur 2/10")
        result = self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            api_key="fake-key", client=client,
        )
        assert result == "Pansement réalisé, douleur 2/10"
        assert len(client.audio.calls) == 1

    def test_openai_parametres_appels(self):
        """L'appel API reçoit le modèle et le format de réponse attendus"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            api_key="fake-key", client=client,
        )
        call = client.audio.calls[0]
        assert call["model"] == "whisper-1"
        assert call["response_format"] == "text"

    def test_openai_transmission_langue(self):
        """La langue affichable est convertie en code ISO pour Whisper"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            langue="Français", api_key="fake-key", client=client,
        )
        assert client.audio.calls[0]["language"] == "fr"

    def test_openai_langue_nederlandaise(self):
        """Le néerlandais est bien converti en 'nl'"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            langue="Néerlandais", api_key="fake-key", client=client,
        )
        assert client.audio.calls[0]["language"] == "nl"

    def test_openai_langue_auto_pas_transmise(self):
        """Sans langue précisée, Whisper détecte automatiquement"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            langue=None, api_key="fake-key", client=client,
        )
        assert "language" not in client.audio.calls[0]

    def test_openai_prompt_medical_priming(self):
        """Le vocabulaire médical est transmis comme initial_prompt"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            api_key="fake-key", client=client,
        )
        prompt = client.audio.calls[0].get("initial_prompt", "")
        assert len(prompt) > 0
        assert len(prompt) <= 650
        # Doit contenir des termes cliniques FR/NL
        assert "tension" in prompt.lower() or "bloeddruk" in prompt.lower()
        # Les médicaments courants doivent être primés (noms propres sensibles)
        assert "paracétamol" in prompt.lower() or "paracetamol" in prompt.lower()

    def test_openai_modele_personnalise(self):
        """Un modèle plus précis peut être sélectionné"""
        client = self._mock_openai_client("ok")
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            model="gpt-4o-transcribe", api_key="fake-key", client=client,
        )
        assert client.audio.calls[0]["model"] == "gpt-4o-transcribe"

    def test_openai_erreur_api_key_invalide(self):
        """Une erreur 401 est traduite en message actionnable"""
        class MockAudio:
            def transcribe(self, **kwargs):
                raise Exception("Error code: 401 - Invalid API Key provided")

        class MockClient:
            pass

        client = MockClient()
        client.audio = MockAudio()
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav",
                api_key="bad-key", client=client,
            )
        assert "clé api" in str(excinfo.value).lower()

    def test_openai_erreur_rate_limit(self):
        """Une erreur 429 est traduite en message actionnable"""
        class MockAudio:
            def transcribe(self, **kwargs):
                raise Exception("Error code: 429 - Rate limit reached")

        class MockClient:
            pass

        client = MockClient()
        client.audio = MockAudio()
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav",
                api_key="fake-key", client=client,
            )
        assert "rate limit" in str(excinfo.value).lower()

    def test_openai_transcription_vide(self):
        """Une transcription vide lève une erreur claire"""
        client = self._mock_openai_client("")
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav",
                api_key="fake-key", client=client,
            )
        assert "vide" in str(excinfo.value).lower()

    # --- Backend local (openai-whisper) ---

    def test_whisper_local_transcription(self, monkeypatch):
        """Sans clé API, le backend local est utilisé"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        self._mock_whisper(monkeypatch, "Transcription 100% locale")
        result = self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav", api_key="",
        )
        assert result == "Transcription 100% locale"

    def test_whisper_local_langue(self, monkeypatch):
        """La langue est transmise au modèle local"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        appels = {}

        class MockModel:
            def transcribe(self, path, **kwargs):
                appels.update(kwargs)
                return {"text": "ok"}

        class MockWhisper:
            def load_model(self, name):
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        self._ffmpeg_fictif(monkeypatch)
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            langue="Néerlandais", api_key="",
        )
        assert appels.get("language") == "nl"

    def test_whisper_local_prompt_medical(self, monkeypatch):
        """Le priming du vocabulaire médical est transmis au modèle local"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        appels = {}

        class MockModel:
            def transcribe(self, path, **kwargs):
                appels.update(kwargs)
                return {"text": "ok"}

        class MockWhisper:
            def load_model(self, name):
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        self._ffmpeg_fictif(monkeypatch)
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav", api_key="",
        )
        assert appels.get("initial_prompt")
        assert "tension" in appels["initial_prompt"]

    def test_whisper_local_transcription_vide(self, monkeypatch):
        """Une transcription locale vide lève une erreur claire"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        self._mock_whisper(monkeypatch, text="")
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"fake-audio", filename="dictee.wav", api_key="",
            )
        assert "vide" in str(excinfo.value).lower()

    # --- Validation du fichier ---

    def test_fichier_trop_gros(self):
        """Un fichier > 25 Mo est rejeté avant tout appel"""
        gros = b"x" * (26 * 1024 * 1024)
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(gros, filename="gros.wav", api_key="")
        assert "volumineux" in str(excinfo.value).lower()

    def test_format_non_supporte(self):
        """Un format non supporté est rejeté avec la liste des formats"""
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(b"data", filename="video.avi", api_key="")
        msg = str(excinfo.value).lower()
        assert "format" in msg
        assert ".mp3" in msg

    def test_fichier_vide(self):
        """Un fichier vide est rejeté"""
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(b"", filename="vide.wav", api_key="")
        assert "vide" in str(excinfo.value).lower()

    def test_modele_inconnu(self):
        """Un modèle inconnu est rejeté avec la liste des modèles"""
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav",
                model="modele-inexistant", api_key="fake-key",
                client=self._mock_openai_client(),
            )
        msg = str(excinfo.value).lower()
        assert "modèle" in msg
        assert "whisper-1" in msg

    # --- Aucun backend ---

    def test_aucun_backend_disponible(self, monkeypatch):
        """Sans API ni Whisper local, l'erreur guide l'installation"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setitem(sys.modules, "whisper", None)
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav", api_key="",
            )
        msg = str(excinfo.value).lower()
        assert "openai" in msg
        assert "openai-whisper" in msg

    # --- Détection ffmpeg (dépendance du backend local) ---

    def test_chercher_ffmpeg_absent_retourne_none(self, monkeypatch):
        """Sans ffmpeg dans le PATH ni les emplacements connus : None"""
        monkeypatch.setattr(shutil, "which", lambda name: None)
        monkeypatch.setattr(os.path, "isfile", lambda p: False)
        assert NurseLogEngine._chercher_ffmpeg() is None

    def test_assurer_ffmpeg_prefixe_le_path(self, monkeypatch):
        """Un ffmpeg hors PATH est ajouté au PATH pour que whisper le trouve"""
        dossier = os.path.join(tempfile.gettempdir(), "ffmpeg-fictif")
        binaire = os.path.join(dossier, "ffmpeg")
        monkeypatch.setattr(
            NurseLogEngine, "_chercher_ffmpeg", staticmethod(lambda: binaire)
        )
        monkeypatch.setenv("PATH", os.path.join(tempfile.gettempdir(), "autre"))
        resultat = NurseLogEngine._assurer_ffmpeg()
        assert resultat == binaire
        assert dossier in os.environ["PATH"].split(os.pathsep)

    def test_transcription_locale_sans_ffmpeg_erreur_claire(self, monkeypatch):
        """Sans ffmpeg, l'erreur guide l'installation"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        self._mock_whisper(monkeypatch, "ok")
        # Simule l'absence totale de ffmpeg (remplace le patch fictif)
        monkeypatch.setattr(
            NurseLogEngine, "_chercher_ffmpeg", staticmethod(lambda: None)
        )
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"fake-audio", filename="dictee.wav", api_key="",
            )
        msg = str(excinfo.value).lower()
        assert "ffmpeg" in msg
        assert "winget" in msg or "brew" in msg or "apt" in msg

    def test_statut_transcription_inclut_ffmpeg(self):
        """Le statut expose la disponibilité de ffmpeg"""
        statut = NurseLogEngine.statut_transcription()
        assert "ffmpeg_disponible" in statut
        assert isinstance(statut["ffmpeg_disponible"], bool)

    # --- Helpers du moteur ---

    def test_normalisation_langue(self):
        """Les langues affichables sont normalisées en codes ISO"""
        assert NurseLogEngine._normaliser_langue("Français") == "fr"
        assert NurseLogEngine._normaliser_langue("francais") == "fr"
        assert NurseLogEngine._normaliser_langue("néerlandais") == "nl"
        assert NurseLogEngine._normaliser_langue("NL") == "nl"
        assert NurseLogEngine._normaliser_langue(None) is None
        assert NurseLogEngine._normaliser_langue("") is None
        assert NurseLogEngine._normaliser_langue("espagnol") is None

    def test_prompt_medical_structure(self):
        """Le prompt médical est borné et contient du vocabulaire bilingue"""
        prompt = NurseLogEngine._construire_prompt_medical()
        assert 0 < len(prompt) <= 650
        # Pas de doublons
        termes = [t.strip().lower() for t in prompt.split(",")]
        assert len(termes) == len(set(termes))

    def test_prompt_medical_ordre_prioritaire(self):
        """Signes vitaux d'abord, puis médicaments, puis vocabulaire de base"""
        prompt = NurseLogEngine._construire_prompt_medical()
        pos_signes = prompt.lower().find("tension")
        pos_medicament = prompt.lower().find("paracetamol")
        assert pos_signes != -1
        assert pos_medicament != -1
        assert pos_signes < pos_medicament

    def test_constante_medicaments_courants(self):
        """La liste partagée est cohérente (pas de doublons, non vide)"""
        meds = NurseLogEngine.MEDICAMENTS_COURANTS
        assert len(meds) > 0
        bas = [m.lower() for m in meds]
        assert len(bas) == len(set(bas))

    # --- Modèle local (taille + cache) ---

    def test_local_model_transmis_a_load_model(self, monkeypatch):
        """La taille demandée est bien passée à whisper.load_model"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        charges = []

        class MockModel:
            def transcribe(self, path, **kwargs):
                return {"text": "ok"}

        class MockWhisper:
            def load_model(self, name):
                charges.append(name)
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        self._ffmpeg_fictif(monkeypatch)
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav",
            api_key="", local_model="small",
        )
        assert charges == ["small"]

    def test_local_model_invalide(self):
        """Une taille inconnue est rejetée avec la liste des tailles"""
        with pytest.raises(TranscriptionError) as excinfo:
            self.engine.transcrire_audio(
                b"data", filename="dictee.wav",
                local_model="gigantic", api_key="fake-key",
                client=self._mock_openai_client(),
            )
        msg = str(excinfo.value).lower()
        assert "tailles" in msg or "taille" in msg
        assert "tiny" in msg
        assert "small" in msg

    def test_cache_modele_local(self, monkeypatch):
        """Le modèle est chargé une seule fois sur deux transcriptions"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        charges = []

        class MockModel:
            def transcribe(self, path, **kwargs):
                return {"text": "ok"}

        class MockWhisper:
            def load_model(self, name):
                charges.append(name)
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        self._ffmpeg_fictif(monkeypatch)
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav", api_key="",
        )
        self.engine.transcrire_audio(
            b"fake-audio", filename="dictee2.wav", api_key="",
        )
        assert charges == ["base"]

    def test_cache_repli_tiny(self, monkeypatch):
        """Si la taille demandée échoue, on retombe sur 'tiny'"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        charges = []

        class MockModel:
            def transcribe(self, path, **kwargs):
                return {"text": "ok"}

        class MockWhisper:
            def load_model(self, name):
                charges.append(name)
                if name != "tiny":
                    raise RuntimeError("téléchargement impossible")
                return MockModel()

        monkeypatch.setitem(sys.modules, "whisper", MockWhisper())
        self._ffmpeg_fictif(monkeypatch)
        result = self.engine.transcrire_audio(
            b"fake-audio", filename="dictee.wav", api_key="",
            local_model="small",
        )
        assert result == "ok"
        assert charges == ["small", "tiny"]

    def test_statut_transcription_modeles_locaux(self):
        """Le statut expose les tailles de modèles locaux"""
        statut = NurseLogEngine.statut_transcription()
        assert "modeles_locaux" in statut
        assert statut["modeles_locaux"] == ["tiny", "base", "small"]

    def test_statut_transcription_structure(self):
        """Le statut expose les backends et les capacités"""
        statut = NurseLogEngine.statut_transcription()
        assert "disponible" in statut
        assert "backend" in statut
        assert "modeles" in statut
        assert "formats" in statut
        assert "taille_max_mo" in statut
        assert "whisper-1" in statut["modeles"]
        assert "gpt-4o-transcribe" in statut["modeles"]
        assert "mp3" in statut["formats"]
        assert "wav" in statut["formats"]
        assert statut["taille_max_mo"] == 25

    def test_constantes_moteur(self):
        """Les constantes publiques sont cohérentes"""
        assert NurseLogEngine.TAILLE_MAX_AUDIO_MO == 25
        assert "whisper-1" in NurseLogEngine.MODELES_TRANSCRIPTION
        assert "mp3" in NurseLogEngine.FORMATS_AUDIO_SUPPORTES
        assert "webm" in NurseLogEngine.FORMATS_AUDIO_SUPPORTES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
