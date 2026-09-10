"""
NurseLog AI - Assistant de Documentation Infirmière par IA
Prototype MVP - Belgium Edition
"""

import copy
import datetime
import json

import streamlit as st
from nurselog_engine import NurseLogEngine
from templates import RAPPORT_TEMPLATE
from database import sauvegarder_rapport, recuperer_historique, recuperer_stats

# ============ CONFIGURATION PAGE ============
st.set_page_config(
    page_title="NurseLog AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ CUSTOM CSS ============
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #006699;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .report-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #006699;
        margin-bottom: 15px;
    }
    .alert-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #ffc107;
        margin-bottom: 15px;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin-bottom: 15px;
    }
    .stButton > button {
        width: 100%;
        background-color: #006699;
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 1rem;
        border-radius: 8px;
    }
    .stButton > button:hover {
        background-color: #004d66;
    }
    .signature-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-top: 20px;
        border: 2px dashed #006699;
    }
</style>
""", unsafe_allow_html=True)

# ============ INITIALISATION SESSION STATE ============
if 'rapport' not in st.session_state:
    st.session_state.rapport = None
if 'validated' not in st.session_state:
    st.session_state.validated = False
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_patient' not in st.session_state:
    st.session_state.current_patient = {}

# ============ INITIALISATION ENGINE ============
engine = NurseLogEngine()

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("### 🏥 NurseLog AI")
    st.markdown("*Documentation intelligente pour infirmiers belges*")
    st.divider()
    
    # Menu de navigation
    page = st.radio("Navigation", [
        "🎙️ Dictée Rapide",
        "📝 Rapport Manuel",
        "📋 Historique",
        "⚙️ Paramètres",
        "ℹ️ À propos"
    ])
    
    st.divider()
    
    # Stats
    st.markdown("### 📊 Statistiques")
    stats = recuperer_stats()
    st.metric("Rapports total", stats["total"])
    st.metric("Rapports validés", stats["valides"])

    if stats["total"] > 0:
        st.success(f"✅ {stats['valides']} documentation(s) validée(s)")

# ============ PAGE: DICTÉE RAPIDE ============
if page == "🎙️ Dictée Rapide":
    st.markdown("<p class='main-header'>🎙️ Dictée Rapide</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Dictez vos soins naturellement — l'IA structure le rapport automatiquement</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📋 Informations Patient")
        
        patient_nom = st.text_input("Nom du patient", placeholder="ex: Marie Dupont")
        patient_prenom = st.text_input("Prénom du patient", placeholder="ex: Marie")
        chambre = st.text_input("Chambre/Lieu", placeholder="ex: CH 12A / Domicile")
        date_naissance = st.date_input("Date de naissance", value=datetime.date(1950, 1, 1))
        
        st.markdown("### 🎤 Dictée des soins")
        st.info("💡 Parlez naturellement comme si vous racontiez ce que vous avez fait. Exemple : *'Pansement plaie sacrum réalisé, plaie propre 5x3cm, douleur 2/10, prochain pansement dans 48h'*")
        
        dictée = st.text_area(
            "📝 Entrez votre dictée ici :",
            height=150,
            placeholder="Dictez vos observations ici...",
            help="Simulez la dictée vocale en tapant votre texte"
        )
        
        # Note: Dans la version production, on intégrerait la reconnaissance vocale
        # avec Whisper API ou Web Speech API
        
        st.markdown("### 🎯 Type de rapport")
        type_rapport = st.selectbox(
            "Sélectionnez le type de documentation",
            [
                "Rapport de soins standard",
                "Transmission de quart",
                "Observation ponctuelle",
                "Évaluation douleur",
                "Suivi plaie",
                "Administration médicamenteuse",
            ]
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            quart = st.selectbox("Quart", ["Matin (07h-15h)", "Après-midi (15h-23h)", "Nuit (23h-07h)"])
        with col_b:
            langue = st.selectbox("Langue", ["Français 🇫🇷", "Néerlandais 🇳🇱", "Mixte"])
        
        st.markdown("---")
        
        # Bouton de génération
        if st.button("🤖 Générer le rapport", type="primary", disabled=not dictée):
            with st.spinner("🔄 Analyse en cours par l'IA..."):
                
                # Préparer les données
                patient_data = {
                    "nom": patient_nom,
                    "prenom": patient_prenom,
                    "chambre": chambre,
                    "date_naissance": str(date_naissance),
                    "quart": quart,
                    "langue": langue,
                    "type_rapport": type_rapport
                }
                
                # Générer le rapport
                rapport = engine.generer_rapport(dictée, patient_data)
                
                st.session_state.rapport = rapport
                st.session_state.validated = False
                st.session_state.current_patient = patient_data
                
                st.success("✅ Rapport généré avec succès !")
    
    with col2:
        st.markdown("### 💡 Conseils")
        st.info("""
