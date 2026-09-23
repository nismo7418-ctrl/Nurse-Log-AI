"""
Relay audio local — capture micro navigateur → transcription.

Ce module expose un petit serveur HTTP **local uniquement** (127.0.0.1) qui
reçoit les enregistrements audio produits par le widget micro du navigateur
(``st.components.v1.html`` + Web Audio API / ``MediaRecorder``) et les stocke
de façon temporaire pour que le moteur (`NurseLogEngine.transcrire_audio`)
puisse les transcrire.

Conçus pour le principe **local-first / RGPD** du projet :
- Le serveur est borné sur ``127.0.0.1`` → inaccessible depuis le réseau.
- L'audio ne quitte jamais la machine (sauf choix explicite de l'API OpenAI,
  déjà géré par le moteur).
- Aucun package tiers : uniquement la bibliothèque standard Python.

Usage (côté application)::

    from audio_relay import get_audio_relay
    relay = get_audio_relay()          # démarre le serveur (singleton)
    url = relay.url                    # à injecter dans le JS du widget
    ...
    info = relay.get_latest_recording()  # {"path", "taille", "mime", "horodatage"}
    with open(info["path"], "rb") as f:
        texte = engine.transcrire_audio(f.read(), "enregistrement.webm", ...)
"""

from __future__ import annotations

import atexit
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Plafond de taille des uploads (mémoire chargée en une fois dans do_POST)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 Mo — bien au-delà du max de 5 min de dictée

# Mapping type MIME (navigateur) → extension de fichier (reconnue par le moteur)
_MIME_VERS_EXTENSION = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/flac": "flac",
    "audio/x-wav": "wav",
}


def mime_vers_extension(mime: str) -> str:
    """Convertit un type MIME audio en extension de fichier (défaut : webm)."""
    cle = (mime or "").lower().split(";")[0].strip()
    return _MIME_VERS_EXTENSION.get(cle, "webm")


def _supprimer_fichier_silencieux(chemin: str | None) -> None:
    """Supprime un fichier sans jamais lever d'exception."""
    try:
        if chemin and os.path.exists(chemin):
            os.remove(chemin)
    except Exception:
        pass


class _EtatRelay:
    """État partagé (thread-safe) du dernier enregistrement reçu."""

    def __init__(self) -> None:
        self._verrou = threading.Lock()
        self._dernier: dict[str, Any] | None = None

    def definir_dernier(self, info: dict[str, Any]) -> None:
        with self._verrou:
            precedent = self._dernier
            self._dernier = info
        # Libère le fichier de l'enregistrement précédent (on ne garde que le dernier)
        _supprimer_fichier_silencieux(precedent.get("path") if precedent else None)

    def dernier(self) -> dict[str, Any] | None:
        with self._verrou:
            return dict(self._dernier) if self._dernier else None

    def vider(self) -> None:
        with self._verrou:
            precedent, self._dernier = self._dernier, None
        _supprimer_fichier_silencieux(precedent.get("path") if precedent else None)


