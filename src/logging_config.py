"""
logging_config.py — Logging structuré et audit trail pour NurseLog AI.

Fournit :
- Un logger JSON structuré (compatible avec les agrégateurs de logs)
- Un audit trail dédié aux actions infirmières (création, validation, signature)
- Configuration centralisée du niveau de log

Usage :
    from src.logging_config import get_logger, audit_log

    logger = get_logger("nurselog.engine")
    logger.info("rapport_genere", extra={"patient_id": "P-001", "sections": 5})

    audit_log("rapport_cree", infirmier="Marie Dupont", patient="Jean Martin",
              rapport_id="R-2025-001", langue="fr")
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ============================================================
# Configuration
# ============================================================

LOG_DIR = Path(os.environ.get("NURSELOG_LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "nurselog.log"
AUDIT_FILE = LOG_DIR / "audit.jsonl"

DEFAULT_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


# ============================================================
# JSON Formatter
# ============================================================

class JSONFormatter(logging.Formatter):
    """Formate les logs en JSON structuré (une ligne = un événement)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Champs additionnels via extra={}
        for key in ("patient_id", "infirmier", "rapport_id", "langue", "duree_ms", "erreur"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # Erreur si présente
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


# ============================================================
# Audit Trail (JSONL)
# ============================================================

class AuditHandler(logging.Handler):
    """Handler dédié à l'audit trail — écrit en JSONL (une ligne JSON par événement)."""

    def __init__(self, filepath: Path):
        super().__init__()
        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.setFormatter(JSONFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            self.handleError(record)


# ============================================================
# Setup
# ============================================================

_configured = False


def _ensure_configured() -> None:
    """Configure les loggers une seule fois (idempotent)."""
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Logger principal
    root = logging.getLogger("nurselog")
    root.setLevel(getattr(logging, DEFAULT_LEVEL, logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    root.addHandler(console_handler)

    # Fichier handler (rotation)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    # Audit logger dédié
    audit_logger = logging.getLogger("nurselog.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Ne pas propager au root
    audit_handler = AuditHandler(AUDIT_FILE)
    audit_logger.addHandler(audit_handler)

    _configured = True


def get_logger(name: str = "nurselog") -> logging.Logger:
    """Retourne un logger configuré sous le namespace 'nurselog'."""
    _ensure_configured()
    if not name.startswith("nurselog"):
        name = f"nurselog.{name}"
    return logging.getLogger(name)


def audit_log(action: str, **kwargs: Any) -> str:
    """
    Enregistre un événement dans l'audit trail.

    Args:
        action: Nom de l'action (ex: "rapport_cree", "rapport_valide", "signature")
        **kwargs: Champs additionnels (infirmier, patient, rapport_id, langue, etc.)

    Returns:
        L'ID unique de l'événement d'audit.
    """
    _ensure_configured()
    event_id = str(uuid.uuid4())

    logger = logging.getLogger("nurselog.audit")
    logger.info(
        action,
        extra={
            "event_id": event_id,
            "action": action,
            **kwargs,
        },
    )
    return event_id


# ============================================================
# Context manager pour mesurer la durée
# ============================================================

class timed:  # noqa: N801 — nom public stable, utilisé dans les tests
    """Context manager qui logge la durée d'un bloc de code.

    Usage :
        with timed("transcription", logger=logger):
            ...
    """

    def __init__(self, operation: str, logger: logging.Logger | None = None):
        self.operation = operation
        self.logger = logger or get_logger("nurselog")
        self._start: float = 0.0

    def __enter__(self) -> timed:
        import time
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        import time
        duree_ms = round((time.perf_counter() - self._start) * 1000, 1)
        if exc_type is None:
            self.logger.info(
                f"{self.operation} terminée",
                extra={"duree_ms": duree_ms, "operation": self.operation},
            )
        else:
            self.logger.error(
                f"{self.operation} échouée",
                extra={
                    "duree_ms": duree_ms,
                    "operation": self.operation,
                    "erreur": str(exc_val),
                },
            )


# ============================================================
# Export pour tests
# ============================================================

def reset_for_tests() -> None:
    """Réinitialise la configuration (à utiliser uniquement dans les tests)."""
    global _configured
    _configured = False
    # Supprimer les handlers existants
    root = logging.getLogger("nurselog")
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    audit = logging.getLogger("nurselog.audit")
    for handler in audit.handlers[:]:
        audit.removeHandler(handler)
        handler.close()
