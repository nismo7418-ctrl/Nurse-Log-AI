"""
tests/test_audio_relay.py — Tests d'intégration du relay audio local.

Couvre :
  - Démarrage / arrêt du serveur
  - POST /audio → get_latest_recording() → contenu correct
  - GET /status
  - MIME → extension mapping
  - Suppression de l'enregistrement précédent (on ne garde que le dernier)
  - Singleton (get_instance)
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.request

import pytest

from audio_relay import (
    AudioRelay,
    get_audio_relay,
    mime_vers_extension,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def relay():
    """Crée un relay isolé (port aléatoire) et l'arrête après le test."""
    r = AudioRelay(enregistrer_atexit=False)
    yield r
    r.arreter()


@pytest.fixture
def singleton_relay():
    """Utilise le singleton (reset avant/après)."""
    AudioRelay._reset_instance()
    r = get_audio_relay()
    yield r
    r.arreter()
    AudioRelay._reset_instance()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_audio(relay: AudioRelay, payload: bytes, mime: str = "audio/webm") -> dict:
    """Envoie un POST /audio et renvoie le JSON de réponse."""
    req = urllib.request.Request(
        f"{relay.url}/audio",
        data=payload,
        headers={"Content-Type": mime},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_status(relay: AudioRelay) -> dict:
    """Récupère GET /status."""
    with urllib.request.urlopen(f"{relay.url}/status", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests : mapping MIME
# ---------------------------------------------------------------------------

class TestMimeMapping:
    def test_webm(self):
        assert mime_vers_extension("audio/webm") == "webm"

    def test_mp4(self):
        assert mime_vers_extension("audio/mp4") == "mp4"

    def test_wav(self):
        assert mime_vers_extension("audio/wav") == "wav"

    def test_wav_alt(self):
        assert mime_vers_extension("audio/x-wav") == "wav"

    def test_avec_params(self):
        assert mime_vers_extension("audio/webm;codecs=opus") == "webm"

    def test_inconnu(self):
        assert mime_vers_extension("audio/unknown") == "webm"

    def test_vide(self):
        assert mime_vers_extension("") == "webm"

    def test_none(self):
        assert mime_vers_extension(None) == "webm"


# ---------------------------------------------------------------------------
# Tests : cycle de vie
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_url_format(self, relay):
        assert relay.url.startswith("http://127.0.0.1:")
        assert relay.port > 0

    def test_au_demarrage_pas_d_enregistrement(self, relay):
        assert relay.get_latest_recording() is None

    def test_arreter_idempotent(self, relay):
        relay.arreter()
        relay.arreter()  # ne doit pas lever d'exception

    def test_arreter_vide_etat(self, relay):
        _post_audio(relay, b"fake-audio-data")
        relay.arreter()
        # Après arrêt, l'état est vidé
        assert relay.etat.dernier() is None


# ---------------------------------------------------------------------------
# Tests : POST /audio → get_latest_recording()
# ---------------------------------------------------------------------------

class TestPostAudio:
    def test_post_et_lire(self, relay):
        """POST un blob → get_latest_recording() renvoie les bonnes infos."""
        payload = b"\x00\x01\x02\x03" * 100  # 400 octets factices
        resp = _post_audio(relay, payload, mime="audio/webm")

        assert resp["ok"] is True
        assert resp["taille"] == len(payload)
        assert "horodatage" in resp

        info = relay.get_latest_recording()
        assert info is not None
        assert info["taille"] == len(payload)
        assert info["mime"] == "audio/webm"
        assert info["horodatage"] > 0

        # Le fichier existe et contient les données
        assert os.path.exists(info["path"])
        with open(info["path"], "rb") as f:
            assert f.read() == payload

    def test_post_corps_vide(self, relay):
        """POST avec corps vide → 400."""
        req = urllib.request.Request(
            f"{relay.url}/audio",
            data=b"",
            headers={"Content-Type": "audio/webm"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            pytest.fail("Devrait lever HTTPError 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read().decode())
            assert body["ok"] is False

    def test_post_route_inconnue(self, relay):
        """POST sur une route inconnue → 404."""
        req = urllib.request.Request(
            f"{relay.url}/inconnu",
            data=b"data",
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            pytest.fail("Devrait lever HTTPError 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_mime_mp4(self, relay):
        """POST avec MIME audio/mp4 → extension .mp4."""
        payload = b"fake-mp4-data"
        _post_audio(relay, payload, mime="audio/mp4")
        info = relay.get_latest_recording()
        assert info["path"].endswith(".mp4")

    def test_mime_wav(self, relay):
        """POST avec MIME audio/wav → extension .wav."""
        payload = b"RIFF....WAVE"
        _post_audio(relay, payload, mime="audio/wav")
        info = relay.get_latest_recording()
        assert info["path"].endswith(".wav")


# ---------------------------------------------------------------------------
# Tests : on ne garde que le dernier enregistrement
# ---------------------------------------------------------------------------

class TestLastRecordingOnly:
    def test_second_post_supprime_le_premier(self, relay):
        """Le second POST supprime le fichier du premier."""
        payload1 = b"premier-enregistrement"
        payload2 = b"deuxieme-enregistrement"

        _post_audio(relay, payload1)
        info1 = relay.get_latest_recording()
        path1 = info1["path"]
        assert os.path.exists(path1)

        _post_audio(relay, payload2)
        info2 = relay.get_latest_recording()

        # Le premier fichier a été supprimé
        assert not os.path.exists(path1)
        # Le second est bien là
        assert os.path.exists(info2["path"])
        with open(info2["path"], "rb") as f:
            assert f.read() == payload2


# ---------------------------------------------------------------------------
# Tests : GET /status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_vide(self, relay):
        data = _get_status(relay)
        assert data["ok"] is True
        assert data["horodatage"] is None

    def test_status_apres_post(self, relay):
        _post_audio(relay, b"audio-data")
        data = _get_status(relay)
        assert data["ok"] is True
        assert data["horodatage"] is not None
        assert data["taille"] == len(b"audio-data")


# ---------------------------------------------------------------------------
# Tests : singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_instance_retourne_le_meme(self, singleton_relay):
        r1 = get_audio_relay()
        r2 = get_audio_relay()
        assert r1 is r2

    def test_reset_puis_nouveau(self, singleton_relay):
        r1 = get_audio_relay()
        AudioRelay._reset_instance()
        r2 = get_audio_relay()
        assert r1 is not r2
        # Nettoyer le second
        r2.arreter()
        AudioRelay._reset_instance()


# ---------------------------------------------------------------------------
# Tests : thread-safety (basique)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_post_pendant_lecture(self, relay):
        """Un POST pendant qu'on lit ne doit pas corrompre l'état."""
        import threading

        errors = []

        def writer():
            try:
                for i in range(10):
                    _post_audio(relay, f"thread-{i}".encode())
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=writer)
        t.start()

        # Lire en parallèle
        for _ in range(20):
            info = relay.get_latest_recording()
            if info is not None:
                assert info["taille"] > 0
            time.sleep(0.005)

        t.join()
        assert not errors


# ---------------------------------------------------------------------------
# Tests : health-check (is_alive)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_is_alive_au_demarrage(self, relay):
        """Le relay est vivant juste après le démarrage."""
        assert relay.is_alive is True

    def test_is_alive_apres_arret(self, relay):
        """Le relay n'est plus vivant après arrêt."""
        relay.arreter()
        assert relay.is_alive is False

    def test_is_alive_apres_double_arret(self, relay):
        """Double arrêt → toujours False, pas d'exception."""
        relay.arreter()
        relay.arreter()
        assert relay.is_alive is False

    def test_singleton_is_alive(self, singleton_relay):
        """Le singleton est vivant."""
        assert get_audio_relay().is_alive is True
