"""
conftest.py — Configuration pytest pour NurseLog AI
Assure que src/ est dans le path Python pour tous les tests.
"""

import os
import sys

# Ajouter le dossier src au path
src_path = os.path.join(os.path.dirname(__file__), "..", "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
