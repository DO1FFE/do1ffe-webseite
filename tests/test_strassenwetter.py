from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re
import sqlite3

import pytest
import requests

import app as webseite
from services import road_weather


def definition(schlüssel):
    return next(
        eintrag
        for eintrag in road_weather.PARAMETER_DEFINITIONEN
        if eintrag.quell_id == schlüssel
    )


def konfiguration(tmp_path, aktiviert=True, **änderungen):
    standard = road_weather.Konfiguration(
        aktiviert=aktiviert,
        station_id="H426",
        kontakt_email="test@example.invalid",
        abrufintervall_sekunden=900,
        timeout_sekunden=4,
        veraltet_nach_sekunden=1800,
        aufbewahrung_tage=90,
        datenbank_pfad=tmp_path / "strassenwetter.sqlite3",
        sperr_pfad=tmp_path / "strassenwetter.lock",
        start_url=road_weather.STANDARD_QUELLSEITE,
        quell_urls={},
    )
    return replace(standard, **änderungen)


def messergebnis(
    wert=None,
    text=None,
    normalisiert=None,
    einheit="°C",
    gemessen_um=None,
    abgerufen_um=None,
    status="current",
    original=None,
):
    gemessen_um = gemessen_um or datetime(2026, 7, 19, 7, 0, tzinfo=road_weather.BERLINER_ZEITZONE)
    abgerufen_um = abgerufen_um or gemessen_um + timedelta(minutes=4)
    return {
        "station_name": "Essen-Ost",
        "elevation_m": 103,
        "numeric_value": wert,
        "text_value": text,
        "normalized_value": normalisiert,
        "unit": einheit,
        "original_value": original if original is not None else (str(wert) if wert is not None else text),
        "original_unit": einheit,
        "measured_at": gemessen_um,
        "fetched_at": abgerufen_um,
        "source_url": "https://kachelmannwetter.com/de/autobahn/essen/test.html",
        "raw_title": "gekürzter Testtitel",
        "status": status,
        "error_message": None,
    }


@pytest.mark.parametrize(
    ("rohwert", "erwartet"),
    [
        ("18,2°C", 18.2),
        ("-1,4°C", -1.4),
        ("18,2 °C", 18.2),
        ("-1.4 °C", -1.4),
    ],
)
def test_deutsche_und_internationale_temperaturen(rohwert, erwartet):
    assert road_weather.parse_zahl(rohwert, "°C") == erwartet


def test_parser_erkennt_ausschliesslich_h426_und_genauen_title_wert():
    html = """
    <p>19.07.2026, 07:00 Uhr</p>
    <a data-station-id="H322" title="99,9°C | Andere Station (80m) | 07:00">100</a>
    <a data-station-id="H426" title="18,2°C | Essen-Ost (103m) | 07:00">18</a>
    """
    ergebnis = road_weather.parse_stations_html(
        html,
        definition("air_temperature"),
        abgerufen_um=datetime(2026, 7, 19, 5, 4, tzinfo=timezone.utc),
    )

    assert ergebnis is not None
    assert ergebnis["numeric_value"] == 18.2
    assert ergebnis["station_name"] == "Essen-Ost"
    assert ergebnis["elevation_m"] == 103
    assert ergebnis["original_value"] == "18,2°C"


def test_falsche_station_wird_nie_uebernommen():
    html = '<a data-station-id="H322" title="8,0°C | Essen-Ost (103m) | 07:00">8</a>'
    assert road_weather.parse_stations_html(html, definition("air_temperature")) is None


def test_fehlendes_title_ist_kontrolliert_nicht_verfuegbar():
    html = '<a data-station-id="H426">18</a>'
    assert road_weather.parse_stations_html(html, definition("air_temperature")) is None


def test_mehrdeutige_h426_werte_werden_verworfen():
    html = """
    <a data-station-id="H426" title="18,2°C | Essen-Ost (103m) | 07:00">18</a>
    <a data-station-id="H426" title="19,2°C | Essen-Ost (103m) | 07:00">19</a>
    """
    assert road_weather.parse_stations_html(html, definition("air_temperature")) is None


