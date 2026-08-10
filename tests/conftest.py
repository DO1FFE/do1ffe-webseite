import sys
from pathlib import Path

import pytest


projekt_wurzel = Path(__file__).resolve().parents[1]
if str(projekt_wurzel) not in sys.path:
    sys.path.insert(0, str(projekt_wurzel))


@pytest.fixture(autouse=True)
def isolierter_strassenwetter_speicher(tmp_path, monkeypatch):
    """Verhindert, dass Routentests Laufzeitdateien im Projekt anlegen."""

    monkeypatch.setenv("ROAD_WEATHER_DATABASE", str(tmp_path / "strassenwetter.sqlite3"))
    monkeypatch.setenv("ROAD_WEATHER_LOCK_FILE", str(tmp_path / "strassenwetter.lock"))
    monkeypatch.setenv("ROAD_WEATHER_ENABLED", "false")


@pytest.fixture(autouse=True)
def isolierte_meshcore_regionen_api(monkeypatch):
    """Verhindert externe Regionenabrufe in Routentests."""

    import app as webseite

    monkeypatch.setattr(webseite, "MESHCORE_REGIONEN_API_URL", "")
    webseite.MESHCORE_REGIONEN_CACHE["daten"] = None
    yield
    webseite.MESHCORE_REGIONEN_CACHE["daten"] = None


# Copyright © 2026 Erik Schauer, do1ffe@darc.de