class AudioRelay:
    """Serveur HTTP local (thread daemon) recevant les enregistrements micro.

    - Borné sur ``127.0.0.1`` (RGPD : pas d'exposition réseau).
    - Port choisi par le système (``port=0``) → pas de conflit.
    - Thread-safe : le thread HTTP écrit, le thread Streamlit lit.
    - Ne conserve que le dernier enregistrement (les précédents sont supprimés).
    """

    _instance: AudioRelay | None = None
    _verrou_instance = threading.Lock()

    def __init__(self, host: str = "127.0.0.1", enregistrer_atexit: bool = False) -> None:
        self._host = host
        self.etat = _EtatRelay()
        self._serveur: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = 0
        self._demarrer()
        if enregistrer_atexit:
            atexit.register(self.arreter)

    # ------------------------------------------------------------------ #
    # Cycle de vie
    # ------------------------------------------------------------------ #
    def _demarrer(self) -> None:
        handler = self._fabrique_handler()
        # port=0 → le système attribue un port libre ; on le relit ensuite.
        self._serveur = ThreadingHTTPServer((self._host, 0), handler)
        self._port = self._serveur.server_address[1]
        self._thread = threading.Thread(target=self._serveur.serve_forever, daemon=True)
        self._thread.start()

    def arreter(self) -> None:
        """Arrête le serveur et nettoie l'enregistrement en cours (idempotent)."""
        if self._serveur is not None:
            try:
                self._serveur.shutdown()
                self._serveur.server_close()
            except Exception:
                pass
            self._serveur = None
            self._thread = None
        self.etat.vider()

    # ------------------------------------------------------------------ #
    # API publique
    # ------------------------------------------------------------------ #
    @property
    def port(self) -> int:
        return self._port

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def is_alive(self) -> bool:
        """Vérifie que le thread HTTP est toujours actif.

        Permet à l'application de détecter un crash silencieux du relay
        (OOM, port fermé, etc.) et d'afficher un message clair.
        """
        return self._thread is not None and self._thread.is_alive()

    def get_latest_recording(self) -> dict[str, Any] | None:
        """Renvoie le dernier enregistrement reçu, ou ``None``.

        Clés : ``path`` (fichier temporaire), ``taille`` (octets),
        ``mime`` (type MIME), ``horodatage`` (epoch).
        """
        return self.etat.dernier()

    @classmethod
    def get_instance(cls) -> AudioRelay:
        """Singleton par processus (survit aux reruns Streamlit)."""
        with cls._verrou_instance:
            if cls._instance is None:
                cls._instance = cls(enregistrer_atexit=True)
            return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Utilitaire de test : libère le singleton (sans arrêter un serveur actif)."""
        with cls._verrou_instance:
            cls._instance = None

    # ------------------------------------------------------------------ #
    # Serveur HTTP
    # ------------------------------------------------------------------ #
    def _fabrique_handler(self):
        relay = self

        class _Handler(BaseHTTPRequestHandler):
            server_version = "NurseLogAudioRelay/1.0"

            def _entetes_cors(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def do_OPTIONS(self) -> None:  # noqa: N802 (nom imposé par http.server)
                self.send_response(204)
                self._entetes_cors()
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                if self.path.split("?")[0] != "/audio":
                    self._repondre(404, {"ok": False, "erreur": "route inconnue"})
                    return
                try:
                    longueur = int(self.headers.get("Content-Length", 0) or 0)
                    if longueur > MAX_UPLOAD_BYTES:
                        self._repondre(
                            413, {"ok": False, "erreur": "fichier trop volumineux"}
                        )
                        return
                    corps = self.rfile.read(longueur) if longueur > 0 else b""
                    if not corps:
                        self._repondre(400, {"ok": False, "erreur": "corps vide"})
                        return
                    mime = self.headers.get("Content-Type", "audio/webm")
                    extension = mime_vers_extension(mime)
                    fd, chemin = tempfile.mkstemp(
                        suffix=f".{extension}", prefix="nurselog_micro_"
                    )
                    with os.fdopen(fd, "wb") as f:
                        f.write(corps)
                    info = {
                        "path": chemin,
                        "taille": len(corps),
                        "mime": mime,
                        "horodatage": time.time(),
                    }
                    relay.etat.definir_dernier(info)
                    self._repondre(
                        200,
                        {"ok": True, "taille": len(corps), "horodatage": info["horodatage"]},
                    )
                except Exception as exc:  # noqa: BLE001 — on renvoie une erreur JSON propre
                    self._repondre(500, {"ok": False, "erreur": str(exc)})

            def do_GET(self) -> None:  # noqa: N802
                if self.path.split("?")[0] == "/status":
                    dernier = relay.etat.dernier()
                    if dernier:
                        self._repondre(
                            200,
                            {
                                "ok": True,
                                "horodatage": dernier["horodatage"],
                                "taille": dernier["taille"],
                            },
                        )
                    else:
                        self._repondre(200, {"ok": True, "horodatage": None})
                else:
                    self._repondre(404, {"ok": False, "erreur": "route inconnue"})

            def _repondre(self, code: int, payload: dict[str, Any]) -> None:
                donnees = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self._entetes_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

            def log_message(self, *args: Any) -> None:  # silence le logging par défaut
                return None

        return _Handler


def get_audio_relay() -> AudioRelay:
    """Renvoie (et démarre si besoin) le relay audio singleton du processus."""
    return AudioRelay.get_instance()