def test_amtlicher_dwd_datensatz_wird_fuer_h426_umgerechnet():
    ausgabe = """
    subsetNumber=1
    shortStationName="H322"
    airTemperature=399.15
    subsetNumber=2
    shortStationName="H426"
    stationOrSiteName="E Ost1 P"
    year=2026
    month=7
    day=19
    hour=13
    minute=45
    heightOfStationGroundAboveMeanSeaLevel=103
    airTemperature=294.85
    dewpointTemperature=280.15
    relativeHumidity=38
    horizontalVisibility=MISSING
    roadSurfaceTemperature=309.15
    #1#depthBelowLandSurface=0.1
    #1#roadSubSurfaceTemperature=301.15
    #2#depthBelowLandSurface=0.3
    #2#roadSubSurfaceTemperature=MISSING
    waterFilmThickness=0
    roadSurfaceCondition=0
    precipitationType=0
    totalPrecipitationOrTotalWaterEquivalent=MISSING
    windDirection=MISSING
    windSpeed=MISSING
    """
    jetzt = datetime(2026, 7, 19, 13, 50, tzinfo=timezone.utc)

    ergebnisse = road_weather.parse_dwd_bufr_ausgabe(
        ausgabe,
        "H426",
        jetzt,
        road_weather.STANDARD_DWD_QUELLSEITE,
        1800,
    )

    assert len(ergebnisse) == 17
    assert ergebnisse["air_temperature"]["numeric_value"] == 21.7
    assert ergebnisse["surface_temperature_fast_lane"]["numeric_value"] == 36.0
    assert ergebnisse["ground_temperature_10cm"]["numeric_value"] == 28.0
    assert ergebnisse["ground_temperature_30cm"]["status"] == "unavailable"
    assert ergebnisse["water_film"]["numeric_value"] == 0
    assert ergebnisse["road_condition"]["normalized_value"] == "dry"
    assert ergebnisse["precipitation_type"]["text_value"] == "Kein Niederschlag"
    assert ergebnisse["air_temperature"]["measured_at"].isoformat() == "2026-07-19T13:45:00+00:00"


def test_dwd_quell_url_ist_exakt_begrenzt():
    assert road_weather.ist_dwd_quell_url(road_weather.STANDARD_DWD_QUELLSEITE)
    assert not road_weather.ist_dwd_quell_url(
        "https://opendata.dwd.de.evil.example/weather/weather_reports/road_weather_stations/KM/datei-NW---bin"
    )
    assert not road_weather.ist_dwd_quell_url(
        "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/DD/datei-NW---bin"
    )


def test_strassenzustand_wird_normalisiert_und_original_bleibt_erhalten():
    html = '<a data-station-id="H426" title="Trocken | Essen-Ost (103m) | 07:00">Trocken</a>'
    ergebnis = road_weather.parse_stations_html(html, definition("road_condition"))

    assert ergebnis["normalized_value"] == "dry"
    assert ergebnis["text_value"] == "Trocken"
    assert ergebnis["original_value"] == "Trocken"


def test_unbekannter_strassenzustand_bewahrt_originaltext():
    html = '<a data-station-id="H426" title="Schmierfilm | Essen-Ost (103m) | 07:00">?</a>'
    ergebnis = road_weather.parse_stations_html(html, definition("road_condition"))

    assert ergebnis["normalized_value"] == "unknown"
    assert ergebnis["original_value"] == "Schmierfilm"


def test_messzeit_beruecksichtigt_sommerzeit():
    zeitpunkt = road_weather.kombiniere_messzeit(
        "07:00",
        "So. 19.07.2026, 07:00 Uhr MESZ",
        datetime(2026, 7, 19, 5, 4, tzinfo=timezone.utc),
    )

    assert zeitpunkt.isoformat() == "2026-07-19T07:00:00+02:00"


def test_messzeit_beruecksichtigt_winterzeit():
    zeitpunkt = road_weather.kombiniere_messzeit(
        "07:00",
        "Mo. 19.01.2026, 07:00 Uhr MEZ",
        datetime(2026, 1, 19, 6, 4, tzinfo=timezone.utc),
    )

    assert zeitpunkt.isoformat() == "2026-01-19T07:00:00+01:00"


