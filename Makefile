# ============================================================
# Makefile — NurseLog AI
# Tâches courantes pour le développement
# ============================================================

.PHONY: help test test-cov test-single lint format run clean docker-build docker-run

.DEFAULT_GOAL := help

help: ## Afficher l'aide
	@echo "NurseLog AI — Tâches disponibles"
	@echo ""
	@echo "  make test          Exécuter tous les tests"
	@echo "  make test-cov      Tests avec couverture"
	@echo "  make test-single F=test_engine.py   Test unique"
	@echo "  make lint          Linting (ruff)"
	@echo "  make format        Formater le code (ruff)"
	@echo "  make run           Lancer l'application Streamlit"
	@echo "  make clean         Nettoyer les artefacts"
	@echo "  make docker-build  Construire l'image Docker"
	@echo "  make docker-run    Lancer le conteneur Docker"
	@echo ""

test: ## Exécuter tous les tests
	pytest tests/ -v --tb=short

test-cov: ## Tests avec rapport de couverture
	pytest tests/ -v --cov=src --cov-report=term-missing

test-single: ## Exécuter un seul fichier de test (usage: make test-single F=test_engine.py)
	pytest $(F) -v --tb=short

lint: ## Linting avec ruff
	ruff check src/ tests/ app.py

format: ## Formater le code avec ruff
	ruff format src/ tests/ app.py
	ruff check --fix src/ tests/ app.py

run: ## Lancer l'application Streamlit
	streamlit run app.py

clean: ## Nettoyer les artefacts de build et cache
	rm -rf src/__pycache__ tests/__pycache__ .pytest_cache .coverage htmlcov/
	rm -rf dist/ build/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Artefacts nettoyés"

docker-build: ## Construire l'image Docker
	docker build -t nurselog-ai:latest .

docker-run: ## Lancer le conteneur Docker
	docker run -p 8501:8501 -v $(PWD)/data:/app/data --name nurselog-ai nurselog-ai:latest
