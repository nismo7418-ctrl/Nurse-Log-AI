#!/usr/bin/env python3
"""
Validation script pour vérifier l'implémentation complète de NurseLog AI
"""

import sys
import os

# Ajouter le dossier src au chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def validate_requirements():
    """Vérifie que tous les modules nécessaires sont présents"""
    try:
        import streamlit
        import sqlite3
        import json
        from database import initialiser_base, sauvegarder_rapport, recuperer_historique
        from nurselog_engine import NurseLogEngine
        print("OK - Tous les modules de base sont disponibles")
        return True
    except ImportError as e:
        print(f"ERROR - Module manquant: {e}")
        return False

def validate_database():
    """Valide la structure de base de données"""
    try:
        from database import initialiser_base, DATABASE_PATH
        import os
        
        # Vérifier que le fichier existe
        if not os.path.exists(DATABASE_PATH):
            print("WARN - Base de données non créée, mais ce n'est pas anormal")
        
        # Initialiser la base pour les tests
        initialiser_base()
        print("OK - Structure de base de données valide")
        return True
    except Exception as e:
        print(f"ERROR - Erreur dans la base de données: {e}")
        return False

def validate_engine():
    """Valide le moteur d'IA"""
    try:
        from nurselog_engine import NurseLogEngine
        engine = NurseLogEngine()
        
        # Vérifier qu'il peut être instancié
        assert hasattr(engine, 'version')
        assert hasattr(engine, 'generer_rapport')
        print("OK - Moteur d'IA fonctionnel")
        return True
    except Exception as e:
        print(f"ERROR - Erreur dans le moteur: {e}")
        return False

def validate_features():
    """Vérifie que toutes les fonctionnalités clés sont implémentées"""
    
    # Vérifier la présence des fichiers clés
    required_files = [
        'src/app.py',
        'src/database.py', 
        'src/nurselog_engine.py',
        'src/templates.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"ERROR - Fichiers manquants: {missing_files}")
        return False
    else:
        print("OK - Tous les fichiers principaux présents")
        return True

def validate_tests():
    """Vérifie que les tests passent"""
    try:
        import subprocess
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '--tb=short'], 
                              capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("OK - Tous les tests passent")
            return True
        else:
            print(f"ERROR - Certains tests échouent:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR - Erreur lors de l'exécution des tests: {e}")
        return False

def main():
    """Fonction principale de validation"""
    print("Validation de l'implémentation NurseLog AI")
    print("=" * 50)
    
    checks = [
        validate_requirements,
        validate_database,
        validate_engine,
        validate_features,
        validate_tests
    ]
    
    results = []
    for check in checks:
        print(f"\n--- {check.__name__} ---")
        result = check()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("Résultats de validation:")
    
    all_passed = all(results)
    if all_passed:
        print("SUCCESS - Tous les tests passent! L'implémentation est complète.")
        return 0
    else:
        print("FAILED - Certaines vérifications ont échoué.")
        return 1

if __name__ == "__main__":
    sys.exit(main())