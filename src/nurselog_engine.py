"""
NurseLog AI - Moteur d'IA pour Documentation Infirmière
========================================================
Prototype MVP — Moteur de traitement textuel pour la génération
de rapports de soins structurés conformes aux standards belges.

Architecture :
  - Analyse textuelle (regex + mots-clés) simulant un LLM
  - Extraction des signes vitaux, soins, alertes, plan
  - Mapping automatique des codes NAA belges
  - Structuration selon les templates KCE/eHealth

En production : remplacement par LLM (Llama 3, Mistral, ou Claude)
avec RAG sur la terminologie médicale belge.
"""

import datetime
import importlib.util
import json
import os
import re
import shutil
import tempfile
from typing import Any

from templates import (
    CODES_NAA_RECONNAISSANCE,
    RAPPORT_TEMPLATE,
    VOCABULAIRE,
)


class TranscriptionError(Exception):
    """
    Erreur lors de la transcription vocale.

    Le message est toujours actionnable pour l'utilisateur
    (fichier invalide, backend manquant, clé API, ...).
    """


class NurseLogEngine:
    """
    Moteur principal de NurseLog AI.

    Transforme une dictée textuelle libre en rapport de soins structuré,
    conforme aux standards belges (KCE, eHealth, NAA).
    """

    def __init__(self):
        self.version = "0.1.0"
        self.langue_par_defaut = "Français"
        self._initialiser_modeles_extraction()

        # Pour les futures améliorations avec LLM
        self.llm_available = importlib.util.find_spec("transformers") is not None

    # ========================================================================
    # INITIALISATION
    # ========================================================================

    def _initialiser_modeles_extraction(self):
        """Compile les expressions régulières pour l'extraction de données."""
        self.regex_signes_vitaux = {
            "tension": re.compile(
                r'(?:tension|TA|bloeddruk)\s*(?:artérielle)?\s*(?:de\s*)?'
                r'(?:=\s*|:\s*)?(\d{2,3})\s*/\s*(\d{2,3})',
                re.IGNORECASE
            ),
            "pouls": re.compile(
                r'(?:pouls|fréquence\s*cardiaque|FC|pols)\s*(?:de\s*)?'
                r'(?:=\s*|:\s*)?(\d{2,3})\s*(?:bpm)?',
                re.IGNORECASE
            ),
            "temperature": re.compile(
                r'(?:température|T°|fièvre|temperatuur)\s*(?:de\s*)?'
                r'(?:=\s*|:\s*)?(\d+(?:\.\d+)?)\s*(?:°C|degrees)?',
                re.IGNORECASE
            ),
            "spo2": re.compile(
                r'(?:SpO2|saturation|oxygénation|saturatie)\s*(?:de\s*)?'
                r'(?:=\s*|:\s*)?(\d{2,3})\s*(?:%)?',
                re.IGNORECASE
            ),
            "douleur": re.compile(
                r'(?:douleur|EVA|pijn)\s*(?:=\s*|:\s*)?(\d)\s*(?:/10)?',
                re.IGNORECASE
            ),
            "glycemie": re.compile(
                r'(?:glycémie|glycémie\s*capillaire|bloedsuiker)\s*(?:=\s*|:\s*)?'
                r'(\d+(?:\.\d+)?)\s*(?:g/L|mmol/L)?',
                re.IGNORECASE
            ),
            "respiration": re.compile(
                r'(?:respiration|fréquence\s*respiratoire|FR|respiratie)\s*(?:=\s*|:\s*)?'
                r'(\d{2,3})\s*(?:irpm)?',
                re.IGNORECASE
            ),
        }

        self.regex_dimensions_plaie = re.compile(
            r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)'
            r'(?:\s*[xX×]\s*(\d+(?:\.\d+)?))?',
            re.IGNORECASE
        )

        self.regex_code_naa = re.compile(
            r'(?:code|NAA)\s*(\d{2}\.\d{3})',
            re.IGNORECASE
        )

        self.regex_medicament = re.compile(
            r'([A-Za-zàâéèêîôûùçñ]{3,}(?:\s+[A-Za-zàâéèêîôûùçñ]+)*)'
            r'\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|UI|µg|microg)',
            re.IGNORECASE
        )

    # ========================================================================
    # MÉTHODE PRINCIPALE
    # ========================================================================

    def generer_rapport(self, dictee: str, patient_data: dict[str, Any]) -> dict[str, Any]:
        """
        Génère un rapport structuré à partir d'une dictée textuelle.

        Args:
            dictee: Texte libre dicté par l'infirmier(e)
            patient_data: Données du patient (nom, chambre, etc.)

        Returns:
            Dictionnaire structuré conforme au template belge
        """
        # Initialiser le rapport depuis le template
        rapport = self._copier_template()

        # Remplir les métadonnées
        self._remplir_metadonnees(rapport, patient_data)

        # Remplir les infos patient
        self._remplir_patient(rapport, patient_data)

        # Extraire les signes vitaux
        rapport["evaluation"] = self._extraire_signes_vitaux(dictee)

        # Extraire les soins réalisés
        rapport["soins"] = self._extraire_soins(dictee)

        # Extraire les alertes
        rapport["alertes"] = self._extraire_alertes(dictee)

        # Extraire le plan de soins
        rapport["plan"] = self._extraire_plan(dictee)

        # Mapper les codes NAA
        rapport["codes_naa"] = self._mapper_codes_naa(dictee)

        # Extraire les médicaments
        rapport["medicaments"] = self._extraire_medicaments(dictee)

        # Générer les transmissions SBAr
        rapport["transmissions"] = self._generer_transmissions(dictee, rapport)

        # Conserver la dictée originale (audit + vérifications croisées)
        rapport["dictee_originale"] = dictee

        return rapport

    # ========================================================================
    # REMPLISSAGE MÉTADONNÉES & PATIENT
    # ========================================================================

    def _copier_template(self) -> dict:
        """Crée une copie profonde du template de rapport."""
        return json.loads(json.dumps(RAPPORT_TEMPLATE))

    def _remplir_metadonnees(self, rapport: dict, patient_data: dict):
        """Remplit les métadonnées du rapport."""
        maintenant = datetime.datetime.now()
        rapport["metadata"]["date"] = maintenant.strftime("%Y-%m-%d")
        rapport["metadata"]["heure"] = maintenant.strftime("%H:%M")
        rapport["metadata"]["quart"] = patient_data.get("quart", "")
        rapport["metadata"]["type_rapport"] = patient_data.get("type_rapport", "Rapport de soins standard")
        rapport["metadata"]["langue"] = patient_data.get("langue", "Français")

    def _remplir_patient(self, rapport: dict, patient_data: dict):
        """Remplit les informations patient."""
        rapport["patient"]["nom"] = patient_data.get("nom", "")
        rapport["patient"]["prenom"] = patient_data.get("prenom", "")
        rapport["patient"]["date_naissance"] = patient_data.get("date_naissance", "")
        rapport["patient"]["chambre"] = patient_data.get("chambre", "")
        rapport["patient"]["numero_dossier"] = patient_data.get("numero_dossier", "")

    # ========================================================================
    # EXTRACTION DES SIGNES VITAUX
    # ========================================================================

    def _extraire_signes_vitaux(self, texte: str) -> dict:
        """Extrait et structure les signes vitaux du texte."""
        evaluation = {
            "Signes vitaux": {},
            "Confort douleur": "",
            "État général": "",
            "Nutrition hydratation": "",
            "Mobilité": "",
            "Pele muqueuses": "",
            "Eliminations": "",
            "État psychologique": "",
        }

        # Tension artérielle
        match = self.regex_signes_vitaux["tension"].search(texte)
        if match:
            sys = int(match.group(1))
            dias = int(match.group(2))
            evaluation["Signes vitaux"]["Tension artérielle"] = f"{sys}/{dias} mmHg"
            if sys > 160 or dias > 100:
                evaluation["Signes vitaux"]["TA"] = "⚠️ Hypertension"
            elif sys < 90 or dias < 60:
                evaluation["Signes vitaux"]["TA"] = "⚠️ Hypotension"
            else:
                evaluation["Signes vitaux"]["TA"] = "✅ Normale"

        # Pouls
        match = self.regex_signes_vitaux["pouls"].search(texte)
        if match:
            fc = int(match.group(1))
            evaluation["Signes vitaux"]["Pouls"] = f"{fc} bpm"
            if fc > 100:
                evaluation["Signes vitaux"]["FC"] = "⚠️ Tachycardie"
            elif fc < 60:
                evaluation["Signes vitaux"]["FC"] = "⚠️ Bradycardie"
            else:
                evaluation["Signes vitaux"]["FC"] = "✅ Normal"

        # Température
        match = self.regex_signes_vitaux["temperature"].search(texte)
        if match:
            temp = float(match.group(1).replace(',', '.'))
            evaluation["Signes vitaux"]["Température"] = f"{temp}°C"
            if temp >= 38.0:
                evaluation["Signes vitaux"]["T°"] = "⚠️ Fièvre"
            elif temp < 36.0:
                evaluation["Signes vitaux"]["T°"] = "⚠️ Hypothermie"
            else:
                evaluation["Signes vitaux"]["T°"] = "✅ Normale"

        # SpO2
        match = self.regex_signes_vitaux["spo2"].search(texte)
        if match:
            spo2 = int(match.group(1))
            evaluation["Signes vitaux"]["SpO2"] = f"{spo2}%"
            if spo2 < 95:
                evaluation["Signes vitaux"]["Sat"] = "⚠️ Hypoxémie"
            else:
                evaluation["Signes vitaux"]["Sat"] = "✅ Normale"

        # Douleur
        match = self.regex_signes_vitaux["douleur"].search(texte)
        if match:
            douleur = int(match.group(1))
            evaluation["Confort douleur"] = f"EVA: {douleur}/10"
            if douleur >= 7:
                evaluation["Confort douleur"] += " — ⚠️ Douleur sévère"
            elif douleur >= 4:
                evaluation["Confort douleur"] += " — ⚠️ Douleur modérée"
            elif douleur >= 1:
                evaluation["Confort douleur"] += " — Légère"
            else:
                evaluation["Confort douleur"] += " — ✅ Aucune"

        # Glycémie
        match = self.regex_signes_vitaux["glycemie"].search(texte)
        if match:
            glyc = float(match.group(1).replace(',', '.'))
            evaluation["Signes vitaux"]["Glycémie"] = f"{glyc} g/L"
            if glyc > 1.4:
                evaluation["Signes vitaux"]["Glycémie"] += " — ⚠️ Hyperglycémie"
            elif glyc < 0.6:
                evaluation["Signes vitaux"]["Glycémie"] += " — ⚠️ Hypoglycémie"
            else:
                evaluation["Signes vitaux"]["Glycémie"] += " — ✅ Normale"

        # Respiration
        match = self.regex_signes_vitaux["respiration"].search(texte)
        if match:
            fr = int(match.group(1))
            evaluation["Signes vitaux"]["Fréquence respiratoire"] = f"{fr} irpm"

        # Analyse sémantique pour état général
        texte_lower = texte.lower()

        # État général
        etat_general_indicateurs = []
        if any(w in texte_lower for w in ["conscient", "eveille", "eveill", "alerte", "orienté", "oriente"]):
            etat_general_indicateurs.append("Patient conscient et éveillé")
        if any(w in texte_lower for w in ["somnolent", "endormi", "difficulté à rester éveillé"]):
            etat_general_indicateurs.append("Somnolence observée")
        if any(w in texte_lower for w in ["agité", "agitation", "désorienté", "desoriente"]):
            etat_general_indicateurs.append("Agitation / désorientation notée")
        if any(w in texte_lower for w in ["stable", "amélioration", "amelioration", "bon état", "bon etat"]):
            etat_general_indicateurs.append("État stable / en amélioration")
        if any(w in texte_lower for w in ["dégradation", "detérioration", "deterioration", "aggravation"]):
            etat_general_indicateurs.append("⚠️ Dégradation de l'état général")

        if etat_general_indicateurs:
            evaluation["État général"] = ". ".join(etat_general_indicateurs)

        # Nutrition / Hydratation
        nutrition_indicateurs = []
        if any(w in texte_lower for w in ["a mangé", "a mange", "bonne alimentation", "a bien mangé", "a bien mange"]):
            nutrition_indicateurs.append("Alimentation satisfaisante")
        if any(w in texte_lower for w in ["n'a pas mangé", "na pas mange", "mauvais appétit", "anorexie"]):
            nutrition_indicateurs.append("⚠️ Mauvais appétit / anorexie")
        # Chercher spécifiquement le % dans le contexte de l'alimentation
        pourcentage_mange = re.search(
            r'(?:mangé|mange|assiette|repas|plat|consommé|consomme)\s*(\d+)%',
            texte, re.IGNORECASE
        )
        if not pourcentage_mange:
            # Fallback: chercher % proche de mots liés à la nourriture
            pourcentage_mange = re.search(
                r'(?:midi|soir|matin|déjeuner|dejeûner|diner|petit\s*déjeuner|repas)\s*(?:\w+\s*)?(\d+)%',
                texte, re.IGNORECASE
            )
        if pourcentage_mange:
            pct = int(pourcentage_mange.group(1))
            nutrition_indicateurs.append(f"Assiette: {pct}% consommé(e)")
            if pct < 50:
                nutrition_indicateurs.append("⚠️ Consommation insuffisante")
        if any(w in texte_lower for w in ["a bu", "hydratation", "boisson"]):
            nutrition_indicateurs.append("Hydratation surveillée")
        if nutrition_indicateurs:
            evaluation["Nutrition hydratation"] = ". ".join(nutrition_indicateurs)

        # Mobilité
        mobilite_indicateurs = []
        if any(w in texte_lower for w in ["ambulant", "se déplace", "mobilisation", "marche"]):
            mobilite_indicateurs.append("Patient ambulant / mobilisé")
        if any(w in texte_lower for w in ["alité", "alite", "couché", "couche", "non ambulant", "lit"]):
            mobilite_indicateurs.append("Patient alité")
        if any(w in texte_lower for w in ["fauteuil", "chaise", "déambulateur", "canne"]):
            mobilite_indicateurs.append("Aide à la marche utilisée")
        if mobilite_indicateurs:
            evaluation["Mobilité"] = ". ".join(mobilite_indicateurs)

        # Eliminations
        elim_indicateurs = []
        if any(w in texte_lower for w in ["diabète", "diabete", "miction", "urine", "urines"]):
            elim_indicateurs.append("Eliminations urinaires surveillées")
        if any(w in texte_lower for w in ["defécation", "defecation", "transit", "selles"]):
            elim_indicateurs.append("Transit surveillé")
        if any(w in texte_lower for w in ["sonde urinaire", "sonde", "cathéter urinaire", "catheter urinaire"]):
            elim_indicateurs.append("Sonde urinaire en place")
        if elim_indicateurs:
            evaluation["Eliminations"] = ". ".join(elim_indicateurs)

        return evaluation

    # ========================================================================
    # EXTRACTION DES SOINS
    # ========================================================================

    def _extraire_soins(self, texte: str) -> list[str]:
        """Extrait la liste des soins réalisés à partir du texte."""
        soins = []
        texte_lower = texte.lower()

        # Soins standard avec phrases structurées
        # Ordre important : motifs plus spécifiques d'abord pour éviter les doublons
        soins_mapping = [
            ("changement de pansement", "Changement de pansement effectué"),
            ("pansement", "Pansement réalisé"),
            ("injection intramusculaire", "Injection IM réalisée"),
            ("injection sous-cutanée", "Injection SC/SQ réalisée"),
            ("injection", "Injection administrée"),
            ("perfusion", "Perfusion en cours"),
            ("voies veineuses", "Voies veineuses vérifiées"),
            ("cathéter", "Cathéter vérifié"),
            ("sonde urinaire", "Sonde urinaire vérifiée"),
            ("sonde", "Sonde vérifiée / entretenue"),
            ("aspiration", "Aspiration réalisée"),
            ("positionnement", "Repositionnement effectué"),
            ("retournement", "Retournement réalisé"),
            ("mobilisation", "Mobilisation du patient"),
            ("toilette", "Soins d'hygiène/toilette réalisés"),
            ("soins d'hygiène", "Soins d'hygiène réalisés"),
            ("éducation", "Éducation thérapeutique dispensée"),
            ("glycémie", "Glycémie mesurée"),
            # ---- Néerlandais (public cible NL) ----
            ("wondverzorging", "Pansement / soins de plaie (wondverzorging)"),
            ("wond", "Soins de plaie (wond)"),
            ("injectie", "Injection administrée (injectie)"),
            ("infuusie", "Perfusion en cours (infuusie)"),
            ("suigen", "Aspiration réalisée (suigen)"),
            ("hygiëne", "Soins d'hygiène réalisés (hygiëne)"),
            ("bloedsuiker", "Glycémie mesurée (bloedsuiker)"),
            ("wondverpleging", "Pansement / soins de plaie (wondverpleging)"),
            ("wondafdekking", "Changement de pansement (wondafdekking)"),
            ("inwendig", "Injection IM réalisée (inwendig)"),
            ("onderhuid", "Injection SC réalisée (onderhuid)"),
            ("infuus", "Perfusion en cours (infuus)"),
            ("catheter", "Cathéter vérifié (catheter)"),
            ("cathéter", "Cathéter vérifié"),
            ("sonde", "Sonde vérifiée / entretenue"),
            ("aspiratie", "Aspiration réalisée (aspiratie)"),
            ("herpositioneren", "Repositionnement effectué (herpositioneren)"),
            ("mobilisatie", "Mobilisation du patient (mobilisatie)"),
            ("persoonlijke verzorging", "Soins d'hygiène réalisés (persoonlijke verzorging)"),
            ("hygiëne", "Soins d'hygiène réalisés (hygiëne)"),
            ("voeding", "Nutrition / hydratation évaluée (voeding)"),
            ("hydratatie", "Hydratation évaluée (hydratatie)"),
            ("pijnmeting", "Évaluation douleur réalisée (pijnmeting)"),
            ("pijn", "Évaluation douleur (pijn)"),
            ("bloeddruk", "Tension artérielle mesurée (bloeddruk)"),
            ("hartslag", "Fréquence cardiaque mesurée (hartslag)"),
            ("ademhaling", "Fréquence respiratoire mesurée (ademhaling)"),
            ("temperatuur", "Température mesurée (temperatuur)"),
            ("zuurstof", "Oxygénation / SpO2 vérifiée (zuurstof)"),
            ("oxygen", "Oxygénation / SpO2 vérifiée (oxygen)"),
            ("wond", "Soins de plaie (wond)"),
            ("escare", "Soins escarre réalisés (escare)"),
            ("decubitus", "Soins escarre réalisés (decubitus)"),
            ("wond", "Soins de plaie (wond)"),
        ]

        # Tracker des motifs déjà détectés pour éviter doublons
        motifs_detectes = set()
        for motif, description in soins_mapping:
            if motif in texte_lower:
                # Vérifier qu'un motif plus spécifique n'a pas déjà été détecté
                motif_doublonne = False
                for m_prev in motifs_detectes:
                    if motif in m_prev or m_prev in motif:
                        motif_doublonne = True
                        break
                if not motif_doublonne:
                    motifs_detectes.add(motif)
                    # Enrichir avec des détails si présents
                    soin_enrichi = self._enrichir_soin(description, texte, motif)
                    if soin_enrichi not in soins:
                        soins.append(soin_enrichi)

        # Dimensions de plaie
        match_plaie = self.regex_dimensions_plaie.search(texte)
        if match_plaie:
            longueur = match_plaie.group(1)
            largeur = match_plaie.group(2)
            profondeur = match_plaie.group(3) if match_plaie.group(3) else "N/A"
            if f"Plaie mesurée: {longueur} x {largeur} x {profondeur} cm" not in soins:
                soins.append(f"Plaie mesurée: {longueur} x {largeur} x {profondeur} cm")

        # Si aucun soin détecté, utiliser le texte brut comme fallback
        if not soins:
            phrases = self._extraire_phrases_soins(texte)
            soins.extend(phrases)

        return soins

    def _enrichir_soin(self, description: str, texte: str, motif: str) -> str:
        """Enrichit un soin avec des détails extraits du contexte."""
        texte_lower = texte.lower()

        enrichissements = {
            "propre": " — plaie propre, bonne évolution",
            "sale": " — plaie à nettoyer",
            "granulation": " — granulations présentes",
            "bonne évolution": " — bonne évolution",
            "mauvaise évolution": " — ⚠️ mauvaise évolution",
            "douleur 0": " — sans douleur",
            "tolère bien": " — bien toléré",
            "mal toléré": " — ⚠️ mal toléré",
        }

        for indicateur, ajout in enrichissements.items():
            if indicateur in texte_lower:
                return description + ajout

        return description

    def _extraire_phrases_soins(self, texte: str) -> list[str]:
        """Extrait les phrases descriptives comme fallback."""
        phrases = []
        # Séparer par ponctuation principale
        segments = re.split(r'[.;\n]+', texte)
        for segment in segments:
            segment = segment.strip()
            if 20 < len(segment) < 200:
                # Ne garder que les segments qui décrivent des actions
                mots_action = ["réalisé", "effectué", "fait", "administré", "posé",
                             "vérifié", "surveillé", "observé", "noté", "changé"]
                if any(mot in segment.lower() for mot in mots_action):
                    phrases.append(segment)
        return phrases

    # ========================================================================
    # RECONNAISSANCE VOCALE (Whisper API / Whisper local)
    # ========================================================================

    # Formats audio acceptés par l'API OpenAI Whisper
    FORMATS_AUDIO_SUPPORTES = ("mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac")

    # Limite de taille des fichiers audio (OpenAI : 25 Mo)
    TAILLE_MAX_AUDIO_MO = 25

    # Modèles de transcription disponibles (API OpenAI)
    MODELES_TRANSCRIPTION = (
        "whisper-1",
        "gpt-4o-mini-transcribe",
        "gpt-4o-transcribe",
    )

    # Tailles de modèles Whisper local (openai-whisper)
    # tiny : le plus rapide (~39 Mo) — base : équilibré (~142 Mo) — small : le plus précis (~466 Mo)
    MODELES_LOCAUX = ("tiny", "base", "small")

    # Cache des modèles Whisper locaux chargés (évite de recharger à chaque transcription)
    _whisper_cache: dict[str, Any] = {}

    # Médicaments courants en soins infirmiers (FR + NL), par classe thérapeutique,
    # les plus fréquents en premier. Utilisé à la fois pour le priming de la
    # transcription (initial_prompt) et l'extraction de médicaments dans le texte.
    MEDICAMENTS_COURANTS = (
        # Antalgiques / anti-inflammatoires
        "paracétamol", "paracetamol", "ibuprofène", "ibuprofen",
        "diclofénac", "diclofenac", "kétoprofène", "ketoprofen",
        "morphine", "fentanyl", "tramadol", "codeïne", "codeine",
        "oxycodone", "buprenorphine", "naloxone", "spasfon",
        # Anxiolytiques / sédatifs
        "diazépam", "diazepam", "midazolam",
        # Antibiotiques
        "amoxicilline", "amoxiciline", "azithromycine",
        "ciprofloxacine", "levofloxacine", "nitrofurantoïne", "nitrofurantoin",
        # Anticoagulants / antiagrégants
        "heparine", "warfarine", "clopidogrel", "aspirine",
        "enoxaparine", "dalteparine", "rivaroxaban", "apixaban", "dabigatran",
        # Diabète
        "insuline", "glargine", "asparte", "lispro",
        "metformine", "glibenclamide", "glimepiride", "sitagliptine",
        "empagliflozine", "dapagliflozine",
        # Gastro-entérologie
        "oméprazole", "omeprazole", "omeprazol", "pantoprazole", "ranitidine",
        # Cardio-vasculaire
        "sildenafil", "tadalafil", "simvastatine", "atorvastatine",
        "rosuvastatine", "lisinopril", "ramipril", "perindopril",
        "amlodipine", "bisoprolol", "metoprolol", "atenolol",
        "furosemide", "spironolactone", "hydrochlorothiazide",
        # Corticoïdes
        "prednisolone", "prednisone", "cortisone", "cortison",
    )

    def transcrire_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        langue: str | None = None,
        model: str = "whisper-1",
        local_model: str = "base",
        api_key: str | None = None,
        client: Any | None = None,
        timeout: int = 120,
    ) -> str:
        """
        Transcrit un fichier audio en texte (dictée de soins).

        Deux backends, dans cet ordre (RGPD : local d'abord) :
          1. **Whisper local** (package `openai-whisper`) — 100% local,
             aucune donnée ne quitte la machine (principe local-first / RGPD).
          2. **API OpenAI Whisper** — si `api_key` est fournie et le package
             `openai` est installé (transfert de l'audio hors machine ;
             voir section RGPD du README).

        Forcer un backend : `NURSELOG_TRANSCRIPTION_BACKEND=openai|local`.

        Args:
            audio_data: Contenu binaire du fichier audio.
            filename: Nom du fichier (sert à détecter le format).
            langue: "fr", "nl" ou None pour détection automatique.
            model: Modèle de transcription (API OpenAI uniquement).
            local_model: Taille du modèle Whisper local ("tiny", "base", "small").
            api_key: Clé API OpenAI (sinon : os.environ["OPENAI_API_KEY"]).
            client: Client OpenAI injectable (principalement pour les tests).
            timeout: Timeout de l'appel API en secondes.

        Returns:
            Le texte transcrit.

        Raises:
            TranscriptionError: Si le fichier est invalide, trop volumineux,
                ou si aucun backend de transcription n'est disponible.
        """
        # --- Validation du fichier -----------------------------------------
        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        if ext not in self.FORMATS_AUDIO_SUPPORTES:
            formats = ", ".join(f".{f}" for f in self.FORMATS_AUDIO_SUPPORTES)
            raise TranscriptionError(
                f"Format audio non supporté : .{ext or 'inconnu'}. "
                f"Formats acceptés : {formats}"
            )

        taille_mo = len(audio_data) / (1024 * 1024)
        if taille_mo > self.TAILLE_MAX_AUDIO_MO:
            raise TranscriptionError(
                f"Fichier audio trop volumineux ({taille_mo:.1f} Mo). "
                f"Limite : {self.TAILLE_MAX_AUDIO_MO} Mo. "
                "Découpez l'enregistrement en plusieurs segments."
            )

        if not audio_data:
            raise TranscriptionError("Fichier audio vide.")

        if model not in self.MODELES_TRANSCRIPTION:
            raise TranscriptionError(
                f"Modèle de transcription inconnu : {model}. "
                f"Modèles disponibles : {', '.join(self.MODELES_TRANSCRIPTION)}"
            )

        def _whisper_local_disponible() -> bool:
            try:
                import whisper  # noqa: F401
                return True
            except ImportError:
                return False

        def _openai_client() -> Any | None:
            if api_key:
                if client is not None:
                    return client
                try:
                    from openai import OpenAI
                except ImportError:
                    return None
                return OpenAI(api_key=api_key, timeout=timeout)
            return None

        pref = os.environ.get("NURSELOG_TRANSCRIPTION_BACKEND", "").lower()

        if local_model not in self.MODELES_LOCAUX:
            raise TranscriptionError(
                f"Modèle local inconnu : {local_model}. "
                f"Tailles disponibles : {', '.join(self.MODELES_LOCAUX)}"
            )

        langue_code = self._normaliser_langue(langue)

        # Clé API effective (paramètre ou environnement), finalisée avant la
        # décision de backend pour éviter une lecture incohérente.
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

        whisper_local_ok = _whisper_local_disponible()
        client_openai = _openai_client() if api_key else None

        def _transcrire_local_backend() -> str:
            return self._transcrire_local(
                audio_data=audio_data,
                filename=filename,
                langue=langue_code,
                local_model=local_model,
            )

        def _transcrire_openai_backend() -> str:
            return self._transcrire_openai(
                client=client_openai,
                audio_data=audio_data,
                filename=filename,
                langue=langue_code,
                model=model,
            )

        # --- Choix du backend (RGPD : local d'abord) -------------------------
        # pref=="local"  → local uniquement (jamais de repli OpenAI : RGPD).
        # pref=="openai" → OpenAI, repli local si indisponible (données locales).
        # sinon          → local d'abord, repli OpenAI.
        if pref == "local":
            if not whisper_local_ok:
                raise TranscriptionError(
                    "Backend local forcé (NURSELOG_TRANSCRIPTION_BACKEND=local) "
                    "mais `openai-whisper` n'est pas installé. "
                    "Installez `openai-whisper` et `ffmpeg`."
                )
            return _transcrire_local_backend()

        if pref == "openai":
            if client_openai is not None:
                return _transcrire_openai_backend()
            if whisper_local_ok:
                return _transcrire_local_backend()
            raise TranscriptionError(
                "Backend OpenAI forcé (NURSELOG_TRANSCRIPTION_BACKEND=openai) "
                "mais indisponible (pas de OPENAI_API_KEY ou package `openai` "
                "absent), et aucun repli local possible."
            )

        # Défaut : local d'abord (RGPD), repli OpenAI.
        if whisper_local_ok:
            return _transcrire_local_backend()
        if client_openai is not None:
            return _transcrire_openai_backend()

        raise TranscriptionError(
            "Aucun backend de transcription disponible.\n"
            "Option 1 (API) : installez le package `openai` "
            "(`pip install openai`) et définissez OPENAI_API_KEY.\n"
            "Option 2 (local, 100% RGPD) : installez `openai-whisper` "
            "(`pip install openai-whisper`) et `ffmpeg` "
            "(Windows : `winget install Gyan.FFmpeg`)."
        )

    @staticmethod
    def _normaliser_langue(langue: str | None) -> str | None:
        """Convertit une langue affichable en code ISO pour Whisper."""
        if not langue:
            return None
        mapping = {
            "fr": "fr", "français": "fr", "francais": "fr",
            "nl": "nl", "néerlandais": "nl", "nederlands": "nl",
        }
        return mapping.get(langue.lower())

    @staticmethod
    def _construire_prompt_medical() -> str:
        """
        Construit un `initial_prompt` de priming avec le vocabulaire médical
        FR/NL du projet. Whisper utilise ce contexte pour mieux reconnaître
        les termes cliniques (SpO2, EVA, paracétamol, bloeddruk, ...).

        L'ordre est volontairement prioritaire (le prompt est tronqué) :
          1. Signes vitaux — abréviations (TA, FC, SpO2, EVA) les plus
             sensibles à la méreconnaissance ;
          2. Médicaments courants — noms propres souvent mal orthographiés ;
          3. Soins courants, alertes, états généraux — vocabulaire de base.
        """
        termes: list[str] = []

        def _ajouter_categorie(categorie: str) -> None:
            for valeurs in VOCABULAIRE.get(categorie, {}).values():
                termes.extend(valeurs)

        _ajouter_categorie("signes_vitaux")
        # Médicaments courants (FR + NL) — placés juste après les signes vitaux
        # pour maximiser leur présence dans le prompt tronqué.
        termes.extend(NurseLogEngine.MEDICAMENTS_COURANTS)
        for categorie in ("soins_courants", "alertes", "etats_generaux"):
            _ajouter_categorie(categorie)
        # Dédupliquer en préservant l'ordre
        vus = set()
        uniques = []
        for t in termes:
            cle = t.lower()
            if cle not in vus:
                vus.add(cle)
                uniques.append(t)
        # Prompt volontairement compact : au-delà, l'effet de priming diminue
        prompt = ", ".join(uniques)
        return prompt[:650]

    def _transcrire_openai(
        self,
        client: Any,
        audio_data: bytes,
        filename: str,
        langue: str | None,
        model: str,
    ) -> str:
        """Transcription via l'API OpenAI Whisper."""
        suffix = os.path.splitext(filename)[1] or ".wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            kwargs: dict[str, Any] = {
                "model": model,
                "file": open(tmp_path, "rb"),
                "response_format": "text",
            }
            if langue:
                kwargs["language"] = langue
            # Priming du vocabulaire médical pour une meilleure précision
            prompt_medical = self._construire_prompt_medical()
            if prompt_medical:
                kwargs["initial_prompt"] = prompt_medical

            response = client.audio.transcribe(**kwargs)
            texte = (response or "").strip()
            if not texte:
                raise TranscriptionError(
                    "La transcription est vide. Vérifiez que l'enregistrement "
                    "contient bien de la parole."
                )
            return texte
        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(self._traduire_erreur_openai(e)) from e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _traduire_erreur_openai(e: Exception) -> str:
        """Transforme les erreurs brutes de l'API en messages actionnables."""
        msg = str(e).lower()
        if "invalid api key" in msg or "unauthorized" in msg or "401" in msg:
            return (
                "Clé API OpenAI invalide ou expirée. "
                "Vérifiez OPENAI_API_KEY dans votre environnement."
            )
        if "rate limit" in msg or "429" in msg:
            return (
                "Limite de requêtes atteinte (rate limit). "
                "Réessayez dans quelques minutes."
            )
        if "file" in msg and ("large" in msg or "size" in msg):
            return (
                f"Fichier audio trop volumineux (limite : "
                f"{NurseLogEngine.TAILLE_MAX_AUDIO_MO} Mo)."
            )
        if "no speech" in msg or "could not find any speech" in msg:
            return "Aucune parole détectée dans l'enregistrement."
        if "timeout" in msg or "timed out" in msg:
            return (
                "Délai d'attente dépassé lors de la transcription. "
                "Réessayez avec un enregistrement plus court."
            )
        return f"Erreur lors de la transcription : {e}"

    @staticmethod
    def _chercher_ffmpeg() -> str | None:
        """Localise l'exécutable ffmpeg (requis par openai-whisper).

        Cherche d'abord dans le PATH, puis dans les emplacements
        d'installation courants (winget, scoop, Homebrew, système).

        Returns:
            Le chemin complet de l'exécutable, ou None s'il est introuvable.
        """
        trouve = shutil.which("ffmpeg")
        if trouve:
            return trouve

        binaire = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        candidats: list[str] = []
        if os.name == "nt":
            base_user = os.path.expanduser("~")
            # winget : Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-*-full_build/bin
            winget = os.path.join(
                base_user, "AppData", "Local", "Microsoft", "WinGet", "Packages"
            )
            if os.path.isdir(winget):
                for paquet in os.listdir(winget):
                    if paquet.lower().startswith("gyan.ffmpeg"):
                        racine = os.path.join(winget, paquet)
                        try:
                            builds = os.listdir(racine)
                        except OSError:
                            continue
                        for build in builds:
                            bin_dir = os.path.join(racine, build, "bin")
                            if os.path.isfile(os.path.join(bin_dir, binaire)):
                                candidats.append(bin_dir)
            # scoop / installations manuelles courantes
            candidats += [
                os.path.join(base_user, "scoop", "shims"),
                r"C:\Program Files\ffmpeg\bin",
                r"C:\ffmpeg\bin",
            ]
        else:
            # macOS (Homebrew) / Linux
            candidats += ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]

        for dossier in candidats:
            chemin = os.path.join(dossier, binaire)
            if os.path.isfile(chemin):
                return chemin
        return None

    @classmethod
    def _assurer_ffmpeg(cls) -> str | None:
        """S'assure que ffmpeg est accessible dans le PATH.

        openai-whisper appelle ffmpeg en sous-processus pour décoder
        l'audio. Si l'exécutable est installé mais hors du PATH
        (cas fréquent avec winget sur Windows), on préfixe le dossier
        qui le contient au PATH pour que l'appel fonctionne.

        Returns:
            Le chemin de l'exécutable, ou None s'il est introuvable.
        """
        chemin = cls._chercher_ffmpeg()
        if chemin:
            dossier = os.path.dirname(chemin)
            path_actuel = os.environ.get("PATH", "")
            if dossier.lower() not in path_actuel.lower().split(os.pathsep):
                os.environ["PATH"] = dossier + os.pathsep + path_actuel
        return chemin

    def _transcrire_local(
        self,
        audio_data: bytes,
        filename: str,
        langue: str | None,
        local_model: str = "base",
    ) -> str:
        """Transcription 100% locale via le package openai-whisper.

        Le modèle est chargé une seule fois puis mis en cache (clé : taille),
        ce qui accélère fortement les transcriptions suivantes.
        """
        import whisper

        # ffmpeg est requis par whisper pour décoder l'audio
        if NurseLogEngine._assurer_ffmpeg() is None:
            raise TranscriptionError(
                "ffmpeg est introuvable — il est requis par Whisper local "
                "pour décoder l'audio.\n"
                "Installation :\n"
                "  - Windows : `winget install Gyan.FFmpeg` (ou `choco install ffmpeg`)\n"
                "  - macOS : `brew install ffmpeg`\n"
                "  - Linux : `sudo apt install ffmpeg`\n"
                "Puis relancez l'application."
            )

        suffix = os.path.splitext(filename)[1] or ".wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            kwargs: dict[str, Any] = {"fp16": False}
            if langue:
                kwargs["language"] = langue
            # Priming du vocabulaire médical (identique au backend API)
            prompt_medical = self._construire_prompt_medical()
            if prompt_medical:
                kwargs["initial_prompt"] = prompt_medical

            model = self._charger_modele_local(whisper, local_model)
            result = model.transcribe(tmp_path, **kwargs)
            texte = (result.get("text") or "").strip()
            if not texte:
                raise TranscriptionError(
                    "La transcription est vide. Vérifiez que l'enregistrement "
                    "contient bien de la parole."
                )
            return texte
        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(
                f"Erreur lors de la transcription locale : {e}"
            ) from e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _charger_modele_local(whisper: Any, local_model: str) -> Any:
        """Charge (une seule fois) le modèle Whisper local demandé, avec cache.

        Si le modèle demandé n'est pas disponible (téléchargement impossible),
        on retombe sur "tiny" (le plus léger).
        """
        if local_model in NurseLogEngine._whisper_cache:
            return NurseLogEngine._whisper_cache[local_model]
        try:
            modele = whisper.load_model(local_model)
        except Exception:
            if local_model == "tiny":
                raise
            # Modèle indisponible : repli sur la taille la plus légère
            modele = whisper.load_model("tiny")
            NurseLogEngine._whisper_cache["tiny"] = modele
            return modele
        NurseLogEngine._whisper_cache[local_model] = modele
        return modele

    @classmethod
    def statut_transcription(cls) -> dict[str, Any]:
        """
        État des backends de transcription disponibles.
        Utilisé par l'interface pour afficher le statut et guider l'utilisateur.
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        openai_ok = False
        try:
            import openai  # noqa: F401
            openai_ok = True
        except ImportError:
            pass

        whisper_local_ok = False
        try:
            import whisper  # noqa: F401
            whisper_local_ok = True
        except ImportError:
            pass

        # ffmpeg est requis par le backend local (décodage audio)
        ffmpeg_ok = cls._chercher_ffmpeg() is not None

        # Même logique que transcrire_audio (RGPD : local d'abord).
        pref = os.environ.get("NURSELOG_TRANSCRIPTION_BACKEND", "").lower()
        if pref == "local":
            # Forcé local : jamais de repli OpenAI (données ne doivent pas sortir).
            backend = "local" if whisper_local_ok else None
        elif pref == "openai":
            backend = "openai" if (api_key and openai_ok) else (
                "local" if whisper_local_ok else None
            )
        else:
            backend = "local" if whisper_local_ok else (
                "openai" if (api_key and openai_ok) else None
            )

        return {
            "disponible": backend is not None,
            "backend": backend,
            "api_key": bool(api_key),
            "openai_installe": openai_ok,
            "whisper_local_installe": whisper_local_ok,
            "ffmpeg_disponible": ffmpeg_ok,
            "modeles": list(cls.MODELES_TRANSCRIPTION),
            "modeles_locaux": list(cls.MODELES_LOCAUX),
            "formats": list(cls.FORMATS_AUDIO_SUPPORTES),
            "taille_max_mo": cls.TAILLE_MAX_AUDIO_MO,
        }

    # ========================================================================
    # EXTRACTION DES ALERTES
    # ========================================================================

    def _extraire_alertes(self, texte: str) -> list[str]:
        """Détecte les alertes et points de vigilance."""
        alertes = []
        texte_lower = texte.lower()

        alertes_mapping = [
            ("risque chute", "⚠️ Risque de chute — précautions anti-chute en place"),
            ("chute", "⚠️ Chute signalée / risque de chute"),
            ("allergie", "⚠️ Allergie signalée — vérifier protocole"),
            ("isolement", "⚠️ Patient en isolement"),
            ("contrainte", "⚠️ Contrainte physique — vérifier légalité"),
            ("fin de vie", "🕊️ Fin de vie — protocole palliatif"),
            ("palliatif", "🕊️ Soins palliatifs"),
            ("urgence", "🚨 Situation urgente"),
            ("alerter le médecin", "📞 Médecin à alerter"),
            ("informer le médecin", "📞 Médecin informé"),
            ("médecin notifié", "📞 Médecin notifié"),
            ("deterioration", "⚠️ Détérioration de l'état"),
            ("dégradation", "⚠️ Dégradation de l'état"),
            ("aggravation", "⚠️ Aggravation de l'état"),
            ("fièvre", "⚠️ Fièvre — surveillance accrue"),
            ("surveiller", "📋 Surveillance accrue recommandée"),
            ("transmission", "📢 Transmission requise"),
            ("agitation", "⚠️ Agitation du patient"),
            ("confusion", "⚠️ Confusion / délire"),
            ("sang", "⚠️ Saignement"),
            ("hémorragie", "🚨 Hémorragie"),
            # ---- Néerlandais (public cible NL) ----
            ("valrisico", "⚠️ Risque de chute — précautions anti-chute en place"),
            ("dwang", "⚠️ Contrainte physique — vérifier légalité"),
            ("eind van leven", "🕊️ Fin de vie — protocole palliatif"),
            ("palliatieve", "🕊️ Soins palliatifs"),
            ("arts informeren", "📞 Médecin à alerter"),
            ("spoed", "🚨 Situation urgente"),
            ("bloeding", "⚠️ Saignement (bloeding)"),
            ("valrisico", "⚠️ Risque de chute — précautions anti-chute en place"),

            ("allergie", "⚠️ Allergie signalée — vérifier protocole"),
            ("allergie", "⚠️ Allergie signalée — vérifier protocole (allergie)"),
            ("isolatie", "⚠️ Patient en isolement (isolatie)"),
            ("dwang", "⚠️ Contrainte physique — vérifier légalité (dwang)"),
            ("eind van leven", "🕊️ Fin de vie — protocole palliatif"),
            ("palliatieve zorg", "🕊️ Soins palliatifs (palliatieve zorg)"),
            ("spoed", "🚨 Situation urgente (spoed)"),
            ("nood", "🚨 Situation urgente (nood)"),
            ("arts informeren", "📞 Médecin à alerter"),
            ("arts verwittigen", "📞 Médecin à alerter (arts verwittigen)"),
            ("arts gebeld", "📞 Médecin notifié (arts gebeld)"),
            ("verergering", "⚠️ Aggravation de l'état (verergering)"),
            ("verslechtering", "⚠️ Dégradation de l'état (verslechtering)"),
            ("koorts", "⚠️ Fièvre — surveillance accrue (koorts)"),
            ("pijn", "⚠️ Douleur — évaluation requise (pijn)"),
            ("agressie", "⚠️ Agitation du patient (agressie)"),
            ("verwardheid", "⚠️ Confusion / délire (verwardheid)"),
            ("ademnood", "🚨 Détresse respiratoire (ademnood)"),
            ("hypoxie", "⚠️ Hypoxémie — oxygène requis"),
            ("oedeem", "⚠️ Œdème — surveillance"),
            ("incontinentie", "⚠️ Incontinence — soins adaptés"),
            ("diabetes", "⚠️ Diabétique — surveillance glycémie"),
            ("anticoagulans", "⚠️ Anticoagulant — risque hémorragique"),
            ("anticoagulant", "⚠️ Anticoagulant — risque hémorragique"),
        ]

        for motif, alerte in alertes_mapping:
            if motif in texte_lower:
                if alerte not in alertes:
                    alertes.append(alerte)

        # Vérifier valeurs anormales (déjà détectées dans signes vitaux)
        match_ta = self.regex_signes_vitaux["tension"].search(texte)
        if match_ta:
            sys = int(match_ta.group(1))
            dias = int(match_ta.group(2))
            if sys > 160 or dias > 100:
                if "⚠️ Hypertension artérielle" not in alertes:
                    alertes.append("⚠️ Hypertension artérielle")
            if sys < 90 or dias < 60:
                if "⚠️ Hypotension artérielle" not in alertes:
                    alertes.append("⚠️ Hypotension artérielle")

        match_pouls = self.regex_signes_vitaux["pouls"].search(texte)
        if match_pouls:
            fc = int(match_pouls.group(1))
            if fc > 100:
                if "⚠️ Tachycardie (FC > 100)" not in alertes:
                    alertes.append("⚠️ Tachycardie (FC > 100)")
            if fc < 60:
                if "⚠️ Bradycardie (FC < 60)" not in alertes:
                    alertes.append("⚠️ Bradycardie (FC < 60)")

        match_temp = self.regex_signes_vitaux["temperature"].search(texte)
        if match_temp:
            temp = float(match_temp.group(1).replace(',', '.'))
            if temp >= 38.5:
                if "⚠️ Fièvre élevée (>38.5°C)" not in alertes:
                    alertes.append("⚠️ Fièvre élevée (>38.5°C)")

        match_spo2 = self.regex_signes_vitaux["spo2"].search(texte)
        if match_spo2:
            spo2 = int(match_spo2.group(1))
            if spo2 < 92:
                if "⚠️ Hypoxémie sévère (SpO2 < 92%)" not in alertes:
                    alertes.append("⚠️ Hypoxémie sévère (SpO2 < 92%)")
            elif spo2 < 95:
                if "⚠️ Hypoxémie modérée (SpO2 < 95%)" not in alertes:
                    alertes.append("⚠️ Hypoxémie modérée (SpO2 < 95%)")

        return alertes

    # ========================================================================
    # EXTRACTION DU PLAN DE SOINS
    # ========================================================================

    def _extraire_plan(self, texte: str) -> list[str]:
        """Extrait les actions futures et le plan de soins."""
        plan = []
        texte_lower = texte.lower()

        # Extraire les phrases contenant des mots-clés d'actions futures
        # Séparer le texte en phrases
        phrases = re.split(r'[.;\n]+', texte)
        mots_cles_plan = [
            r'prochain', r'prochaine', r'dans\s+\d+', r'à\s+refaire', r'a\s+refaire',
            r'répéter', r'répeter', r'surveiller', r'veiller', r'prévoir', r'prevoir',
            r'planifier', r'demain', r'quart\s+suivant', r'à\s+faire', r'a\s+faire',
            r'objectif', r'recommand', r'conseil',
            # ---- Néerlandais ----
            r'volgende', r'morgen', r'herbeoordeling', r'controle',
            r'controleer', r'opnieuw', r'herhaal', r'waakzaam',
            r'plannen', r'ter\s+plekke', r'afspraken', r'afspraken\s+maken',
            r'volgend\s+quart', r'volgende\s+24', r'volgende\s+48',
            # ---- Français supplémentaire ----
            r'réévaluer', r'reevaluer', r'réévaluation', r'reevaluation',
            r'contrôler', r'controle', r'vérifier\s+au', r'verifier\s+au',
            r'noter\s+au', r'inscrire\s+au', r'consigner',
        ]
        pattern_plan = re.compile(
            r'(?:' + '|'.join(mots_cles_plan) + r')',
            re.IGNORECASE
        )

        for phrase in phrases:
            phrase = phrase.strip()
            if pattern_plan.search(phrase) and 10 < len(phrase) < 200:
                # Nettoyer la phrase
                phrase_nettoyee = phrase.strip('.,;:-• ')
                if phrase_nettoyee and phrase_nettoyee not in plan:
                    plan.append(phrase_nettoyee)

        # Plans par défaut basés sur les soins détectés
        # (uniquement si pas déjà extraits du texte)
        plans_par_defaut = {
            "pansement": "Prochain pansement dans 48h (sauf indication contraire)",
            "plaie": "Surveillance plaie quotidienne",
            "sonde": "Vérifier perméabilité sonde au quart",
            "perfusion": "Surveillance voie veineuse",
            "chute": "Précautions anti-chute maintenues",
            "douleur": "Réévaluation douleur après traitement",
            "fièvre": "Surveillance température toutes les 4h",
        }

        for motif, plan_action in plans_par_defaut.items():
            if motif in texte_lower:
                # Ne pas ajouter si le sujet est déjà dans les plans existants
                si_deja_present = False
                for plan_existant in plan:
                    if motif in plan_existant.lower():
                        si_deja_present = True
                        break
                if not si_deja_present and plan_action not in plan:
                    plan.append(plan_action)

        if not plan and texte.strip():
            plan.append("📌 Surveillance standard au quart")
            plan.append("📌 Réévaluation selon protocole")

        return plan

    # ========================================================================
    # MAPPING CODES NAA
    # ========================================================================

    def _mapper_codes_naa(self, texte: str) -> list[dict]:
        """Mappe le texte aux codes NAA belges appropriés."""
        codes_trouves = []
        texte_lower = texte.lower()

        # Vérifier si un code NAA est explicitement mentionné
        match_explicite = self.regex_code_naa.search(texte)
        if match_explicite:
            codes_trouves.append({
                "code": match_explicite.group(1),
                "source": "mention_explicite"
            })

        # Mapping automatique basé sur les soins détectés
        mapping_auto = {
            "pansement": "pansement",
            "plaie": "pansement",
            "escarr": "pansement",  # escarre, escarres
            "ulcère": "pansement",  # ulcère, ulcères
            "injection": "injection",
            "im": "injection",
            "sc": "injection",
            "sq": "injection",
            "perfusion": "perfusion",
            "voie veineuse": "perfusion",
            "cathéter": "perfusion",
            "glycémie": "surveillance",
            "glycémie capillaire": "surveillance",
            "spo2": "surveillance",
            "saturation": "surveillance",
            "surveillance": "surveillance",
            "éducation": "education",
            "éduquer": "education",
            "douleur": "douleur",
            "eva": "douleur",
        }

        for motif, categorie in mapping_auto.items():
            if motif in texte_lower:
                for code_info in CODES_NAA_RECONNAISSANCE.get(categorie, []):
                    code_entree = {
                        "code": code_info["code"],
                        "nom": code_info["nom"],
                        "source": "mapping_auto"
                    }
                    # Éviter les doublons
                    if not any(c.get("code") == code_info["code"] for c in codes_trouves):
                        codes_trouves.append(code_entree)

        return codes_trouves

    # ========================================================================
    # EXTRACTION MÉDICAMENTS
    # ========================================================================

    # Voies d'administration reconnues (FR + NL + abréviations)
    VOIES_ADMINISTRATION = {
        "iv": ["iv", "i.v.", "intraveineuse", "intraveineux", "voie veineuse", "intra-veineuse", "i.v."],
        "im": ["im", "i.m.", "intramusculaire", "intra-musculaire"],
        "sc": ["sc", "sq", "s.c.", "s.q.", "sous-cutanée", "sous-cutane", "sous-cutanée", "subcutane"],
        "po": ["po", "per os", "oral", "orale", "per os", "oraal"],
        "sl": ["sl", "sublinguale", "sublingual"],
        "top": ["top", "topique", "topical", "local"],
        "inhal": ["inhal", "inhalation", "inhalé", "inhele"],
        "rectal": ["rectal", "rectale", "suppositoire"],
        "oculaire": ["oculaire", "oculaire", "collyre"],
        "auriculaire": ["auriculaire", "oreille"],
    }

    def _detecter_voie(self, contexte: str) -> str:
        """Détecte la voie d'administration dans le contexte autour du médicament.

        Les variantes courtes (≤ 3 caractères, sans espaces) sont
        testées en word-boundary pour éviter les faux positifs
        (ex. "sc" dans "escargot", "iv" dans "privé").
        """
        contexte_lower = contexte.lower()
        for voie, variantes in self.VOIES_ADMINISTRATION.items():
            for variante in variantes:
                if len(variante) <= 3 and not any(c in variante for c in " ."):
                    if re.search(rf'\b{re.escape(variante)}\b', contexte_lower):
                        return voie.upper()
                else:
                    if variante in contexte_lower:
                        return voie.upper()
        return ""

    def _extraire_medicaments(self, texte: str) -> list[dict]:
        """
        Extrait TOUTES les informations sur les médicaments.

        Gère plusieurs patterns :
          - "paracétamol 1g IV" (nom + dose + voie)
          - "1g de paracétamol" (dose + nom)
          - "paracétamol, 1000mg" (virgule)
          - "administration de morphine 2mg SC" (préposition)
          - "paracétamol 1000 mg" (espace entre dose et unité)
          - "insuline 10 UI" (unités internationales)
        """
        medicaments = []

        # --- Pattern 1 : nom + dose + unité (regex existante) ---
        for match in self.regex_medicament.finditer(texte):
            nom = match.group(1).strip()
            dose = match.group(2)
            unite = match.group(3)
            # Extraire la voie dans le contexte (±30 caractères après)
            contexte_voie = texte[match.end():match.end()+40]
            voie = self._detecter_voie(contexte_voie)
            if not any(m["nom"].lower() == nom.lower() for m in medicaments):
                medicaments.append({
                    "nom": nom,
                    "dose": dose,
                    "unite": unite,
                    "voie": voie,
                })

        # --- Pattern 2 : dose + "de" + nom (ex: "1g de paracétamol") ---
        regex_dose_nom = re.compile(
            r'(\d+(?:\.\d+)?)\s*(mg|ml|g|UI|µg|microg)\s*(?:de|d\'?)\s+'
            r'([A-Za-zàâéèêîôûùçñ]{3,}(?:\s+[A-Za-zàâéèêîôûùçñ]+)*)',
            re.IGNORECASE
        )
        for match in regex_dose_nom.finditer(texte):
            dose = match.group(1)
            unite = match.group(2)
            nom = match.group(3).strip()
            contexte_voie = texte[match.end():match.end()+40]
            voie = self._detecter_voie(contexte_voie)
            if not any(m["nom"].lower() == nom.lower() for m in medicaments):
                medicaments.append({
                    "nom": nom,
                    "dose": dose,
                    "unite": unite,
                    "voie": voie,
                })

        # --- Pattern 3 : nom + virgule + dose (ex: "paracétamol, 1g") ---
        regex_nom_comma_dose = re.compile(
            r'([A-Za-zàâéèêîôûùçñ]{3,}(?:\s+[A-Za-zàâéèêîôûùçñ]+)*)\s*[,;]\s*'
            r'(\d+(?:\.\d+)?)\s*(mg|ml|g|UI|µg|microg)',
            re.IGNORECASE
        )
        for match in regex_nom_comma_dose.finditer(texte):
            nom = match.group(1).strip()
            dose = match.group(2)
            unite = match.group(3)
            contexte_voie = texte[match.end():match.end()+40]
            voie = self._detecter_voie(contexte_voie)
            if not any(m["nom"].lower() == nom.lower() for m in medicaments):
                medicaments.append({
                    "nom": nom,
                    "dose": dose,
                    "unite": unite,
                    "voie": voie,
                })

        # --- Pattern 4 : nom + dose sans espace (ex: "paracétamol1000mg") ---
        # Filtre : nom ≥ 4 caractères pour éviter les faux positifs
        # (ex. "chambre 12g" → "chambre" n'est pas un médicament).
        regex_nom_dose_colle = re.compile(
            r'([A-Za-zàâéèêîôûùçñ]{4,})\s*(\d+(?:\.\d+)?)\s*(mg|ml|g|UI|µg|microg)',
            re.IGNORECASE
        )
        for match in regex_nom_dose_colle.finditer(texte):
            nom = match.group(1).strip()
            dose = match.group(2)
            unite = match.group(3)
            contexte_voie = texte[match.end():match.end()+40]
            voie = self._detecter_voie(contexte_voie)
            if not any(m["nom"].lower() == nom.lower() for m in medicaments):
                medicaments.append({
                    "nom": nom,
                    "dose": dose,
                    "unite": unite,
                    "voie": voie,
                })

        # --- Recherche générique de noms de médicaments courants (FR + NL) ---
        meds_courants = list(self.MEDICAMENTS_COURANTS)

        texte_lower = texte.lower()
        for med in meds_courants:
            if med in texte_lower:
                if not any(m["nom"].lower() == med.lower() for m in medicaments):
                    # Chercher la voie dans les 60 caractères autour
                    idx = texte_lower.find(med)
                    contexte = texte[max(0, idx-20):idx+len(med)+40]
                    voie = self._detecter_voie(contexte)
                    medicaments.append({
                        "nom": med.capitalize(),
                        "dose": "N/A",
                        "unite": "",
                        "voie": voie,
                    })

        return medicaments

    # ========================================================================
    # TRANSMISSIONS SBAr
    # ========================================================================

    def _generer_transmissions(self, texte: str, rapport: dict) -> list[dict]:
        """
        Génère une transmission structurée en format SBAr enrichi.

        Le SBAr (Situation-Background-Assessment-Recommendation) est le
        standard de communication clinique en Belgique. Cette version
        inclut les données cliniques réelles extraites du rapport.
        """
        transmission = {
            "format": "SBAr",
            "S_Situation": self._resumer_situation(rapport),
            "B_Contexte": self._resumer_contexte(texte, rapport),
            "A_Appreciation": self._resumer_appreciation(rapport),
            "R_Recommandation": self._resumer_recommandation(rapport),
        }
        return [transmission]

    def _resumer_situation(self, rapport: dict) -> str:
        """Résume la situation actuelle du patient avec les données clés."""
        patient = rapport.get("patient", {})
        nom = patient.get("prenom", "") + " " + patient.get("nom", "")
        chambre = patient.get("chambre", "")

        situation = f"Patient {nom}, {chambre}."

        # État général
        etat = rapport.get("evaluation", {}).get("État général", "")
        if etat:
            situation += f" {etat}"

        # Douleur (donnée critique pour la transmission)
        douleur = rapport.get("evaluation", {}).get("Confort douleur", "")
        if douleur:
            situation += f" {douleur}."

        # Alertes critiques (max 3 pour rester concis)
        alertes = rapport.get("alertes", [])
        if alertes:
            critiques = [a for a in alertes if "🚨" in a or "⚠️" in a][:3]
            if critiques:
                situation += f" Points de vigilance : {'; '.join(critiques)}."
            else:
                situation += f" {len(alertes)} point(s) de vigilance."

        return situation

    def _resumer_contexte(self, texte: str, rapport: dict) -> str:
        """Résume le contexte clinique avec les signes vitaux et traitements."""
        contexte_parts = []

        # Signes vitaux (extraits du rapport, plus fiables que re-parsing)
        sv = rapport.get("evaluation", {}).get("Signes vitaux", {})
        if sv:
            for cle, valeur in sv.items():
                if cle in ("Tension artérielle", "Pouls", "Température", "SpO2", "Glycémie", "Fréquence respiratoire"):
                    contexte_parts.append(f"{cle}: {valeur}")

        # Si pas de SV dans le rapport, extraire du texte (fallback)
        if not contexte_parts:
            match_ta = self.regex_signes_vitaux["tension"].search(texte)
            if match_ta:
                contexte_parts.append(f"TA: {match_ta.group(1)}/{match_ta.group(2)}")
            match_pouls = self.regex_signes_vitaux["pouls"].search(texte)
            if match_pouls:
                contexte_parts.append(f"FC: {match_pouls.group(1)} bpm")
            match_temp = self.regex_signes_vitaux["temperature"].search(texte)
            if match_temp:
                contexte_parts.append(f"T°: {match_temp.group(1)}°C")
            match_spo2 = self.regex_signes_vitaux["spo2"].search(texte)
            if match_spo2:
                contexte_parts.append(f"SpO2: {match_spo2.group(1)}%")

        # Médicaments administrés (contexte important)
        medicaments = rapport.get("medicaments", [])
        if medicaments:
            meds_str = ", ".join(
                f"{m['nom']} {m.get('dose', '')} {m.get('unite', '')}".strip()
                for m in medicaments[:4]
            )
            contexte_parts.append(f"Traitements: {meds_str}")

        # Nutrition / hydratation
        nutrition = rapport.get("evaluation", {}).get("Nutrition hydratation", "")
        if nutrition:
            contexte_parts.append(nutrition)

        return "; ".join(contexte_parts) if contexte_parts else "Voir rapport complet."

    def _resumer_appreciation(self, rapport: dict) -> str:
        """Résume l'appréciation clinique avec les soins et alertes spécifiques."""
        soins = rapport.get("soins", [])
        alertes = rapport.get("alertes", [])

        appreciation_parts = []

        # Soins réalisés (max 4 pour rester concis)
        if soins:
            soins_str = "; ".join(soins[:4])
            appreciation_parts.append(f"Soins: {soins_str}.")
        else:
            appreciation_parts.append("Aucun soin spécifique documenté.")

        # Alertes spécifiques
        if alertes:
            alertes_str = "; ".join(alertes[:3])
            appreciation_parts.append(f"Vigilance: {alertes_str}.")
        else:
            appreciation_parts.append("Aucune alerte majeure.")

        # État de douleur (si présent)
        douleur = rapport.get("evaluation", {}).get("Confort douleur", "")
        if douleur and ("⚠️" in douleur or "sévère" in douleur.lower()):
            appreciation_parts.append(f"Douleur significative: {douleur}.")

        return " ".join(appreciation_parts)

    def _resumer_recommandation(self, rapport: dict) -> str:
        """Résume les recommandations et actions à venir."""
        plan = rapport.get("plan", [])
        if plan:
            return "\n".join(f"• {p}" for p in plan[:6])
        return "Surveillance standard. Réévaluation selon protocole."

    # ========================================================================
    # SCORE DE COMPLÉTUDE
    # ========================================================================

    def score_completude(self, rapport: dict) -> dict:
        """
        Calcule un score de complétude du rapport (0-100%).

        Évalue :
          - Identification patient (nom, chambre)
          - Signes vitaux (au moins 1 mesuré)
          - Soins documentés
          - Plan de soins
          - Alertes (si pertinentes)
          - Transmission SBAr

        Returns:
            {"score": int, "details": [{"criter": str, "ok": bool, "poids": int, "note": str}]}
        """
        criteres = []

        # 1. Identification patient (poids 20)
        patient = rapport.get("patient", {})
        patient_ok = bool(patient.get("nom") and patient.get("chambre"))
        criteres.append({
            "criter": "Identification patient",
            "ok": patient_ok,
            "poids": 20,
            "note": "Nom et chambre renseignés" if patient_ok else "Nom ou chambre manquant",
        })

        # 2. Signes vitaux (poids 25)
        sv = rapport.get("evaluation", {}).get("Signes vitaux", {})
        sv_ok = len(sv) >= 1
        sv_count = len(sv)
        criteres.append({
            "criter": "Signes vitaux",
            "ok": sv_ok,
            "poids": 25,
            "note": f"{sv_count} paramètre(s) mesuré(s)" if sv_ok else "Aucun signe vital enregistré",
        })

        # 3. Soins documentés (poids 25)
        soins = rapport.get("soins", [])
        soins_ok = len(soins) >= 1
        criteres.append({
            "criter": "Soins documentés",
            "ok": soins_ok,
            "poids": 25,
            "note": f"{len(soins)} soin(s)" if soins_ok else "Aucun soin documenté",
        })

        # 4. Plan de soins (poids 15)
        plan = rapport.get("plan", [])
        plan_ok = len(plan) >= 1
        criteres.append({
            "criter": "Plan de soins",
            "ok": plan_ok,
            "poids": 15,
            "note": f"{len(plan)} action(s) prévue(s)" if plan_ok else "Aucun plan défini",
        })

        # 5. Transmission SBAr (poids 15)
        transmissions = rapport.get("transmissions", [])
        sbar_ok = len(transmissions) >= 1 and all(
            t.get("S_Situation") and t.get("A_Appreciation")
            for t in transmissions
        )
        criteres.append({
            "criter": "Transmission SBAr",
            "ok": sbar_ok,
            "poids": 15,
            "note": "SBAr complet" if sbar_ok else "SBAr incomplet ou absent",
        })

        # Calcul du score pondéré
        score_total = sum(c["poids"] for c in criteres if c["ok"])
        score_max = sum(c["poids"] for c in criteres)
        score = round(score_total / score_max * 100) if score_max > 0 else 0

        return {
            "score": score,
            "details": criteres,
            "complet": score >= 80,
            "partiel": 40 <= score < 80,
            "incomplet": score < 40,
        }

    # ========================================================================
    # UTILITAIRES
    # ========================================================================

    def exporter_json(self, rapport: dict) -> str:
        """Exporte le rapport en format JSON."""
        return json.dumps(rapport, indent=2, ensure_ascii=False)

    def exporter_texte_lisible(self, rapport: dict) -> str:
        """Exporte le rapport en texte lisible pour impression."""
        lignes = []
        lignes.append("=" * 60)
        lignes.append("NURSELOG AI — RAPPORT DE SOINS INFIRMIERS")
        lignes.append("=" * 60)
        lignes.append("")

        # Patient
        p = rapport.get("patient", {})
        lignes.append(f"Patient: {p.get('prenom', '')} {p.get('nom', '')}")
        lignes.append(f"Lieu: {p.get('chambre', '')}")
        lignes.append(f"Date: {rapport.get('metadata', {}).get('date', '')} "
                     f"{rapport.get('metadata', {}).get('heure', '')}")
        lignes.append("")

        # Évaluation
        eval_data = rapport.get("evaluation", {})
        if eval_data.get("Signes vitaux"):
            lignes.append("--- SIGNES VITAUX ---")
            for k, v in eval_data["Signes vitaux"].items():
                lignes.append(f"  {k}: {v}")
            lignes.append("")

        # Soins
        if rapport.get("soins"):
            lignes.append("--- SOINS RÉALISÉS ---")
            for soin in rapport["soins"]:
                lignes.append(f"  ✅ {soin}")
            lignes.append("")

        # Alertes
        if rapport.get("alertes"):
            lignes.append("--- ALERTES ---")
            for alerte in rapport["alertes"]:
                lignes.append(f"  ⚠️ {alerte}")
            lignes.append("")

        # Plan
        if rapport.get("plan"):
            lignes.append("--- PLAN DE SOINS ---")
            for action in rapport["plan"]:
                lignes.append(f"  📌 {action}")
            lignes.append("")

        # Médicaments
        if rapport.get("medicaments"):
            lignes.append("--- MÉDICAMENTS ---")
            for med in rapport["medicaments"]:
                voie = f" ({med['voie']})" if med.get('voie') else ""
                lignes.append(f"  💊 {med.get('nom', 'N/A')} — {med.get('dose', '')} {med.get('unite', '')}{voie}")
            lignes.append("")

        # Transmission SBAr
        transmissions = rapport.get("transmissions", [])
        if transmissions:
            lignes.append("--- TRANSMISSION SBAr ---")
            for t in transmissions:
                for section, contenu in t.items():
                    if section != "format":
                        lignes.append(f"  {section}: {contenu}")
            lignes.append("")

        lignes.append("=" * 60)
        lignes.append("Généré par NurseLog AI v" + self.version)
        lignes.append("=" * 60)

        return "\n".join(lignes)

    def generer_rapport_structure(self, patient_data: dict[str, Any], evaluation: dict, soins: list[str], alertes: list[str], plan: list[str]) -> dict[str, Any]:
        """
        Génère un rapport directement depuis des champs structurés (mode Manuel).
        Pas de parsing regex — les données sont déjà structurées.

        Args:
            patient_data: {nom, prenom, chambre, date_naissance, numero_dossier, quart, langue, type_rapport}
            evaluation: Dictionnaire des signes vitaux et évaluations
            soins: Liste des soins réalisés (déjà en texte)
            alertes: Liste des alertes
            plan: Liste des actions du plan

        Returns:
            Dictionnaire structuré conforme au template belge
        """
        rapport = self._copier_template()

        # Métadonnées
        maintenant = datetime.datetime.now()
        rapport["metadata"]["date"] = maintenant.strftime("%Y-%m-%d")
        rapport["metadata"]["heure"] = maintenant.strftime("%H:%M")
        rapport["metadata"]["quart"] = patient_data.get("quart", "")
        rapport["metadata"]["type_rapport"] = patient_data.get("type_rapport", "Rapport de soins standard")
        rapport["metadata"]["langue"] = patient_data.get("langue", "Français")

        # Patient
        rapport["patient"]["nom"] = patient_data.get("nom", "")
        rapport["patient"]["prenom"] = patient_data.get("prenom", "")
        rapport["patient"]["date_naissance"] = patient_data.get("date_naissance", "")
        rapport["patient"]["chambre"] = patient_data.get("chambre", "")
        rapport["patient"]["numero_dossier"] = patient_data.get("numero_dossier", "")

        # Évaluation (déjà structurée)
        rapport["evaluation"] = evaluation if evaluation else self._evaluation_vide()

        # Soins, alertes, plan (déjà en liste)
        rapport["soins"] = soins if soins else []
        rapport["alertes"] = alertes if alertes else []
        rapport["plan"] = plan if plan else []

        # Codes NAA — mapping automatique depuis les soins
        texte_soins = " ".join(soins).lower() if soins else ""
        rapport["codes_naa"] = self._mapper_codes_naa(texte_soins)

        # Médicaments — extraction depuis le texte des soins
        rapport["medicaments"] = self._extraire_medicaments(" ".join(soins))

        # Transmission SBAr
        rapport["transmissions"] = self._generer_transmissions(" ".join(soins), rapport)

        return rapport

    def _evaluation_vide(self) -> dict:
        """Retourne une structure d'évaluation vide."""
        return {
            "Signes vitaux": {},
            "Confort douleur": "",
            "État général": "",
            "Nutrition hydratation": "",
            "Mobilité": "",
            "Pele muqueuses": "",
            "Eliminations": "",
            "État psychologique": "",
        }

    def valider_rapport(self, rapport: dict) -> tuple[bool, list[str]]:
        """
        Valide la complétude du rapport avec vérifications croisées cliniques.

        Vérifications de base :
          - Identification patient
          - Signes vitaux
          - Soins documentés
          - Plan de soins

        Vérifications croisées (logique clinique) :
          - Douleur ≥ 7 → traitement antalgique documenté ?
          - Fièvre ≥ 38.5 → antipyrétique ou surveillance ?
          - SpO2 < 95 → oxygénothérapie ou alerte médecin ?
          - Hypotension → surveillance renforcée ?
          - Hypoglycémie → traitement ou surveillance ?

        Returns:
            (est_valide, liste_des_warnings)
        """
        warnings = []

        # --- Vérifications de base ---
        patient = rapport.get("patient", {})
        if not patient.get("nom"):
            warnings.append("⚠️ Nom du patient manquant")
        if not patient.get("prenom"):
            warnings.append("⚠️ Prénom du patient manquant")

        sv = rapport.get("evaluation", {}).get("Signes vitaux", {})
        if not sv:
            warnings.append("⚠️ Aucun signe vital enregistré")

        if not rapport.get("soins"):
            warnings.append("⚠️ Aucun soin documenté")

        if not rapport.get("plan"):
            warnings.append("⚠️ Aucun plan de soins défini")

        # --- Vérifications croisées cliniques ---
        texte_complet = " ".join([
            rapport.get("dictee_originale", ""),
            " ".join(rapport.get("soins", [])),
            " ".join(rapport.get("alertes", [])),
            " ".join(rapport.get("plan", [])),
            str(rapport.get("evaluation", {}).get("Confort douleur", "")),
            str(rapport.get("evaluation", {}).get("État général", "")),
        ]).lower()

        medicaments = rapport.get("medicaments", [])
        noms_meds = " ".join(m.get("nom", "").lower() for m in medicaments)

        # 1. Douleur sévère (≥ 7) → traitement antalgique ?
        douleur_val = rapport.get("evaluation", {}).get("Confort douleur", "")
        match_douleur = re.search(r'(\d{1,2})/10', douleur_val)
        if match_douleur:
            douleur_score = int(match_douleur.group(1))
            if douleur_score >= 7:
                antalgiques = ["paracétamol", "ibuprofène", "morphine", "fentanyl",
                              "tramadol", "codeïne", "oxycodone", "buprenorphine",
                              "diclofénac", "kétoprofène", "spasfon"]
                a_ete_traite = any(ant in noms_meds or ant in texte_complet for ant in antalgiques)
                if not a_ete_traite:
                    warnings.append(
                        f"🔴 Douleur {douleur_score}/10 — aucun traitement antalgique documenté. "
                        "Vérifier si un traitement a été administré ou si le médecin a été informé."
                    )

        # 2. Fièvre élevée (≥ 38.5) → antipyrétique ou surveillance ?
        temp_val = sv.get("Température", "")
        match_temp = re.search(r'(\d+(?:\.\d+)?)', temp_val)
        if match_temp:
            temp = float(match_temp.group(1))
            if temp >= 38.5:
                antipyrétiques = ["paracétamol", "ibuprofène", "aspirine"]
                a_ete_traite = any(ant in noms_meds or ant in texte_complet for ant in antipyrétiques)
                surveillance_specifique = any(
                    s in texte_complet for s in
                    ["surveillance renforcée", "surveillance rapprochée", "surveiller de près",
                     "surveillance toutes les", "surveillance stricte", "surveillance active"]
                )
                if not a_ete_traite and not surveillance_specifique:
                    warnings.append(
                        f"🔴 Fièvre {temp}°C — aucun antipyrétique ni surveillance documentée. "
                        "Vérifier le protocole."
                    )

        # 3. SpO2 < 95% → oxygénothérapie ou alerte ?
        spo2_val = sv.get("SpO2", "")
        match_spo2 = re.search(r'(\d{2,3})', spo2_val)
        if match_spo2:
            spo2 = int(match_spo2.group(1))
            if spo2 < 95:
                oxygene = any(
                    s in texte_complet for s in
                    ["oxygène", "oxygene", "oxygen", "oxygénothérapie", "oxygenotherapie",
                     "oxygenation", "o2 therapy", "o2 therapi", "oxygène administré", "o2 administré"]
                )
                medecin = "médecin" in texte_complet or "medecin" in texte_complet or "alerter" in texte_complet
                if not oxygene and not medecin:
                    warnings.append(
                        f"🔴 SpO2 {spo2}% — aucune oxygénothérapie ni alerte médecin documentée. "
                        "Vérifier la prise en charge."
                    )

        # 4. Hypotension (TA < 90/60) → surveillance renforcée ?
        ta_val = sv.get("Tension artérielle", "")
        match_ta = re.search(r'(\d{2,3})/(\d{2,3})', ta_val)
        if match_ta:
            sys = int(match_ta.group(1))
            dias = int(match_ta.group(2))
            if sys < 90 or dias < 60:
                surveillance = "surveillance" in texte_complet or "surveiller" in texte_complet
                medecin = "médecin" in texte_complet or "medecin" in texte_complet
                if not surveillance and not medecin:
                    warnings.append(
                        f"🔴 Hypotension ({sys}/{dias}) — aucune surveillance renforcée ni alerte médecin. "
                        "Vérifier la prise en charge."
                    )

        # 5. Hypoglycémie (< 0.6 g/L) → traitement ?
        glyc_val = sv.get("Glycémie", "")
        match_glyc = re.search(r'([\d.]+)', glyc_val)
        if match_glyc:
            glyc = float(match_glyc.group(1))
            if glyc < 0.6:
                traitement = "glucose" in texte_complet or "dextrose" in texte_complet or "sucre" in texte_complet
                medecin = "médecin" in texte_complet or "medecin" in texte_complet
                if not traitement and not medecin:
                    warnings.append(
                        f"🔴 Hypoglycémie ({glyc} g/L) — aucun traitement ni alerte médecin. "
                        "Vérifier la prise en charge."
                    )

        return (len(warnings) == 0, warnings)
