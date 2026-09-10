"""
Configuration pytest pour NurseLog AI
"""

import sys
import os

# Ajouter le dossier src au PYTHONPATH pour les imports
src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, src_dir)