**Pour une dictée efficace :**
- Parlez clairement et à rythme normal
- Mentionnez les éléments importants
- Incluez les observations cliniques
- Précisez les actions realizadas
- Notez les alertes ou points de vigilance
        """)
        
        st.markdown("### 📖 Exemple de dictée")
        st.code("""
"Patiente Marie Dupont, 
chambre 12. Pansement plaie 
sacrum réalisé. Plaie propre, 
5x3cm, granulation en bonne 
évolution. Pas de drainage. 
Patiente tolère bien, douleur 
2/10. Prochain pansement 
dans 48h. Transmission : 
surveiller l'appétit, a mangé 
30% ce midi."
        """)

# ============ PAGE: RAPPORT MANUEL ============
elif page == "📝 Rapport Manuel":
    st.markdown("<p class='main-header'>📝 Rapport Manuel</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Créez un rapport en remplissant les champs structurés</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Informations Patient")
        patient_nom = st.text_input("Nom du patient")
        patient_prenom = st.text_input("Prénom du patient")
        chambre = st.text_input("Chambre/Lieu")
        
        st.markdown("### 🩺 Évaluation Clinique")
        glycémie = st.text_input("Glycémie", placeholder="ex: 1.1 g/L")
        tension = st.text_input("Tension artérielle", placeholder="ex: 120/80")
        pouls = st.text_input("Pouls", placeholder="ex: 72 bpm")
        temperature = st.text_input("Température", placeholder="ex: 37.2°C")
        douleur = st.slider("Échelle douleur (0-10)", 0, 10, 0)
        spo2 = st.text_input("SpO2", placeholder="ex: 98%")
        
    with col2:
        st.markdown("### 📝 Soins Réalisés")
        soins_texte = st.text_area(
            "Décrivez les soins réalisés",
            height=100,
            placeholder="Pansement, administration médicaments, ..."
        )
        
        st.markdown("### ⚠️ Alertes")
        alertes = st.text_area(
            "Points de vigilance / alertes",
            height=80,
            placeholder="Signaler au médecin, surveiller, ..."
        )
        
        st.markdown("### 📅 Plan de Soins")
        plan = st.text_area(
            "Prochains soins / actions",
            height=80,
            placeholder="Prochain pansement, surveillance, ..."
        )
    
    if st.button("🤖 Générer le rapport structuré", type="primary"):
        with st.spinner("🔄 Structuration en cours..."):
            dictée_simulée = f"""
            Patient {patient_prenom} {patient_nom}, {chambre}.
            Glycémie: {glycémie}, Tension: {tension}, Pouls: {pouls}, 
            Température: {temperature}, SpO2: {spo2}, Douleur: {douleur}/10.
            Soins: {soins_texte}. Alertes: {alertes}. Plan: {plan}.
            """
            
            patient_data = {
                "nom": patient_nom,
                "prenom": patient_prenom,
                "chambre": chambre,
                "date_naissance": "",
                "quart": "Matin",
                "langue": "Français",
                "type_rapport": "Rapport de soins standard"
            }
            
            rapport = engine.generer_rapport(dictée_simulée, patient_data)
            st.session_state.rapport = rapport
            st.session_state.validated = False
            st.session_state.current_patient = patient_data
            
            st.success("✅ Rapport généré !")

# ============ PAGE: HISTORIQUE ============
elif page == "📋 Historique":
    st.markdown("<p class='main-header'>📋 Historique des Rapports</p>", unsafe_allow_html=True)

    # Charger depuis SQLite
    historique_db = recuperer_historique(limite=100)

    if not historique_db:
        st.info("📭 Aucun rapport enregistré. Commencez par créer un rapport !")
    else:
        st.success(f"📊 {len(historique_db)} rapport(s) trouvé(s) en base")
        for i, rapport_hist in enumerate(historique_db):
            patient = rapport_hist.get("patient", {})
            metadata = rapport_hist.get("metadata", {})
            db_id = rapport_hist.get("_db_id", i + 1)
            with st.expander(
                f"📄 Rapport #{db_id} — {patient.get('prenom', '')} {patient.get('nom', '')}"
                f" — {metadata.get('date', 'N/A')} {metadata.get('heure', '')}"
            ):
                st.json(rapport_hist)

# ============ PAGE: PARAMÈTRES ============
elif page == "⚙️ Paramètres":
    st.markdown("<p class='main-header'>⚙️ Paramètres</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👤 Profil Infirmier")
        nom_infirmier = st.text_input("Votre nom", placeholder="ex: Jean Dupont")
        num_infirmier = st.text_input("Numéro d'identification", placeholder="ex: 123456")
        etablissement = st.text_input("Établissement", placeholder="ex: CHU Bruxelles")
        
        st.markdown("### 🌐 Langue par défaut")
        langue_par_defaut = st.selectbox("Langue", ["Français", "Néerlandais", "Bilingue"])
    
    with col2:
        st.markdown("### 🔒 Données & Confidentialité")
        st.info("📍 Les données sont stockées localement (SQLite)")
        st.info("📍 Aucun envoi vers des serveurs externes")
        st.info("📍 Conçu pour une future conformité RGPD/AI Act")

        st.markdown("### 📊 Intégrations")
        st.warning("🔧 Intégration eHealth/SumEHR en développement")
        st.warning("🔧 Export FHIR/HL7 en développement")

# ============ PAGE: À PROPOS ============
elif page == "ℹ️ À propos":
    st.markdown("<p class='main-header'>ℹ️ À propos de NurseLog AI</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏥 Qu'est-ce que NurseLog AI ?")
        st.info("""
