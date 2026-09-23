"""
NurseLog AI - Templates de Rapports de Soins (Standards Belges)
---------------------------------------------------------------
Conforme aux recommandations KCE, eHealth Belgique, et pratiques
hospitalières belges (CHU, EMS, soins à domicile, infirmiers libéraux).
"""

# ============================================================================
# TEMPLATE PRINCIPAL DU RAPPORT
# ============================================================================

RAPPORT_TEMPLATE = {
    "patient": {
        "nom": "",
        "prenom": "",
        "date_naissance": "",
        "chambre": "",
        "numero_dossier": ""
    },
    "metadata": {
        "date": "",
        "heure": "",
        "quart": "",
        "infirmier": "",
        "type_rapport": "",
        "langue": "Français",
        "valide": False,
        "signature_date": ""
    },
    "evaluation": {
        "Signes vitaux": {},
        "Confort douleur": "",
        "État général": "",
        "Nutrition hydratation": "",
        "Mobilité": "",
        "Pele muqueuses": "",
        "Eliminations": "",
        "État psychologique": ""
    },
    "soins": [],
    "alertes": [],
    "plan": [],
    "codes_naa": [],
    "medicaments": [],
    "transmissions": []
}

# ============================================================================
# TEMPLATES PAR TYPE DE RAPPORT
# ============================================================================

TEMPLATES_TYPES = {
    "Rapport de soins standard": {
        "sections_requises": [
            "Signes vitaux", "État général", "Soins réalisés", "Plan de soins"
        ],
        "structure": {
            "en_tete": "RAPPORT DE SOINS INFIRMIERS",
            "sections": [
                "Identification patient",
                "Évaluation clinique",
                "Soins réalisés",
                "Alertes et observations",
                "Plan de soins",
                "Signatures"
            ]
        }
    },
    "Transmission de quart": {
        "sections_requises": [
            "État général", "Soins du quart", "Transmissions", "Vigilance"
        ],
        "structure": {
            "en_tete": "TRANSMISSION DE QUART",
            "sections": [
                "Situation générale",
                "Évolution du quart",
                "Soins réalisés",
                "Points de vigilance",
                "Transmissions orales",
                "Plan quart suivant"
            ]
        }
    },
    "Observation ponctuelle": {
        "sections_requises": [
            "Motif", "Observation", "Action"
        ],
        "structure": {
            "en_tete": "OBSERVATION PONCTUELLE",
            "sections": [
                "Motif de l'observation",
                "Constatations",
                "Actions entreprises",
                "Suite à donner"
            ]
        }
    },
    "Évaluation douleur": {
        "sections_requises": [
            "Douleur", "Localisation", "Intensité", "Traitement", "Réévaluation"
        ],
        "structure": {
            "en_tete": "ÉVALUATION DE LA DOULEUR (EVA/EN)",
            "sections": [
                "Localisation et caractère",
                "Intensité (EVA 0-10)",
                "Facteurs aggravants/allégeants",
                "Traitement administré",
                "Réévaluation post-traitement",
                "Impact qualité de vie"
            ]
        }
    },
    "Suivi plaie": {
        "sections_requises": [
            "Localisation", "Dimensions", "Aspect", "Traitement", "Prochain pansement"
        ],
        "structure": {
            "en_tete": "SUIVI PLAIE — DOCUMENTATION",
            "sections": [
                "Localisation et typologie",
                "Dimensions (L x l x prof)",
                "Fond de plaie",
                "Bords et périphérie",
                "Drainage",
                "Douleur associée",
                "Traitement appliqué",
                "Classification (Brussels Wound Healing Symposium)",
                "Prochain pansement prévu"
            ]
        }
    },
    "Administration médicamenteuse": {
        "sections_requises": [
            "Médicament", "Posologie", "Voie", "Heure", "Réaction"
        ],
        "structure": {
            "en_tete": "ADMINISTRATION MÉDICAMENTEUSE",
            "sections": [
                "Nom du médicament",
                "Dose et voie d'administration",
                "Heure d'administration",
                "Vérification (5 droits)",
                "Réaction/effets indésirables",
                "Éducation patient"
            ]
        }
    }
}

