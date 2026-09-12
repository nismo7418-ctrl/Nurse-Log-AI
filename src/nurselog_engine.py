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

import os
import re
import datetime
import json
import tempfile
from typing import Dict, List, Optional, Any

from templates import (
    RAPPORT_TEMPLATE,
    TEMPLATES_TYPES,
    VOCABULAIRE,
    CODES_NAA_RECONNAISSANCE,
    ECHELLES_EVALUATION,
    STRUCTURE_SBAr
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
        self.llm_available = False
        try:
            import transformers
            self.llm_available = True
        except ImportError:
            pass

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
                r'(?:=\s*|:\s*)?([\d.]+)\s*(?:°C|degrees)?',
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
                r'([\d.]+)\s*(?:g/L|mmol/L)?',
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
            r'([A-Za-zàâéèêîôûùçñ]+(?:\s+[A-Za-zàâéèêîôûùçñ]+)*)'
            r'\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|UI|µg|microg)',
            re.IGNORECASE
        )

        self.regex_heure = re.compile(
            r'(\d{1,2})\s*(?:h|:)\s*(\d{2})',
            re.IGNORECASE
        )

    # ========================================================================
    # MÉTHODE PRINCIPALE
    # ========================================================================

    def generer_rapport(self, dictee: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
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
        
        return rapport

    # ========================================================================
    # REMPLISSAGE MÉTADONNÉES & PATIENT
    # ========================================================================

    def _copier_template(self) -> Dict:
        """Crée une copie profonde du template de rapport."""
        return json.loads(json.dumps(RAPPORT_TEMPLATE))

    def _remplir_metadonnees(self, rapport: Dict, patient_data: Dict):
        """Remplit les métadonnées du rapport."""
        maintenant = datetime.datetime.now()
        rapport["metadata"]["date"] = maintenant.strftime("%Y-%m-%d")
        rapport["metadata"]["heure"] = maintenant.strftime("%H:%M")
        rapport["metadata"]["quart"] = patient_data.get("quart", "")
        rapport["metadata"]["type_rapport"] = patient_data.get("type_rapport", "Rapport de soins standard")
        rapport["metadata"]["langue"] = patient_data.get("langue", "Français")

    def _remplir_patient(self, rapport: Dict, patient_data: Dict):
        """Remplit les informations patient."""
        rapport["patient"]["nom"] = patient_data.get("nom", "")
        rapport["patient"]["prenom"] = patient_data.get("prenom", "")
        rapport["patient"]["date_naissance"] = patient_data.get("date_naissance", "")
        rapport["patient"]["chambre"] = patient_data.get("chambre", "")
        rapport["patient"]["numero_dossier"] = patient_data.get("numero_dossier", "")

    # ========================================================================
    # EXTRACTION DES SIGNES VITAUX
    # ========================================================================

    def _extraire_signes_vitaux(self, texte: str) -> Dict:
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

    def _extraire_soins(self, texte: str) -> List[str]:
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
            l = match_plaie.group(1)
            w = match_plaie.group(2)
            d = match_plaie.group(3) if match_plaie.group(3) else "N/A"
            if f"Plaie mesurée: {l} x {w} x {d} cm" not in soins:
                soins.append(f"Plaie mesurée: {l} x {w} x {d} cm")

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

    def _extraire_phrases_soins(self, texte: str) -> List[str]:
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
    _whisper_cache: Dict[str, Any] = {}

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
        langue: Optional[str] = None,
        model: str = "whisper-1",
        local_model: str = "base",
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        timeout: int = 120,
    ) -> str:
        """
        Transcrit un fichier audio en texte (dictée de soins).

        Deux backends, dans cet ordre :
          1. **API OpenAI Whisper** — si `api_key` est fournie et le package
             `openai` est installé. Bénéficie de l'indice de langue et du
             priming de vocabulaire médical (`initial_prompt`) pour une
             meilleure précision sur les termes cliniques.
          2. **Whisper local** (package `openai-whisper`) — 100% local,
             aucune donnée ne quitte la machine (conforme au principe
             local-first / RGPD du projet).

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

        if local_model not in self.MODELES_LOCAUX:
            raise TranscriptionError(
                f"Modèle local inconnu : {local_model}. "
                f"Tailles disponibles : {', '.join(self.MODELES_LOCAUX)}"
            )

        langue_code = self._normaliser_langue(langue)

        # --- Backend 1 : API OpenAI Whisper ---------------------------------
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            if client is None:
                try:
                    from openai import OpenAI
                except ImportError:
                    client = None
                else:
                    client = OpenAI(api_key=api_key, timeout=timeout)
            if client is not None:
                return self._transcrire_openai(
                    client=client,
                    audio_data=audio_data,
                    filename=filename,
                    langue=langue_code,
                    model=model,
                )

        # --- Backend 2 : Whisper local (openai-whisper) ----------------------
        try:
            import whisper  # noqa: F401
        except ImportError:
            pass
        else:
            return self._transcrire_local(
                audio_data=audio_data,
                filename=filename,
                langue=langue_code,
                local_model=local_model,
            )

        # --- Aucun backend disponible ----------------------------------------
        raise TranscriptionError(
            "Aucun backend de transcription disponible.\n"
            "Option 1 (API) : installez le package `openai` "
            "(`pip install openai`) et définissez OPENAI_API_KEY.\n"
            "Option 2 (local, 100% RGPD) : installez `openai-whisper` "
            "(`pip install openai-whisper`)."
        )

    @staticmethod
    def _normaliser_langue(langue: Optional[str]) -> Optional[str]:
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
        termes: List[str] = []

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
        langue: Optional[str],
        model: str,
    ) -> str:
        """Transcription via l'API OpenAI Whisper."""
        suffix = os.path.splitext(filename)[1] or ".wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            kwargs: Dict[str, Any] = {
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

    def _transcrire_local(
        self,
        audio_data: bytes,
        filename: str,
        langue: Optional[str],
        local_model: str = "base",
    ) -> str:
        """Transcription 100% locale via le package openai-whisper.

        Le modèle est chargé une seule fois puis mis en cache (clé : taille),
        ce qui accélère fortement les transcriptions suivantes.
        """
        import whisper

        suffix = os.path.splitext(filename)[1] or ".wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            kwargs: Dict[str, Any] = {"fp16": False}
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
    def statut_transcription(cls) -> Dict[str, Any]:
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

        if api_key and openai_ok:
            backend = "openai"
        elif whisper_local_ok:
            backend = "local"
        else:
            backend = None

        return {
            "disponible": backend is not None,
            "backend": backend,
            "api_key": bool(api_key),
            "openai_installe": openai_ok,
            "whisper_local_installe": whisper_local_ok,
            "modeles": list(cls.MODELES_TRANSCRIPTION),
            "modeles_locaux": list(cls.MODELES_LOCAUX),
            "formats": list(cls.FORMATS_AUDIO_SUPPORTES),
            "taille_max_mo": cls.TAILLE_MAX_AUDIO_MO,
        }

    # ========================================================================
    # EXTRACTION DES ALERTES
    # ========================================================================

    def _extraire_alertes(self, texte: str) -> List[str]:
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

    def _extraire_plan(self, texte: str) -> List[str]:
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
            r'objectif', r'recommand', r'conseil'
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

        # Vérifier si le sujet est déjà couvert par les plans extraits
        plan_sujets = " ".join(plan).lower()
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

        if not plan:
            plan.append("📌 Surveillance standard au quart")
            plan.append("📌 Réévaluation selon protocole")

        return plan

    # ========================================================================
    # MAPPING CODES NAA
    # ========================================================================

    def _mapper_codes_naa(self, texte: str) -> List[Dict]:
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
            "IM": "injection",
            "SC": "injection",
            "SQ": "injection",
            "perfusion": "perfusion",
            "voie veineuse": "perfusion",
            "cathéter": "perfusion",
            "glycémie": "surveillance",
            "glycémie capillaire": "surveillance",
            "SpO2": "surveillance",
            "saturation": "surveillance",
            "surveillance": "surveillance",
            "éducation": "education",
            "éduquer": "education",
            "douleur": "douleur",
            "EVA": "douleur",
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

    def _extraire_medicaments(self, texte: str) -> List[Dict]:
        """Tente d'extraire TOUTES les informations sur les médicaments (findall)."""
        medicaments = []
        
        # Trouver TOUS les médicaments avec dose (pas seulement le premier)
        for match in self.regex_medicament.finditer(texte):
            nom = match.group(1).strip()
            dose = match.group(2)
            unite = match.group(3)
            # Éviter les doublons
            if not any(m["nom"].lower() == nom.lower() for m in medicaments):
                medicaments.append({
                    "nom": nom,
                    "dose": dose,
                    "unite": unite
                })

        # Recherche générique de noms de médicaments courants (FR + NL).
        # Liste partagée avec le priming de la transcription (MEDICAMENTS_COURANTS),
        # organisée par classe thérapeutique, variantes orthographiques FR/NL incluses.
        meds_courants = list(self.MEDICAMENTS_COURANTS)
        
        texte_lower = texte.lower()
        for med in meds_courants:
            if med in texte_lower:
                if not any(m["nom"].lower() == med.lower() for m in medicaments):
                    medicaments.append({"nom": med.capitalize(), "dose": "N/A", "unite": ""})

        return medicaments

    # ========================================================================
    # TRANSMISSIONS SBAr
    # ========================================================================

    def _generer_transmissions(self, texte: str, rapport: Dict) -> List[Dict]:
        """Génère une transmission structurée en format SBAr."""
        transmission = {
            "format": "SBAr",
            "S_Situation": self._resumer_situation(rapport),
            "B_Contexte": self._resumer_contexte(texte),
            "A_Appreciation": self._resumer_appreciation(rapport),
            "R_Recommandation": "\n".join(rapport.get("plan", [])),
        }
        return [transmission]

    def _resumer_situation(self, rapport: Dict) -> str:
        """Résume la situation actuelle du patient."""
        patient = rapport.get("patient", {})
        nom = patient.get("prenom", "") + " " + patient.get("nom", "")
        chambre = patient.get("chambre", "")
        
        situation = f"Patient {nom}, {chambre}."
        
        etat = rapport.get("evaluation", {}).get("État général", "")
        if etat:
            situation += f" {etat}"
        
        alertes = rapport.get("alertes", [])
        if alertes:
            situation += f" Alertes: {len(alertes)} point(s) de vigilance."
        
        return situation

    def _resumer_contexte(self, texte: str) -> str:
        """Résume le contexte clinique."""
        # Extraire les signes vitaux comme contexte
        contexte_parts = []
        
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
        
        return ", ".join(contexte_parts) if contexte_parts else "Voir rapport complet."

    def _resumer_appreciation(self, rapport: Dict) -> str:
        """Résume l'appréciation clinique."""
        soins = rapport.get("soins", [])
        alertes = rapport.get("alertes", [])
        
        appreciation = f"{len(soins)} soin(s) réalisé(s)."
        
        if alertes:
            appreciation += f" {len(alertes)} alerte(s) à surveiller."
        else:
            appreciation += " Aucune alerte majeure."
        
        return appreciation

    # ========================================================================
    # UTILITAIRES
    # ========================================================================

    def exporter_json(self, rapport: Dict) -> str:
        """Exporte le rapport en format JSON."""
        return json.dumps(rapport, indent=2, ensure_ascii=False)

    def exporter_texte_lisible(self, rapport: Dict) -> str:
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

    def generer_rapport_structure(self, patient_data: Dict[str, Any], evaluation: Dict, soins: List[str], alertes: List[str], plan: List[str]) -> Dict[str, Any]:
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

    def _evaluation_vide(self) -> Dict:
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

    def valider_rapport(self, rapport: Dict) -> tuple[bool, List[str]]:
        """
        Valide la complétude du rapport.
        Retourne (est_valide, liste_des_warnings).
        """
        warnings = []
        
        # Vérifier les infos patient
        patient = rapport.get("patient", {})
        if not patient.get("nom"):
            warnings.append("⚠️ Nom du patient manquant")
        if not patient.get("prenom"):
            warnings.append("⚠️ Prénom du patient manquant")
        
        # Vérifier les signes vitaux
        sv = rapport.get("evaluation", {}).get("Signes vitaux", {})
        if not sv:
            warnings.append("⚠️ Aucun signe vital enregistré")
        
        # Vérifier les soins
        if not rapport.get("soins"):
            warnings.append("⚠️ Aucun soin documenté")
        
        # Vérifier le plan
        if not rapport.get("plan"):
            warnings.append("⚠️ Aucun plan de soins défini")
        
        return (len(warnings) == 0, warnings)