def test_wind_wird_intern_in_ms_gespeichert_und_in_kmh_ausgegeben(tmp_path):
    konfig = konfiguration(tmp_path)
    sammler = road_weather.StrassenwetterSammler(
        konfig,
        definitionen=(definition("wind_speed_kmh"), definition("wind_speed_ms")),
    )
    jetzt = datetime(2026, 7, 19, 5, 4, tzinfo=timezone.utc)
    zusammengeführt = sammler._führe_parameter_zusammen(
        {
            "wind_speed_kmh": messergebnis(36.0, einheit="km/h", abgerufen_um=jetzt),
            "wind_speed_ms": messergebnis(10.1, einheit="m/s", abgerufen_um=jetzt),
        },
        jetzt,
    )

    assert zusammengeführt["wind_speed"]["numeric_value"] == 10.1
    speicher = road_weather.StrassenwetterSpeicher(konfig.datenbank_pfad)
    speicher.speichere_aktualisierung("H426", zusammengeführt, jetzt, None)
    api = road_weather.lade_api_daten(konfig, jetzt)
    assert api["measurements"]["wind_speed"]["value_ms"] == 10.1
    assert api["measurements"]["wind_speed"]["value_kmh"] == 36.36
    assert api["measurements"]["wind_speed"]["original_unit"] == "m/s"


def test_windrichtung_erzeugt_himmelsrichtung():
    html = '<a data-station-id="H426" title="225° | Essen-Ost (103m) | 07:00">SW</a>'
    ergebnis = road_weather.parse_stations_html(html, definition("wind_direction"))

    assert ergebnis["numeric_value"] == 225
    assert ergebnis["normalized_value"] == "SW"


def test_parameter_urls_werden_aus_aktuellem_quellmenue_gelesen():
    html = """
    <nav>
      <a href="/de/autobahn/essen/lufttemperatur/">Lufttemperatur (°C)</a>
      <a href="https://example.org/falsch">Taupunkt (°C)</a>
    </nav>
    """
    urls = road_weather.ermittle_parameter_urls(
        html,
        road_weather.STANDARD_QUELLSEITE,
        (definition("air_temperature"), definition("dew_point")),
    )

    assert urls == {
        "air_temperature": "https://kachelmannwetter.com/de/autobahn/essen/lufttemperatur/"
    }


class FakeAntwort:
    def __init__(self, status_code, inhalt=b"", headers=None):
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self.inhalt = inhalt
        self.geschlossen = False

    def iter_content(self, chunk_size=32768):
        yield self.inhalt

    def close(self):
        self.geschlossen = True


class FakeSession:
    def __init__(self, antworten):
        self.headers = {}
        self.antworten = list(antworten)
        self.aufrufe = 0

    def get(self, *args, **kwargs):
        self.aufrufe += 1
        antwort = self.antworten[min(self.aufrufe - 1, len(self.antworten) - 1)]
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


@pytest.mark.parametrize("status_code", [403, 429])
def test_zugriffssperren_werden_nicht_wiederholt(tmp_path, status_code):
    session = FakeSession([FakeAntwort(status_code)])
    client = road_weather.SichererHtmlClient(konfiguration(tmp_path), session=session, pause=lambda sekunden: None)

    with pytest.raises(road_weather.ZugriffGesperrt):
        client.hole_html(road_weather.STANDARD_QUELLSEITE)

    assert session.aufrufe == 1


def test_netzwerk_timeout_hat_nur_begrenzte_wiederholungen(tmp_path):
    session = FakeSession([requests.Timeout("Zeitüberschreitung")])
    client = road_weather.SichererHtmlClient(konfiguration(tmp_path), session=session, pause=lambda sekunden: None)

    with pytest.raises(road_weather.AbrufFehler):
        client.hole_html(road_weather.STANDARD_QUELLSEITE)

    assert session.aufrufe == 3


def test_robots_sperre_wird_respektiert(tmp_path):
    antwort = FakeAntwort(
        200,
        b"User-agent: *\nDisallow: /de/autobahn/\n",
        {"Content-Type": "text/plain; charset=utf-8"},
    )
    client = road_weather.SichererHtmlClient(
        konfiguration(tmp_path),
        session=FakeSession([antwort]),
        pause=lambda sekunden: None,
    )

    robots = client.lade_robots()
    assert robots.can_fetch(client.konfiguration.user_agent, road_weather.STANDARD_QUELLSEITE) is False


def test_station_auf_erreichbarer_parameterseite_nicht_vorhanden_ergibt_unavailable(tmp_path):
    jetzt = datetime(2026, 7, 19, 5, 4, tzinfo=timezone.utc)
    sammler = road_weather.StrassenwetterSammler(
        konfiguration(tmp_path),
        definitionen=(definition("air_temperature"),),
    )
    zusammengeführt = sammler._führe_parameter_zusammen(
        {"air_temperature": sammler._unavailable_ergebnis(jetzt, road_weather.STANDARD_QUELLSEITE)},
        jetzt,
    )

    assert zusammengeführt["air_temperature"]["numeric_value"] is None
    assert zusammengeführt["air_temperature"]["status"] == "unavailable"