# ============================================================================
# VOCABULAIRE MÉDICAL BELGE (Français + Néerlandais)
# ============================================================================

VOCABULAIRE = {
    "signes_vitaux": {
        "tension": ["tension", "TA", "tension artérielle", "blood pressure", "bloeddruk"],
        "pouls": ["pouls", "fréquence cardiaque", "FC", "pulse", "pols"],
        "temperature": ["température", "T°", "fièvre", "fever", "temperatuur"],
        "spo2": ["SpO2", "saturation", "oxygénation", "saturatie"],
        "respiration": ["respiration", "fréquence respiratoire", "FR", "respiratie"],
        "douleur": ["douleur", "douleurs", "EVA", "EN", "échelle visuelle analogique", "pijn"],
        "glycemie": ["glycémie", "glycémie capillaire", "glycémie veineuse", "bloedsuiker"]
    },
    "soins_courants": {
        "pansement": ["pansement", "changement de pansement", "wondverzorging"],
        "injection": ["injection", "IM", "IV", "SC", "SQ", "IT", "injectie"],
        "perfusion": ["perfusion", "voies veineuses", "cathéter", "catheter"],
        "sondage": ["sonde urinaire", "sondage", "cathéter urinaire", "sonde"],
        "aspiration": ["aspiration", "aspirations", "suigen"],
        "positionnement": ["positionnement", "retournement", "mobilisation", "positionering"],
        "toilette": ["toilette", "soins d'hygiène", "nettoyage", "hygiëne"],
        "nutrition": ["alimentation", "nutrition", "sonde nasogastrique", "PEG", "voeding"],
        "elimination": ["elimination", "diabète", "miction", "defécation", "Eliminatie"],
        "surveillance": ["surveillance", "monitoring", "observatie"]
    },
    "alertes": {
        "chute": ["chute", "risque chute", "val", "valrisico"],
        "allergie": ["allergie", "allergique", "allergie"],
        "isolement": ["isolement", "contact", "gouttelettes", "isolement"],
        "contrainte": ["contrainte", "contention", "dwang"],
        "fin_de_vie": ["fin de vie", "soins palliatifs", "sédatif", "eind van leven", "palliatieve"],
        "alerte_medecin": ["alerter le médecin", "informer le médecin", "médecin notifié", "arts informeren"],
        "urgence": ["urgence", "urgence vitale", "deterioration", "spoed"]
    },
    "etats_generaux": {
        "conscient": ["conscient", "éveillé", "alerte", "bewust"],
        "orientation": ["orienté", "désorienté", "orientation", "georienteerd"],
        "apetite": ["appétit", "apétit", "mauvais appétit", "anorexie", "appetiet"],
        "sommeil": ["sommeil", "insomnie", "somnolence", "slaap"]
    }
}

# ============================================================================
# CODES NAA BELGES (Nomenclature des Actes et Prestations)
# ============================================================================