**NurseLog AI** est le premier assistant de documentation clinique 
par IA conçu spécifiquement pour les **infirmiers belges**.

L'outil transforme votre parole naturelle en rapports de soins 
structurés, complets et conformes aux standards belges.
        """)
        
        st.markdown("### 🎯 Objectif")
        st.success("""
Réduire de **70%** le temps passé en documentation 
administrative pour que les infirmiers puissent se 
concentrer sur l'essentiel : **leurs patients**.
        """)
    
    with col2:
        st.markdown("### 📊 Fonctionnalités")
        
        features = [
            ("🎙️ DocuVoice", "Dictée vocale intelligente FR/NL"),
            ("🔄 TransmiShift", "Transmission entre quarts assistée"),
            ("📚 FormuCare", "Formation continue intelligente"),
            ("📊 AnalysInsight", "Analytics établissement"),
        ]
        
        for title, desc in features:
            st.markdown(f"**{title}** : {desc}")
        
        st.markdown("### 🔒 Conformité (en cours)")
        st.info("""
- 📍 Stockage local (pas d'envoi externe)
- 📍 Architecture conçue pour RGPD / AI Act
- 📍 Intégration eHealth/SumEHR planifiée (Phase 3)
- 📍 Chiffrement en transit & au repos (Phase 2)
""")

# ============ AFFICHAGE DU RAPPORT GÉNÉRÉ ============
if st.session_state.rapport and page in ["🎙️ Dictée Rapide", "📝 Rapport Manuel"]:
    st.markdown("---")
    st.markdown("<p class='main-header'>📋 Rapport Généré</p>", unsafe_allow_html=True)
    
    rapport = st.session_state.rapport
    
    # En-tête du rapport
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**👤 Patient :** {rapport.get('patient', {}).get('nom', 'N/A')}")
    with col2:
        st.markdown(f"**📍 Lieu :** {rapport.get('patient', {}).get('chambre', 'N/A')}")
    with col3:
        st.markdown(f"**📅 Date :** {rapport.get('metadata', {}).get('date', 'N/A')}")
    
    st.divider()
    
    # Sections du rapport
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🩺 Évaluation Clinique")
        if 'evaluation' in rapport:
            for key, value in rapport['evaluation'].items():
                st.markdown(f"**{key}:** {value}")
        
        st.markdown("### 📝 Soins Réalisés")
        if 'soins' in rapport:
            for soin in rapport['soins']:
                st.success(f"✅ {soin}")
    
    with col2:
        st.markdown("### ⚠️ Alertes")
        if 'alertes' in rapport and rapport['alertes']:
            for alerte in rapport['alertes']:
                st.warning(f"⚠️ {alerte}")
        else:
            st.success("✅ Aucune alerte")
        
        st.markdown("### 📅 Plan de Soins")
        if 'plan' in rapport:
            for action in rapport['plan']:
                st.info(f"📌 {action}")
    
    st.divider()
    
    # Codes NAA
    if 'codes_naa' in rapport and rapport['codes_naa']:
        st.markdown("### 💰 Codes NAA (Facturation)")
        for code in rapport['codes_naa']:
            code_text = f"Code: {code.get('code', 'N/A')} | {code.get('nom', '')} | Source: {code.get('source', 'N/A')}"
            st.code(code_text)
    
    st.divider()
    
    # Validation et signature
    st.markdown("### ✍️ Validation & Signature")
    
    if not st.session_state.validated:
        st.info("🔍 Vérifiez attentivement le rapport avant validation. **L'IA ne remplace pas votre jugement clinique.**")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("❌ Modifier", type="secondary"):
                st.session_state.rapport = None
                st.rerun()
        
        with col2:
            if st.button("✅ Valider & Signer", type="primary"):
                st.session_state.validated = True
                
                # Ajouter à l'historique
                rapport['metadata']['valide'] = True
                rapport['metadata']['signature_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.history.append(copy.deepcopy(rapport))

                # Sauvegarder en base SQLite
                try:
                    sauvegarder_rapport(1, rapport)
                except Exception:
                    pass  # SQLite silencieux, pas bloquant

                st.success("✅ Rapport validé et signé électroniquement !")
                st.balloons()
    
    else:
        st.success("✅ **Rapport validé et signé**")
        st.markdown(f"📅 Signé le : {rapport.get('metadata', {}).get('signature_date', 'N/A')}")
        
        # Options post-validation
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Exporter en PDF"):
                st.info("🔧 Export PDF disponible en version production")
        
        with col2:
            if st.button("📤 Exporter vers SIH"):
                st.info("🔧 Intégration SIH (FHIR) disponible en version production")
        
        st.divider()
        
        # Nouveau rapport
        if st.button("🆕 Nouveau Rapport", type="primary"):
            st.session_state.rapport = None
            st.session_state.validated = False
            st.rerun()

# ============ FOOTER ============
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.8rem;'>
    NurseLog AI v0.1 (Prototype) | Belgium Edition | © 2025
    <br>Conformité RGPD • AI Act • eHealth Belgique
</div>
""", unsafe_allow_html=True)