def test_alter_messwert_wird_in_der_api_stale(tmp_path):
    konfig = konfiguration(tmp_path)
    jetzt = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)
    alt = jetzt - timedelta(hours=2)
    speicher = road_weather.StrassenwetterSpeicher(konfig.datenbank_pfad)
    speicher.speichere_aktualisierung(
        "H426",
        {"air_temperature": messergebnis(14.5, gemessen_um=alt, abgerufen_um=alt + timedelta(minutes=2))},
        alt + timedelta(minutes=2),
        None,
    )

    daten = road_weather.lade_api_daten(konfig, jetzt)
    assert daten["status"] == "stale"
    assert daten["stale"] is True
    assert daten["measurements"]["air_temperature"]["status"] == "stale"


def test_temporaerer_abruf_fehler_bewahrt_letzten_wert(tmp_path):
    konfig = konfiguration(tmp_path)
    speicher = road_weather.StrassenwetterSpeicher(konfig.datenbank_pfad)
    alt = datetime(2026, 7, 19, 5, 0, tzinfo=timezone.utc)
    speicher.speichere_aktualisierung(
        "H426",
        {"air_temperature": messergebnis(18.2, gemessen_um=alt, abgerufen_um=alt)},
        alt,
        None,
    )

    fehler = messergebnis(gemessen_um=alt, abgerufen_um=alt + timedelta(hours=1), status="error")
    fehler.update({"numeric_value": None, "text_value": None, "normalized_value": None, "error_message": "Timeout"})
    speicher.speichere_aktualisierung(
        "H426",
        {"air_temperature": fehler},
        alt + timedelta(hours=1),
        "Timeout",
    )

    daten = road_weather.lade_api_daten(konfig, alt + timedelta(hours=1))
    assert daten["measurements"]["air_temperature"]["value"] == 18.2
    assert daten["measurements"]["air_temperature"]["status"] == "stale"
    with speicher.verbinde() as verbindung:
        status_historie = [
            zeile[0]
            for zeile in verbindung.execute(
                "SELECT status FROM road_weather_history WHERE parameter = 'air_temperature' ORDER BY id"
            )
        ]
    assert status_historie == ["current", "stale"]


def test_historie_verhindert_unveraenderte_dubletten(tmp_path):
    konfig = konfiguration(tmp_path)
    speicher = road_weather.StrassenwetterSpeicher(konfig.datenbank_pfad)
    zeitpunkt = datetime(2026, 7, 19, 5, 0, tzinfo=timezone.utc)
    ergebnis = messergebnis(18.2, gemessen_um=zeitpunkt, abgerufen_um=zeitpunkt)
    speicher.speichere_aktualisierung("H426", {"air_temperature": ergebnis}, zeitpunkt, None)
    ergebnis = dict(ergebnis, fetched_at=zeitpunkt + timedelta(minutes=15))
    speicher.speichere_aktualisierung("H426", {"air_temperature": ergebnis}, zeitpunkt + timedelta(minutes=15), None)

    with speicher.verbinde() as verbindung:
        anzahl = verbindung.execute("SELECT COUNT(*) FROM road_weather_history").fetchone()[0]
    assert anzahl == 1