CODES_NAA_RECONNAISSANCE = {
    "soins_generaux": [
        {"code": "01.001", "nom": "Soins infirmiers de base", "description": "Soins généraux"},
        {"code": "01.005", "nom": "Soins infirmiers élémentaires", "description": "Soins élémentaires"},
    ],
    "pansement": [
        {"code": "01.011", "nom": "Pansement simple", "description": "Pansement peu étendu"},
        {"code": "01.012", "nom": "Pansement moyen", "description": "Pansement d'étendue moyenne"},
        {"code": "01.013", "nom": "Pansement complexe", "description": "Pansement étendu ou complexe"},
        {"code": "01.014", "nom": "Pansement escarre", "description": "Pansement d'escarre/ulcère"},
    ],
    "injection": [
        {"code": "01.021", "nom": "Injection intramusculaire", "description": "IM"},
        {"code": "01.022", "nom": "Injection sous-cutanée", "description": "SC/SQ"},
        {"code": "01.023", "nom": "Injection intraveineuse", "description": "IV"},
    ],
    "perfusion": [
        {"code": "01.031", "nom": "Pose voie veineuse", "description": "Cathéter périphérique"},
        {"code": "01.032", "nom": "Perfusion continue", "description": "Perfusion en continu"},
        {"code": "01.033", "nom": "Perfusion intermittente", "description": "Perfusion en bolus"},
    ],
    "surveillance": [
        {"code": "01.041", "nom": "Surveillance clinique", "description": "Monitoring clinique"},
        {"code": "01.042", "nom": "Glycémie capillaire", "description": "Mesure glycémie"},
        {"code": "01.043", "nom": "Saturation oxygène", "description": "SpO2"},
    ],
    "soins_domicile": [
        {"code": "02.001", "nom": "Infirmier à domicile - Soins", "description": "Soins infirmiers domicile"},
        {"code": "02.002", "nom": "Infirmier à domicile - Urgence", "description": "Soins urgents domicile"},
    ],
    "education": [
        {"code": "01.051", "nom": "Éducation thérapeutique", "description": "Éducation patient"},
    ],
    "douleur": [
        {"code": "01.061", "nom": "Évaluation douleur", "description": "Échelle EVA/EN"},
    ]
}

# ============================================================================
# ÉCHELLES ET OUTILS D'ÉVALUATION BELGES
# ============================================================================

ECHELLES_EVALUATION = {
    "douleur": {
        "EVA": {"echelle": "0-10", "description": "Échelle Visuelle Analogique", "units": "/10"},
        "EN": {"echelle": "0-3", "description": "Échelle Numérique verbale", "categories": ["Aucune", "Légère", "Modérée", "Sévère"]},
        "Echelle_gestuelle": {"categories": ["😊", "🙂", "😐", "😕", "😣"]}
    },
    "risque_chute": {
        "Morse": {"seuil_haut": 45, "description": "Morse Fall Scale"},
    },
    "risque_escarre": {
        "Braden": {"seuil_haut": 12, "description": "Braden Scale", "min": 6, "max": 23},
    },
    "plaie": {
        "classification": [
            "Stade I - Érythème non blanchissant",
            "Stade II - Perte partielle de l'épaisseur",
            "Stade III - Perte totale de l'épaisseur",
            "Stade IV - Atteinte des structures profondes",
            "Non classable",
            "Suspecté brûlure tissulaire"
        ]
    }
}

# ============================================================================
# STRUCTURE DE TRANSMISSION (SBAR belge)
# ============================================================================

STRUCTURE_SBAr = {
    "S_Situation": "Description de la situation actuelle du patient",
    "B_Contexte": "Contexte clinique et historique pertinent",
    "A_Appreciation": "Appréciation de la situation par l'infirmier",
    "R_Recommandation": "Recommandations et actions proposées"
}

# ============================================================================
# TERMES DE QUALITÉ ET INDICATEURS BELGES
# ============================================================================

INDICATEURS_QUALITE = [
    "Temps de réponse appel",
    "Taux d'escarre nosocomiale",
    "Taux de chute sans lésion / avec lésion",
    "Taux d'infection associée aux soins (IAS)",
    "Conformité asepsie",
    "Satisfaction patient",
    "Documentation complète dans les délais"
]

# ============================================================================
# LISTES DE CHOIX PARTAGÉES (UI Streamlit — évite la duplication dans app.py)
# ============================================================================

TYPES_RAPPORT = [
    "Rapport de soins standard",
    "Transmission de quart",
    "Observation ponctuelle",
    "Évaluation douleur",
    "Suivi plaie",
    "Administration médicamenteuse",
]

QUARTS = [
    "Matin (07h-15h)",
    "Après-midi (15h-23h)",
    "Nuit (23h-07h)",
]

LANGUES = [
    "Français",
    "Néerlandais",
    "Mixte",
]