def test_api_liefert_stabile_struktur_und_null_ist_nicht_nullwert(tmp_path, monkeypatch):
    monkeypatch.setenv("ROAD_WEATHER_DATABASE", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("ROAD_WEATHER_LOCK_FILE", str(tmp_path / "api.lock"))
    monkeypatch.setenv("ROAD_WEATHER_ENABLED", "true")
    monkeypatch.setenv("ROAD_WEATHER_STATION_ID", "H426")

    antwort = webseite.app.test_client().get("/api/autobahn")
    daten = antwort.get_json()

    assert antwort.status_code == 200
    assert antwort.content_type == "application/json"
    assert daten["station"]["id"] == "H426"
    assert len(daten["measurements"]) == 17
    assert daten["measurements"]["air_temperature"]["value"] is None
    assert daten["measurements"]["air_temperature"]["status"] == "unavailable"


def test_autobahn_seite_funktioniert_ohne_bisherige_daten(tmp_path, monkeypatch):
    monkeypatch.setenv("ROAD_WEATHER_DATABASE", str(tmp_path / "leer.sqlite3"))
    monkeypatch.setenv("ROAD_WEATHER_LOCK_FILE", str(tmp_path / "leer.lock"))
    monkeypatch.setenv("ROAD_WEATHER_ENABLED", "false")

    antwort = webseite.app.test_client().get("/autobahn")
    html = antwort.get_data(as_text=True)

    assert antwort.status_code == 200
    assert "Straßenwetter Essen-Ost" in html
    assert "Station H426" in html
    assert "Nicht gemeldet" in html
    assert "Lokale Daten aktualisieren" not in html
    assert "Datenbasis: BMVBS und Straßenbauverwaltungen der Länder" in html


def test_autobahn_seite_blendet_felder_ohne_wert_und_leere_bereiche_aus(tmp_path, monkeypatch):
    datenbank = tmp_path / "sichtbarkeit.sqlite3"
    konfig = konfiguration(tmp_path, datenbank_pfad=datenbank)
    jetzt = datetime.now(timezone.utc)
    speicher = road_weather.StrassenwetterSpeicher(datenbank)
    speicher.speichere_aktualisierung(
        "H426",
        {
            "air_temperature": messergebnis(20.5, einheit="°C", gemessen_um=jetzt, abgerufen_um=jetzt),
            "water_film": messergebnis(0.0, einheit="mm", gemessen_um=jetzt, abgerufen_um=jetzt),
        },
        jetzt,
        None,
    )
    monkeypatch.setenv("ROAD_WEATHER_DATABASE", str(datenbank))
    monkeypatch.setenv("ROAD_WEATHER_LOCK_FILE", str(tmp_path / "sichtbarkeit.lock"))
    monkeypatch.setenv("ROAD_WEATHER_ENABLED", "true")

    html = webseite.app.test_client().get("/autobahn").get_data(as_text=True)

    luft_karte = re.search(r'<article[^>]*data-autobahn-messwert="air_temperature"[^>]*>', html).group(0)
    wasser_karte = re.search(r'<article[^>]*data-autobahn-messwert="water_film"[^>]*>', html).group(0)
    wind_karte = re.search(r'<article[^>]*data-autobahn-messwert="wind_speed"[^>]*>', html).group(0)
    wind_bereich = re.search(r'<section[^>]*aria-labelledby="autobahn-wind-titel"[^>]*>', html).group(0)

    assert " hidden" not in luft_karte
    assert " hidden" not in wasser_karte
    assert " hidden" in wind_karte
    assert " hidden" in wind_bereich


def test_externer_text_wird_nicht_als_html_ausgefuehrt(tmp_path, monkeypatch):
    datenbank = tmp_path / "xss.sqlite3"
    konfig = konfiguration(tmp_path, datenbank_pfad=datenbank)
    speicher = road_weather.StrassenwetterSpeicher(datenbank)
    jetzt = datetime.now(timezone.utc)
    angriffs_text = '<script>alert("xss")</script>'
    speicher.speichere_aktualisierung(
        "H426",
        {"precipitation_type": messergebnis(text=angriffs_text, einheit=None, gemessen_um=jetzt, abgerufen_um=jetzt)},
        jetzt,
        None,
    )
    monkeypatch.setenv("ROAD_WEATHER_DATABASE", str(datenbank))
    monkeypatch.setenv("ROAD_WEATHER_LOCK_FILE", str(tmp_path / "xss.lock"))
    monkeypatch.setenv("ROAD_WEATHER_ENABLED", "true")

    html = webseite.app.test_client().get("/autobahn").get_data(as_text=True)
    assert angriffs_text not in html
    assert "&lt;script&gt;" in html or "\\u003cscript\\u003e" in html


def test_glaettewarnung_nur_bei_erfuellten_bedingungen():
    eis = {"road_condition": {"value": "ice"}}
    assert road_weather.berechne_glättehinweis(eis)["level"] == "warning"

    kalt_und_nass = {
        "road_condition": {"value": "wet"},
        "surface_temperature_fast_lane": {"value": 0.8},
        "surface_temperature_other_lanes": {"value": None},
        "precipitation_type": {"value": None},
        "precipitation_15min": {"value": None},
        "precipitation_intensity": {"value": None},
    }
    assert road_weather.berechne_glättehinweis(kalt_und_nass)["level"] == "warning"

    unvollständig = {"road_condition": {"value": None}}
    hinweis = road_weather.berechne_glättehinweis(unvollständig)
    assert hinweis["level"] == "uncertain"
    assert hinweis["text"] == "Keine vollständige Beurteilung der Glättegefahr möglich."


# Copyright © 2026 Erik Schauer, do1ffe@darc.de
