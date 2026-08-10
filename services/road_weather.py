"""Sicherer Sammler und lokaler Speicher für das Straßenwetter Essen-Ost.

Der externe Abruf ist absichtlich nur über die Konfiguration aktivierbar. Die
Webseite und die API lesen ausschließlich aus dem lokalen SQLite-Speicher.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
import fcntl
from html import unescape
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from typing import Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests


PROJEKT_WURZEL = Path(__file__).resolve().parents[1]
BERLINER_ZEITZONE = ZoneInfo("Europe/Berlin")
KACHELMANN_QUELLHOST = "kachelmannwetter.com"
DWD_QUELLHOST = "opendata.dwd.de"
ERLAUBTE_QUELLHOSTS = {KACHELMANN_QUELLHOST, DWD_QUELLHOST}
ERLAUBTER_QUELLHOST = KACHELMANN_QUELLHOST
STANDARD_QUELLSEITE = "https://kachelmannwetter.com/de/autobahn/essen/"
STANDARD_DWD_QUELLSEITE = (
    "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/KM/"
    "swis2-ISXD70_DWKM_LATEST-NW---bin"
)
BUFR_DUMP_BEFEHL = "/usr/bin/bufr_dump"
STANDARD_DATENBANK = PROJEKT_WURZEL / "daten" / "strassenwetter.sqlite3"
STANDARD_SPERRE = PROJEKT_WURZEL / "daten" / "strassenwetter.lock"
MAXIMALE_ANTWORTGRÖSSE = 2 * 1024 * 1024
MAXIMALE_ROHWERT_LÄNGE = 500
STATUSWERTE = {"current", "stale", "unavailable", "error", "disabled"}

STATION = {
    "id": "H426",
    "name": "Essen-Ost",
    "elevation_m": 103,
    "latitude": 51.4547,
    "longitude": 7.0421,
    "location": "Autobahndreieck Essen-Ost",
    "districts": ["Huttrop", "Frillendorf"],
    "roads": ["A40", "A52"],
    "postal_code": "45139",
    "city": "Essen",
}

STRASSENZUSTAND_ANZEIGEN = {
    "dry": "Trocken",
    "damp": "Feucht",
    "wet": "Nass",
    "frost": "Reif",
    "snow": "Schnee",
    "ice": "Eis",
    "slippery": "Glätte",
    "not_dry": "Nicht trocken",
    "unknown": "Unbekannt",
}


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    """Zentrale Beschreibung einer öffentlich auswählbaren Messgröße."""

    quell_id: str
    schlüssel: str
    anzeigename: str
    quell_bezeichnung: str
    quellseite: str
    erwartete_einheit: str | None
    kategorie: str
    parsertyp: str
    reihenfolge: int
    symbol: str
    numerisch: bool
    priorität: int = 0


def _definition(
    quell_id: str,
    schlüssel: str,
    anzeigename: str,
    quell_bezeichnung: str,
    einheit: str | None,
    kategorie: str,
    parsertyp: str,
    reihenfolge: int,
    symbol: str,
    numerisch: bool,
    priorität: int = 0,
) -> ParameterDefinition:
    return ParameterDefinition(
        quell_id=quell_id,
        schlüssel=schlüssel,
        anzeigename=anzeigename,
        quell_bezeichnung=quell_bezeichnung,
        quellseite=STANDARD_QUELLSEITE,
        erwartete_einheit=einheit,
        kategorie=kategorie,
        parsertyp=parsertyp,
        reihenfolge=reihenfolge,
        symbol=symbol,
        numerisch=numerisch,
        priorität=priorität,
    )


# Die Quellseite bietet 19 Auswahlmöglichkeiten. Windgeschwindigkeiten werden
# nach dem Einlesen in den zwei kanonischen Objekten wind_speed und wind_gust
# zusammengeführt. Konkrete Parameter-URLs werden aus dem aktuellen Quellmenü
# ermittelt oder explizit über ROAD_WEATHER_SOURCE_URLS_JSON vorgegeben.
PARAMETER_DEFINITIONEN: tuple[ParameterDefinition, ...] = (
    _definition("road_condition", "road_condition", "Straßenzustand", "Straßenzustand", None, "Fahrbahn", "road_condition", 1, "road", False),
    _definition("surface_temperature_fast_lane", "surface_temperature_fast_lane", "Belagstemperatur schnelle Spur", "Belagstemperatur (schnelle Spur)", "°C", "Fahrbahn", "number", 2, "temperature", True),
    _definition("surface_temperature_other_lanes", "surface_temperature_other_lanes", "Belagstemperatur andere Spuren", "Belagstemperatur (andere Spuren)", "°C", "Fahrbahn", "number", 3, "temperature", True),
    _definition("ground_temperature_10cm", "ground_temperature_10cm", "Bodentemperatur in 10 cm Tiefe", "Bodentemperatur -10cm", "°C", "Fahrbahn", "number", 4, "ground", True),
    _definition("ground_temperature_30cm", "ground_temperature_30cm", "Bodentemperatur in 30 cm Tiefe", "Bodentemperatur -30cm", "°C", "Fahrbahn", "number", 5, "ground", True),
    _definition("water_film", "water_film", "Wasserfilm / Wasserstand", "Wasserstand", "mm", "Fahrbahn", "number", 6, "water", True),
    _definition("visibility", "visibility", "Sichtweite", "Sichtweite", "m", "Fahrbahn", "number", 7, "visibility", True),
    _definition("air_temperature", "air_temperature", "Lufttemperatur", "Lufttemperatur", "°C", "Luft und Feuchtigkeit", "number", 8, "temperature", True),
    _definition("dew_point", "dew_point", "Taupunkt", "Taupunkt", "°C", "Luft und Feuchtigkeit", "number", 9, "dew", True),
    _definition("relative_humidity", "relative_humidity", "Relative Luftfeuchtigkeit", "Relative Luftfeuchtigkeit", "%", "Luft und Feuchtigkeit", "number", 10, "humidity", True),
    _definition("wind_direction", "wind_direction", "Windrichtung", "Windrichtung", "°", "Wind", "direction", 11, "direction", False),
    _definition("wind_gust_direction", "wind_gust_direction", "Windrichtung der Böen", "Windrichtung Windböen", "°", "Wind", "direction", 12, "direction", False),
    _definition("wind_speed_kmh", "wind_speed", "Mittlere Windgeschwindigkeit", "Windmittel (km/h)", "km/h", "Wind", "wind", 13, "wind", True, 1),
    _definition("wind_speed_ms", "wind_speed", "Mittlere Windgeschwindigkeit", "Windmittel (m/s)", "m/s", "Wind", "wind", 14, "wind", True, 2),
    _definition("wind_gust_kmh", "wind_gust", "Windböen", "Windböen (km/h)", "km/h", "Wind", "wind", 15, "gust", True, 1),
    _definition("wind_gust_ms", "wind_gust", "Windböen", "Windböen (m/s)", "m/s", "Wind", "wind", 16, "gust", True, 2),
    _definition("precipitation_15min", "precipitation_15min", "Niederschlagssumme der letzten 15 Minuten", "Niederschlagssumme, 15min", "mm", "Niederschlag", "number", 17, "precipitation", True),
    _definition("precipitation_type", "precipitation_type", "Niederschlagsart", "Niederschlagsart", None, "Niederschlag", "text", 18, "precipitation", False),
    _definition("precipitation_intensity", "precipitation_intensity", "Niederschlagsintensität", "Niederschlagsintensität", None, "Niederschlag", "text", 19, "intensity", False),
)

INTERNE_PARAMETER: tuple[str, ...] = tuple(
    dict.fromkeys(definition.schlüssel for definition in PARAMETER_DEFINITIONEN)
)
DEFINITION_NACH_SCHLÜSSEL = {
    schlüssel: min(
        (definition for definition in PARAMETER_DEFINITIONEN if definition.schlüssel == schlüssel),
        key=lambda definition: definition.reihenfolge,
    )
    for schlüssel in INTERNE_PARAMETER
}


@dataclass(frozen=True, slots=True)
class Konfiguration:
    aktiviert: bool
    station_id: str
    kontakt_email: str
    abrufintervall_sekunden: int
    timeout_sekunden: float
    veraltet_nach_sekunden: int
    aufbewahrung_tage: int
    datenbank_pfad: Path
    sperr_pfad: Path
    start_url: str
    quell_urls: Mapping[str, str]
    maximale_antwortgröße: int = MAXIMALE_ANTWORTGRÖSSE

    @property
    def user_agent(self) -> str:
        if self.kontakt_email:
            return f"AutobahnWeatherDisplay/1.0 (+Kontakt: {self.kontakt_email})"
        return "AutobahnWeatherDisplay/1.0 (öffentliche Straßenwetter-Anzeige)"

    @classmethod
    def aus_umgebung(cls) -> "Konfiguration":
        quell_urls: dict[str, str] = {}
        roh_mapping = os.environ.get("ROAD_WEATHER_SOURCE_URLS_JSON", "").strip()
        if roh_mapping:
            try:
                geladen = json.loads(roh_mapping)
                if isinstance(geladen, dict):
                    quell_urls = {
                        str(schlüssel): str(wert)
                        for schlüssel, wert in geladen.items()
                        if isinstance(wert, str) and wert.strip()
                    }
            except json.JSONDecodeError:
                logging.getLogger(__name__).warning(
                    "strassenwetter_konfiguration_ungueltig feld=ROAD_WEATHER_SOURCE_URLS_JSON"
                )

        return cls(
            aktiviert=_umgebungs_bool("ROAD_WEATHER_ENABLED", False),
            station_id=os.environ.get("ROAD_WEATHER_STATION_ID", "H426").strip() or "H426",
            kontakt_email=os.environ.get("ROAD_WEATHER_CONTACT_EMAIL", "").strip(),
            abrufintervall_sekunden=max(900, _umgebungs_int("ROAD_WEATHER_FETCH_INTERVAL", 900)),
            timeout_sekunden=min(10.0, max(1.0, _umgebungs_float("ROAD_WEATHER_REQUEST_TIMEOUT", 10.0))),
            veraltet_nach_sekunden=max(60, _umgebungs_int("ROAD_WEATHER_STALE_AFTER", 1800)),
            aufbewahrung_tage=max(1, _umgebungs_int("ROAD_WEATHER_HISTORY_RETENTION_DAYS", 90)),
            datenbank_pfad=Path(os.environ.get("ROAD_WEATHER_DATABASE", str(STANDARD_DATENBANK))),
            sperr_pfad=Path(os.environ.get("ROAD_WEATHER_LOCK_FILE", str(STANDARD_SPERRE))),
            start_url=os.environ.get("ROAD_WEATHER_SOURCE_URL", STANDARD_DWD_QUELLSEITE).strip() or STANDARD_DWD_QUELLSEITE,
            quell_urls=quell_urls,
            maximale_antwortgröße=max(32_768, _umgebungs_int("ROAD_WEATHER_MAX_RESPONSE_BYTES", MAXIMALE_ANTWORTGRÖSSE)),
        )


def _umgebungs_bool(name: str, standard: bool) -> bool:
    wert = os.environ.get(name)
    if wert is None:
        return standard
    return wert.strip().casefold() in {"1", "true", "ja", "yes", "on"}


def _umgebungs_int(name: str, standard: int) -> int:
    try:
        return int(os.environ.get(name, str(standard)))
    except (TypeError, ValueError):
        return standard


def _umgebungs_float(name: str, standard: float) -> float:
    try:
        return float(os.environ.get(name, str(standard)))
    except (TypeError, ValueError):
        return standard


def isoformat(zeitpunkt: datetime | None) -> str | None:
    if zeitpunkt is None:
        return None
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    return zeitpunkt.isoformat(timespec="seconds")


def parse_isoformat(wert: str | None) -> datetime | None:
    if not wert:
        return None
    try:
        zeitpunkt = datetime.fromisoformat(wert.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    return zeitpunkt


def kürze_rohwert(wert: str | None, maximale_länge: int = MAXIMALE_ROHWERT_LÄNGE) -> str | None:
    if wert is None:
        return None
    bereinigt = " ".join(unescape(str(wert)).split())
    return bereinigt[:maximale_länge]


ZAHL_MUSTER = re.compile(
    r"(?<![\w])(?P<zahl>[+−-]?(?:\d{1,3}(?:[.\s'’]\d{3})+(?:,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?))"
)
EINHEIT_MUSTER = re.compile(r"(?P<einheit>°\s*C|°|km\s*/\s*h|m\s*/\s*s|mm|m|%)", re.IGNORECASE)
ZEIT_MUSTER = re.compile(r"(?<!\d)(?P<stunde>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)(?!\d)")
DATUM_MUSTER = re.compile(r"(?<!\d)(?P<tag>\d{1,2})\.(?P<monat>\d{1,2})\.(?P<jahr>20\d{2})(?!\d)")
STATION_MUSTER = re.compile(r"(?P<name>[^|()]{2,}?)\s*\(\s*(?P<höhe>-?\d+)\s*m\s*\)", re.IGNORECASE)


def parse_zahl(text: str, erwartete_einheit: str | None = None) -> float | None:
    """Liest deutsche und internationale Dezimal- und Tausenderformate."""

    treffer = ZAHL_MUSTER.search(unescape(text).replace("\u00a0", " "))
    if not treffer:
        return None
    roh = treffer.group("zahl").replace("−", "-").replace(" ", "").replace("'", "").replace("’", "")
    vorzeichen = ""
    if roh.startswith(("+", "-")):
        vorzeichen, roh = roh[0], roh[1:]

    if "," in roh and "." in roh:
        letzter_punkt = roh.rfind(".")
        letztes_komma = roh.rfind(",")
        dezimalzeichen = "." if letzter_punkt > letztes_komma else ","
        tausenderzeichen = "," if dezimalzeichen == "." else "."
        roh = roh.replace(tausenderzeichen, "").replace(dezimalzeichen, ".")
    elif roh.count(",") > 1 or roh.count(".") > 1:
        zeichen = "," if "," in roh else "."
        teile = roh.split(zeichen)
        if all(len(teil) == 3 for teil in teile[1:]):
            roh = "".join(teile)
        else:
            roh = "".join(teile[:-1]) + "." + teile[-1]
    elif "," in roh or "." in roh:
        zeichen = "," if "," in roh else "."
        links, rechts = roh.split(zeichen, 1)
        ist_sichtweite_mit_tausender = erwartete_einheit == "m" and len(rechts) == 3
        if ist_sichtweite_mit_tausender:
            roh = links + rechts
        else:
            roh = links + "." + rechts

    try:
        return float(vorzeichen + roh)
    except ValueError:
        return None


def normalisiere_einheit(wert: str | None, standard: str | None = None) -> str | None:
    if not wert:
        return standard
    einheit = re.sub(r"\s+", "", wert).replace("℃", "°C")
    klein = einheit.casefold()
    if klein == "°c":
        return "°C"
    if klein == "km/h":
        return "km/h"
    if klein == "m/s":
        return "m/s"
    return einheit


def normalisiere_strassenzustand(wert: str | None) -> str:
    text = " ".join((wert or "").casefold().replace("-", " ").split())
    direkt = {
        "trocken": "dry",
        "feucht": "damp",
        "nass": "wet",
        "reif": "frost",
        "schnee": "snow",
        "eis": "ice",
        "glätte": "slippery",
        "glaette": "slippery",
        "nicht trocken": "not_dry",
    }
    if text in direkt:
        return direkt[text]
    for begriff, normalisiert in direkt.items():
        if re.search(rf"\b{re.escape(begriff)}\b", text):
            return normalisiert
    return "unknown"


def himmelsrichtung(grad: float | None) -> str | None:
    if grad is None:
        return None
    richtungen = ("N", "NO", "O", "SO", "S", "SW", "W", "NW")
    return richtungen[int((grad % 360 + 22.5) // 45) % 8]


def kombiniere_messzeit(
    uhrzeit: str | None,
    seiteninhalt: str = "",
    abgerufen_um: datetime | None = None,
    quell_url: str = "",
) -> datetime | None:
    """Kombiniert eine Stationsuhrzeit defensiv mit Datum und Berlin-Zeitzone."""

    if not uhrzeit:
        return None
    zeit_treffer = ZEIT_MUSTER.search(uhrzeit)
    if not zeit_treffer:
        return None
    abgerufen_um = abgerufen_um or datetime.now(timezone.utc)
    lokal_abgerufen = abgerufen_um.astimezone(BERLINER_ZEITZONE)
    stunde = int(zeit_treffer.group("stunde"))
    minute = int(zeit_treffer.group("minute"))

    seitendatum: date | None = None
    url_datum = re.search(r"/(20\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})z(?:\.html)?", quell_url)
    if url_datum:
        utc_zeit = datetime(
            int(url_datum.group(1)),
            int(url_datum.group(2)),
            int(url_datum.group(3)),
            int(url_datum.group(4)),
            int(url_datum.group(5)),
            tzinfo=timezone.utc,
        )
        seitendatum = utc_zeit.astimezone(BERLINER_ZEITZONE).date()

    if seitendatum is None and seiteninhalt:
        text = " ".join(unescape(seiteninhalt).replace("\u00a0", " ").split())
        passendes_muster = re.compile(
            rf"(?P<tag>\d{{1,2}})\.(?P<monat>\d{{1,2}})\.(?P<jahr>20\d{{2}}).{{0,80}}?{stunde:02d}:{minute:02d}",
            re.IGNORECASE,
        )
        treffer = passendes_muster.search(text)
        if not treffer:
            treffer = DATUM_MUSTER.search(text)
        if treffer:
            try:
                seitendatum = date(int(treffer.group("jahr")), int(treffer.group("monat")), int(treffer.group("tag")))
            except ValueError:
                seitendatum = None

    if seitendatum is None:
        seitendatum = lokal_abgerufen.date()

    kandidat = datetime.combine(seitendatum, datetime_time(stunde, minute), tzinfo=BERLINER_ZEITZONE)
    if kandidat - lokal_abgerufen > timedelta(hours=2):
        kandidat -= timedelta(days=1)
    return kandidat


class _StationsElementParser(HTMLParser):
    """Sammelt ausschließlich Elemente mit der exakten Stations-ID."""

    def __init__(self, station_id: str):
        super().__init__(convert_charrefs=True)
        self.station_id = station_id
        self.elemente: list[dict[str, str | None]] = []
        self._tiefe = 0
        self._titel: str | None = None
        self._sichtbar: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attribute = dict(attrs)
        if self._tiefe:
            self._tiefe += 1
            return
        if attribute.get("data-station-id") == self.station_id:
            self._tiefe = 1
            self._titel = attribute.get("title")
            self._sichtbar = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attribute = dict(attrs)
        if attribute.get("data-station-id") == self.station_id:
            self.elemente.append({"title": attribute.get("title"), "sichtbar": ""})

    def handle_data(self, data: str) -> None:
        if self._tiefe:
            self._sichtbar.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._tiefe:
            return
        self._tiefe -= 1
        if self._tiefe == 0:
            self.elemente.append(
                {
                    "title": self._titel,
                    "sichtbar": " ".join("".join(self._sichtbar).split()),
                }
            )
            self._titel = None
            self._sichtbar = []


class _LinkSammler(HTMLParser):
    """Sammelt URL und Beschriftung aus dem aktuellen Parametermenü."""

    URL_ATTRIBUTE = {"href", "data-url", "data-href", "data-link", "data-path"}
    TEXT_ATTRIBUTE = {"title", "aria-label", "data-title", "data-name", "data-label"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.einträge: list[dict[str, object]] = []
        self._stapel: list[int | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attribute = dict(attrs)
        url = next((attribute.get(name) for name in self.URL_ATTRIBUTE if attribute.get(name)), None)
        if not url:
            wert = attribute.get("value", "") or ""
            if wert.startswith(("/", "https://")):
                url = wert
        if url:
            texte = [attribute.get(name, "") or "" for name in self.TEXT_ATTRIBUTE]
            self.einträge.append({"url": url, "texte": texte})
            self._stapel.append(len(self.einträge) - 1)
        else:
            self._stapel.append(self._stapel[-1] if self._stapel else None)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._stapel and self._stapel[-1] is not None:
            eintrag = self.einträge[self._stapel[-1]]
            texte = eintrag["texte"]
            assert isinstance(texte, list)
            texte.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._stapel:
            self._stapel.pop()


def _normalisiere_vergleichstext(text: str) -> str:
    text = unescape(text).casefold().replace("ß", "ss")
    return re.sub(r"[^a-z0-9%°/]+", " ", text).strip()


def ermittle_parameter_urls(
    html: str,
    basis_url: str,
    definitionen: Sequence[ParameterDefinition] = PARAMETER_DEFINITIONEN,
) -> dict[str, str]:
    parser = _LinkSammler()
    parser.feed(html)
    ergebnis: dict[str, str] = {}
    for definition in definitionen:
        gesucht = _normalisiere_vergleichstext(definition.quell_bezeichnung)
        kandidaten: list[str] = []
        for eintrag in parser.einträge:
            texte = eintrag["texte"]
            assert isinstance(texte, list)
            beschriftung = _normalisiere_vergleichstext(" ".join(str(text) for text in texte))
            if gesucht and (gesucht == beschriftung or gesucht in beschriftung):
                kandidaten.append(urljoin(basis_url, str(eintrag["url"])))
        gültige = [url for url in kandidaten if ist_html_quell_url(url)]
        if len(set(gültige)) == 1:
            ergebnis[definition.quell_id] = gültige[0]
    return ergebnis


def ist_erlaubte_quell_url(url: str) -> bool:
    try:
        zerlegt = urlparse(url)
    except ValueError:
        return False
    return (
        zerlegt.scheme == "https"
        and (zerlegt.hostname or "").casefold() in ERLAUBTE_QUELLHOSTS
        and zerlegt.username is None
        and zerlegt.password is None
        and zerlegt.port in {None, 443}
    )


def ist_dwd_quell_url(url: str) -> bool:
    if not ist_erlaubte_quell_url(url):
        return False
    zerlegt = urlparse(url)
    return (
        (zerlegt.hostname or "").casefold() == DWD_QUELLHOST
        and zerlegt.path.startswith("/weather/weather_reports/road_weather_stations/KM/")
        and zerlegt.path.endswith("-NW---bin")
    )


def ist_html_quell_url(url: str) -> bool:
    if not ist_erlaubte_quell_url(url):
        return False
    return (urlparse(url).hostname or "").casefold() == KACHELMANN_QUELLHOST


def _wert_segment_aus_title(title: str, definition: ParameterDefinition) -> str | None:
    teile = [" ".join(teil.split()) for teil in title.split("|") if teil.strip()]
    kandidaten: list[str] = []
    for teil in teile:
        if STATION_MUSTER.search(teil) or ZEIT_MUSTER.fullmatch(teil.strip()):
            continue
        if definition.numerisch:
            if ZAHL_MUSTER.search(teil):
                kandidaten.append(teil)
        elif teil:
            kandidaten.append(teil)
    if len(kandidaten) != 1:
        return None
    return kandidaten[0]


def parse_stations_html(
    html: str,
    definition: ParameterDefinition,
    station_id: str = "H426",
    abgerufen_um: datetime | None = None,
    quell_url: str = STANDARD_QUELLSEITE,
) -> dict[str, object] | None:
    """Parst genau einen eindeutigen Wert der angeforderten Station."""

    parser = _StationsElementParser(station_id)
    parser.feed(html)
    eindeutige: list[dict[str, object]] = []
    abgerufen_um = abgerufen_um or datetime.now(timezone.utc)

    for element in parser.elemente:
        title = kürze_rohwert(element.get("title"))
        if not title:
            continue
        wert_segment = _wert_segment_aus_title(title, definition)
        if not wert_segment:
            continue

        stations_treffer = STATION_MUSTER.search(title)
        station_name = STATION["name"]
        höhe = STATION["elevation_m"]
        if stations_treffer:
            gelesener_name = " ".join(stations_treffer.group("name").split())
            # H426 bleibt das eindeutige Merkmal. Ein unerwarteter Name wird
            # nicht weitergereicht, aber der Stationswert nicht verwechselt.
            if "essen-ost" in gelesener_name.casefold():
                station_name = gelesener_name
            höhe = int(stations_treffer.group("höhe"))

        zeit_treffer = ZEIT_MUSTER.search(title)
        uhrzeit = zeit_treffer.group(0) if zeit_treffer else None
        gemessen_um = kombiniere_messzeit(uhrzeit, html, abgerufen_um, quell_url)
        einheit_treffer = EINHEIT_MUSTER.search(wert_segment)
        gelesene_einheit = normalisiere_einheit(
            einheit_treffer.group("einheit") if einheit_treffer else None,
            definition.erwartete_einheit,
        )

        ergebnis: dict[str, object] = {
            "station_name": station_name,
            "elevation_m": höhe,
            "numeric_value": None,
            "text_value": None,
            "normalized_value": None,
            "unit": gelesene_einheit,
            "original_value": kürze_rohwert(wert_segment, 160),
            "original_unit": gelesene_einheit,
            "measured_at": gemessen_um,
            "fetched_at": abgerufen_um,
            "source_url": quell_url,
            "raw_title": title,
            "status": "current",
            "error_message": None,
            "priorität": definition.priorität,
        }

        if definition.parsertyp in {"number", "wind"}:
            zahl = parse_zahl(wert_segment, definition.erwartete_einheit)
            if zahl is None:
                continue
            ergebnis["numeric_value"] = zahl
        elif definition.parsertyp == "direction":
            grad = parse_zahl(wert_segment, "°")
            if grad is not None:
                ergebnis["numeric_value"] = grad % 360
                ergebnis["normalized_value"] = himmelsrichtung(grad)
            else:
                richtung = kürze_rohwert(wert_segment, 80)
                if not richtung:
                    continue
                ergebnis["text_value"] = richtung
                ergebnis["normalized_value"] = richtung
        else:
            textwert = kürze_rohwert(wert_segment, 160)
            if not textwert:
                continue
            ergebnis["text_value"] = textwert
            if definition.parsertyp == "road_condition":
                ergebnis["normalized_value"] = normalisiere_strassenzustand(textwert)
        eindeutige.append(ergebnis)

    if not eindeutige:
        return None
    signaturen = {
        (
            eintrag.get("numeric_value"),
            eintrag.get("text_value"),
            eintrag.get("normalized_value"),
            isoformat(eintrag.get("measured_at") if isinstance(eintrag.get("measured_at"), datetime) else None),
        )
        for eintrag in eindeutige
    }
    if len(signaturen) != 1:
        return None
    return eindeutige[0]


def _kanonisiere_wind(ergebnis: dict[str, object]) -> dict[str, object]:
    wert = ergebnis.get("numeric_value")
    if not isinstance(wert, (int, float)):
        return ergebnis
    einheit = normalisiere_einheit(str(ergebnis.get("original_unit") or ergebnis.get("unit") or ""))
    if einheit == "km/h":
        wert_ms = float(wert) / 3.6
    else:
        wert_ms = float(wert)
    ergebnis = dict(ergebnis)
    ergebnis["numeric_value"] = wert_ms
    ergebnis["unit"] = "m/s"
    return ergebnis


def _status_für_messzeit(ergebnis: dict[str, object], jetzt: datetime, veraltet_nach: int) -> str:
    gemessen_um = ergebnis.get("measured_at")
    if not isinstance(gemessen_um, datetime):
        return "stale"
    alter = (jetzt.astimezone(timezone.utc) - gemessen_um.astimezone(timezone.utc)).total_seconds()
    return "current" if -120 <= alter <= veraltet_nach else "stale"


class AbrufFehler(RuntimeError):
    pass


class ZugriffGesperrt(AbrufFehler):
    pass


class ParameterNichtGefunden(AbrufFehler):
    pass


@dataclass(frozen=True, slots=True)
class HtmlAntwort:
    html: str
    url: str
    status_code: int


class SichererHtmlClient:
    """Kleine HTTP-Schicht mit Hostprüfung, Grenzen und vorsichtigen Retries."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        session: requests.Session | None = None,
        pause: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
    ):
        self.konfiguration = konfiguration
        self.session = session or requests.Session()
        self.pause = pause
        self.logger = logger or logging.getLogger(__name__)
        self.session.headers.update(
            {
                "User-Agent": konfiguration.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9",
                "Accept-Language": "de-DE,de;q=0.8",
            }
        )

    def hole_html(self, url: str) -> HtmlAntwort:
        if not ist_html_quell_url(url):
            raise AbrufFehler("Quell-URL ist nicht erlaubt")

        letzter_fehler: Exception | None = None
        for versuch in range(3):
            try:
                return self._hole_mit_redirects(url)
            except ZugriffGesperrt:
                raise
            except ParameterNichtGefunden:
                raise
            except (requests.Timeout, requests.ConnectionError, AbrufFehler) as fehler:
                letzter_fehler = fehler
                if versuch >= 2:
                    break
                self.pause(0.25 * (2**versuch))
        raise AbrufFehler(kürze_rohwert(str(letzter_fehler), 240) or "Abruf fehlgeschlagen")

    def lade_robots(self) -> RobotFileParser:
        robots_url = f"https://{KACHELMANN_QUELLHOST}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            antwort = self._hole_mit_redirects(robots_url, {"text/plain"})
        except ParameterNichtGefunden:
            parser.parse([])
            return parser
        parser.parse(antwort.html.splitlines())
        return parser

    def _hole_mit_redirects(
        self,
        start_url: str,
        erlaubte_inhaltstypen: set[str] | None = None,
    ) -> HtmlAntwort:
        erlaubte_inhaltstypen = erlaubte_inhaltstypen or {"text/html", "application/xhtml+xml"}
        url = start_url
        for _weiterleitung in range(4):
            if not ist_html_quell_url(url):
                raise AbrufFehler("Weiterleitungsziel ist nicht erlaubt")
            antwort = self.session.get(
                url,
                allow_redirects=False,
                stream=True,
                timeout=(min(3.0, self.konfiguration.timeout_sekunden), max(1.0, self.konfiguration.timeout_sekunden - 3.0)),
            )
            if antwort.status_code in {301, 302, 303, 307, 308}:
                ziel = antwort.headers.get("Location")
                antwort.close()
                if not ziel:
                    raise AbrufFehler("Weiterleitung ohne Ziel")
                url = urljoin(url, ziel)
                continue
            if antwort.status_code in {401, 403, 429}:
                antwort.close()
                raise ZugriffGesperrt(f"Quellzugriff durch HTTP {antwort.status_code} eingeschränkt")
            if antwort.status_code == 404:
                antwort.close()
                raise ParameterNichtGefunden("Parameterseite meldet HTTP 404")
            if antwort.status_code >= 500:
                antwort.close()
                raise AbrufFehler(f"Quelle meldet HTTP {antwort.status_code}")
            if antwort.status_code != 200:
                antwort.close()
                raise AbrufFehler(f"Unerwarteter HTTP-Status {antwort.status_code}")

            inhaltstyp = antwort.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
            if inhaltstyp not in erlaubte_inhaltstypen:
                antwort.close()
                raise AbrufFehler("Quelle liefert einen unerwarteten Inhaltstyp")
            try:
                angegebene_größe = int(antwort.headers.get("Content-Length", "0") or 0)
            except ValueError:
                angegebene_größe = 0
            if angegebene_größe > self.konfiguration.maximale_antwortgröße:
                antwort.close()
                raise AbrufFehler("HTML-Antwort ist zu groß")

            teile: list[bytes] = []
            größe = 0
            for teil in antwort.iter_content(chunk_size=32_768):
                größe += len(teil)
                if größe > self.konfiguration.maximale_antwortgröße:
                    antwort.close()
                    raise AbrufFehler("HTML-Antwort überschreitet die Größenbegrenzung")
                teile.append(teil)
            kodierung = antwort.encoding or "utf-8"
            antwort.close()
            html = b"".join(teile).decode(kodierung, errors="replace")
            schutztext = html[:80_000].casefold()
            if any(begriff in schutztext for begriff in ("captcha", "cf-chl-", "access denied", "bot protection")):
                raise ZugriffGesperrt("Captcha oder Bot-Schutz erkannt")
            return HtmlAntwort(html=html, url=url, status_code=200)
        raise AbrufFehler("Zu viele HTTP-Weiterleitungen")


@dataclass(frozen=True, slots=True)
class DwdAntwort:
    inhalt: bytes
    url: str
    status_code: int


class SichererDwdClient:
    """Lädt ausschließlich den amtlichen DWD-BUFR-Datensatz für NRW."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        session: requests.Session | None = None,
        pause: Callable[[float], None] = time.sleep,
    ):
        self.konfiguration = konfiguration
        self.session = session or requests.Session()
        self.pause = pause
        self.session.headers.update(
            {
                "User-Agent": konfiguration.user_agent,
                "Accept": "application/octet-stream",
            }
        )

    def hole_bufr(self, url: str) -> DwdAntwort:
        if not ist_dwd_quell_url(url):
            raise AbrufFehler("DWD-Quell-URL ist nicht erlaubt")

        letzter_fehler: Exception | None = None
        for versuch in range(3):
            try:
                return self._hole_mit_redirects(url)
            except (ZugriffGesperrt, ParameterNichtGefunden):
                raise
            except (requests.Timeout, requests.ConnectionError, AbrufFehler) as fehler:
                letzter_fehler = fehler
                if versuch >= 2:
                    break
                self.pause(0.25 * (2**versuch))
        raise AbrufFehler(kürze_rohwert(str(letzter_fehler), 240) or "DWD-Abruf fehlgeschlagen")

    def _hole_mit_redirects(self, start_url: str) -> DwdAntwort:
        url = start_url
        for _weiterleitung in range(4):
            if not ist_dwd_quell_url(url):
                raise AbrufFehler("DWD-Weiterleitungsziel ist nicht erlaubt")
            antwort = self.session.get(
                url,
                allow_redirects=False,
                stream=True,
                timeout=(
                    min(3.0, self.konfiguration.timeout_sekunden),
                    max(1.0, self.konfiguration.timeout_sekunden - 3.0),
                ),
            )
            if antwort.status_code in {301, 302, 303, 307, 308}:
                ziel = antwort.headers.get("Location")
                antwort.close()
                if not ziel:
                    raise AbrufFehler("DWD-Weiterleitung ohne Ziel")
                url = urljoin(url, ziel)
                continue
            if antwort.status_code in {401, 403, 429}:
                antwort.close()
                raise ZugriffGesperrt(f"DWD-Zugriff durch HTTP {antwort.status_code} eingeschränkt")
            if antwort.status_code == 404:
                antwort.close()
                raise ParameterNichtGefunden("DWD-Datensatz meldet HTTP 404")
            if antwort.status_code >= 500:
                antwort.close()
                raise AbrufFehler(f"DWD meldet HTTP {antwort.status_code}")
            if antwort.status_code != 200:
                antwort.close()
                raise AbrufFehler(f"Unerwarteter DWD-HTTP-Status {antwort.status_code}")

            inhaltstyp = antwort.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
            if inhaltstyp not in {"application/octet-stream", "application/x-binary"}:
                antwort.close()
                raise AbrufFehler("DWD liefert einen unerwarteten Inhaltstyp")
            try:
                angegebene_größe = int(antwort.headers.get("Content-Length", "0") or 0)
            except ValueError:
                angegebene_größe = 0
            if angegebene_größe > self.konfiguration.maximale_antwortgröße:
                antwort.close()
                raise AbrufFehler("DWD-BUFR-Antwort ist zu groß")

            teile: list[bytes] = []
            größe = 0
            for teil in antwort.iter_content(chunk_size=32_768):
                größe += len(teil)
                if größe > self.konfiguration.maximale_antwortgröße:
                    antwort.close()
                    raise AbrufFehler("DWD-BUFR-Antwort überschreitet die Größenbegrenzung")
                teile.append(teil)
            antwort.close()
            inhalt = b"".join(teile)
            if not inhalt.startswith(b"BUFR"):
                raise AbrufFehler("DWD-Antwort besitzt keine gültige BUFR-Kennung")
            return DwdAntwort(inhalt=inhalt, url=url, status_code=200)
        raise AbrufFehler("Zu viele DWD-HTTP-Weiterleitungen")


_DWD_ZEILE = re.compile(r"^(?:#\d+#)?(?P<schlüssel>[A-Za-z][A-Za-z0-9]*)=(?P<wert>.*)$")


def _parse_dwd_wert(rohwert: str) -> object:
    rohwert = rohwert.strip()
    if rohwert == "MISSING":
        return None
    if rohwert.startswith('"'):
        try:
            return json.loads(rohwert)
        except json.JSONDecodeError:
            return rohwert.strip('"')
    try:
        return float(rohwert) if any(zeichen in rohwert for zeichen in (".", "e", "E")) else int(rohwert)
    except ValueError:
        return rohwert


def _dwd_station_aus_text(ausgabe: str, station_id: str) -> dict[str, list[object]] | None:
    aktuelle_station: dict[str, list[object]] | None = None
    for rohzeile in ausgabe.splitlines():
        zeile = rohzeile.strip()
        if zeile.startswith("subsetNumber="):
            if aktuelle_station and aktuelle_station.get("shortStationName", [None])[0] == station_id:
                return aktuelle_station
            aktuelle_station = {}
            continue
        if aktuelle_station is None:
            continue
        treffer = _DWD_ZEILE.fullmatch(zeile)
        if not treffer:
            continue
        aktuelle_station.setdefault(treffer.group("schlüssel"), []).append(
            _parse_dwd_wert(treffer.group("wert"))
        )
    if aktuelle_station and aktuelle_station.get("shortStationName", [None])[0] == station_id:
        return aktuelle_station
    return None


def _dwd_einzelwert(station: Mapping[str, Sequence[object]], schlüssel: str) -> object | None:
    werte = station.get(schlüssel, ())
    return werte[0] if werte else None


def _dwd_zahl(station: Mapping[str, Sequence[object]], schlüssel: str) -> float | None:
    wert = _dwd_einzelwert(station, schlüssel)
    return float(wert) if isinstance(wert, (int, float)) else None


def _dwd_temperatur_celsius(wert: float | None) -> float | None:
    return round(wert - 273.15, 3) if wert is not None else None


def parse_dwd_bufr_ausgabe(
    ausgabe: str,
    station_id: str,
    abgerufen_um: datetime,
    quell_url: str,
    veraltet_nach: int,
) -> dict[str, dict[str, object]]:
    """Überführt die ecCodes-Textausgabe für exakt eine Station in Messwerte."""

    station = _dwd_station_aus_text(ausgabe, station_id)
    if station is None:
        raise ParameterNichtGefunden(f"Station {station_id} fehlt im DWD-Datensatz")

    try:
        gemessen_um = datetime(
            int(_dwd_einzelwert(station, "year")),
            int(_dwd_einzelwert(station, "month")),
            int(_dwd_einzelwert(station, "day")),
            int(_dwd_einzelwert(station, "hour")),
            int(_dwd_einzelwert(station, "minute")),
            tzinfo=timezone.utc,
        )
    except (TypeError, ValueError) as fehler:
        raise AbrufFehler("DWD-Datensatz enthält keine eindeutige Messzeit") from fehler

    höhe = _dwd_zahl(station, "heightOfStationGroundAboveMeanSeaLevel")
    stationsname = STATION["name"]
    status = _status_für_messzeit({"measured_at": gemessen_um}, abgerufen_um, veraltet_nach)

    def leer() -> dict[str, object]:
        return {
            "station_name": stationsname,
            "elevation_m": int(höhe) if höhe is not None else STATION["elevation_m"],
            "numeric_value": None,
            "text_value": None,
            "normalized_value": None,
            "unit": None,
            "original_value": None,
            "original_unit": None,
            "measured_at": None,
            "fetched_at": abgerufen_um,
            "source_url": quell_url,
            "raw_title": None,
            "status": "unavailable",
            "error_message": None,
        }

    ergebnisse = {schlüssel: leer() for schlüssel in INTERNE_PARAMETER}

    def setze(
        schlüssel: str,
        *,
        numerisch: float | None = None,
        text: str | None = None,
        normalisiert: str | None = None,
        einheit: str | None = None,
        original: object | None = None,
        original_einheit: str | None = None,
    ) -> None:
        if numerisch is None and text is None and normalisiert is None:
            return
        ergebnisse[schlüssel].update(
            {
                "numeric_value": numerisch,
                "text_value": text,
                "normalized_value": normalisiert,
                "unit": einheit,
                "original_value": kürze_rohwert(str(original), 160) if original is not None else None,
                "original_unit": original_einheit,
                "measured_at": gemessen_um,
                "raw_title": kürze_rohwert(f"DWD BUFR {station_id}: {schlüssel}={original}", 240),
                "status": status,
            }
        )

    luft_kelvin = _dwd_zahl(station, "airTemperature")
    taupunkt_kelvin = _dwd_zahl(station, "dewpointTemperature")
    belag_kelvin = _dwd_zahl(station, "roadSurfaceTemperature")
    setze("air_temperature", numerisch=_dwd_temperatur_celsius(luft_kelvin), einheit="°C", original=luft_kelvin, original_einheit="K")
    setze("dew_point", numerisch=_dwd_temperatur_celsius(taupunkt_kelvin), einheit="°C", original=taupunkt_kelvin, original_einheit="K")
    setze("surface_temperature_fast_lane", numerisch=_dwd_temperatur_celsius(belag_kelvin), einheit="°C", original=belag_kelvin, original_einheit="K")
    setze("relative_humidity", numerisch=_dwd_zahl(station, "relativeHumidity"), einheit="%", original=_dwd_einzelwert(station, "relativeHumidity"), original_einheit="%")
    setze("visibility", numerisch=_dwd_zahl(station, "horizontalVisibility"), einheit="m", original=_dwd_einzelwert(station, "horizontalVisibility"), original_einheit="m")

    tiefen = station.get("depthBelowLandSurface", ())
    untergrund = station.get("roadSubSurfaceTemperature", ())
    for tiefe, temperatur in zip(tiefen, untergrund):
        if not isinstance(tiefe, (int, float)) or not isinstance(temperatur, (int, float)):
            continue
        if abs(float(tiefe) - 0.10) <= 0.005:
            setze("ground_temperature_10cm", numerisch=_dwd_temperatur_celsius(float(temperatur)), einheit="°C", original=temperatur, original_einheit="K")
        elif abs(float(tiefe) - 0.30) <= 0.005:
            setze("ground_temperature_30cm", numerisch=_dwd_temperatur_celsius(float(temperatur)), einheit="°C", original=temperatur, original_einheit="K")

    wasserfilm_meter = _dwd_zahl(station, "waterFilmThickness")
    setze("water_film", numerisch=round(wasserfilm_meter * 1000, 3) if wasserfilm_meter is not None else None, einheit="mm", original=wasserfilm_meter, original_einheit="m")

    zustands_code = _dwd_zahl(station, "roadSurfaceCondition")
    zustände = {
        0: ("Trocken", "dry"),
        1: ("Feucht", "damp"),
        2: ("Nass", "wet"),
        3: ("Reif", "frost"),
        4: ("Schnee", "snow"),
        5: ("Eis", "ice"),
    }
    if zustands_code is not None:
        zustand_text, zustand_normalisiert = zustände.get(int(zustands_code), ("Unbekannt", "unknown"))
        setze("road_condition", text=zustand_text, normalisiert=zustand_normalisiert, original=int(zustands_code), original_einheit="DWD-Code")

    windrichtung = _dwd_zahl(station, "windDirection")
    setze("wind_direction", numerisch=windrichtung, normalisiert=himmelsrichtung(windrichtung), einheit="°", original=windrichtung, original_einheit="°")
    setze("wind_speed", numerisch=_dwd_zahl(station, "windSpeed"), einheit="m/s", original=_dwd_einzelwert(station, "windSpeed"), original_einheit="m/s")
    böenrichtung = _dwd_zahl(station, "maximumWindGustDirection")
    setze("wind_gust_direction", numerisch=böenrichtung, normalisiert=himmelsrichtung(böenrichtung), einheit="°", original=böenrichtung, original_einheit="°")
    setze("wind_gust", numerisch=_dwd_zahl(station, "maximumWindGustSpeed"), einheit="m/s", original=_dwd_einzelwert(station, "maximumWindGustSpeed"), original_einheit="m/s")

    niederschlag = _dwd_zahl(station, "totalPrecipitationOrTotalWaterEquivalent")
    setze("precipitation_15min", numerisch=niederschlag, einheit="mm", original=niederschlag, original_einheit="kg/m²")
    niederschlags_code = _dwd_zahl(station, "precipitationType")
    niederschlagsarten = {0: "Kein Niederschlag", 1: "Regen", 2: "Schneeregen", 3: "Schnee"}
    if niederschlags_code is not None:
        niederschlagsart = niederschlagsarten.get(int(niederschlags_code), "Unbekannt")
        setze("precipitation_type", text=niederschlagsart, original=int(niederschlags_code), original_einheit="DWD-Code")
    intensitäts_code = _dwd_zahl(station, "intensityOfPhenomena")
    intensitäten = {0: "Kein Niederschlag", 1: "Leicht", 2: "Mäßig", 3: "Stark"}
    if intensitäts_code is not None:
        setze("precipitation_intensity", text=intensitäten.get(int(intensitäts_code), "Unbekannt"), original=int(intensitäts_code), original_einheit="DWD-Code")

    return ergebnisse


def dekodiere_dwd_bufr(
    inhalt: bytes,
    station_id: str,
    abgerufen_um: datetime,
    quell_url: str,
    veraltet_nach: int,
) -> dict[str, dict[str, object]]:
    if not Path(BUFR_DUMP_BEFEHL).is_file():
        raise AbrufFehler("ecCodes-Werkzeug bufr_dump ist nicht installiert")
    with tempfile.NamedTemporaryFile(prefix="do1ffe-strassenwetter-", suffix=".bufr") as datei:
        datei.write(inhalt)
        datei.flush()
        try:
            prozess = subprocess.run(
                [BUFR_DUMP_BEFEHL, "-p", datei.name],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired) as fehler:
            raise AbrufFehler("DWD-BUFR-Dekodierung ist fehlgeschlagen") from fehler
    if prozess.returncode != 0:
        raise AbrufFehler("DWD-BUFR-Datensatz konnte nicht dekodiert werden")
    if len(prozess.stdout) > 2 * 1024 * 1024:
        raise AbrufFehler("Dekodierte DWD-BUFR-Daten überschreiten die Größenbegrenzung")
    return parse_dwd_bufr_ausgabe(prozess.stdout, station_id, abgerufen_um, quell_url, veraltet_nach)


class ProzessSperre:
    def __init__(self, pfad: Path):
        self.pfad = pfad
        self._datei = None

    def __enter__(self) -> "ProzessSperre":
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self._datei = self.pfad.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as fehler:
            self._datei.close()
            self._datei = None
            raise RuntimeError("Eine Straßenwetter-Aktualisierung läuft bereits") from fehler
        self._datei.seek(0)
        self._datei.truncate()
        self._datei.write(str(os.getpid()))
        self._datei.flush()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._datei:
            fcntl.flock(self._datei.fileno(), fcntl.LOCK_UN)
            self._datei.close()
            self._datei = None


class StrassenwetterSpeicher:
    def __init__(self, datenbank_pfad: Path):
        self.datenbank_pfad = Path(datenbank_pfad)

    def verbinde(self) -> sqlite3.Connection:
        self.datenbank_pfad.parent.mkdir(parents=True, exist_ok=True)
        verbindung = sqlite3.connect(self.datenbank_pfad, timeout=10)
        verbindung.row_factory = sqlite3.Row
        verbindung.execute("PRAGMA foreign_keys = ON")
        verbindung.execute("PRAGMA journal_mode = WAL")
        return verbindung

    def initialisiere(self) -> None:
        with self.verbinde() as verbindung:
            verbindung.executescript(
                """
                CREATE TABLE IF NOT EXISTS road_weather_current (
                    station_id TEXT NOT NULL,
                    parameter TEXT NOT NULL,
                    station_name TEXT,
                    elevation_m INTEGER,
                    numeric_value REAL,
                    text_value TEXT,
                    normalized_value TEXT,
                    unit TEXT,
                    original_value TEXT,
                    original_unit TEXT,
                    measured_at TEXT,
                    fetched_at TEXT NOT NULL,
                    source_url TEXT,
                    raw_title TEXT,
                    status TEXT NOT NULL CHECK (status IN ('current', 'stale', 'unavailable', 'error', 'disabled')),
                    error_message TEXT,
                    PRIMARY KEY (station_id, parameter)
                );

                CREATE TABLE IF NOT EXISTS road_weather_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id TEXT NOT NULL,
                    parameter TEXT NOT NULL,
                    numeric_value REAL,
                    text_value TEXT,
                    normalized_value TEXT,
                    unit TEXT,
                    original_value TEXT,
                    original_unit TEXT,
                    measured_at TEXT,
                    fetched_at TEXT NOT NULL,
                    source_url TEXT,
                    status TEXT NOT NULL CHECK (status IN ('current', 'stale', 'unavailable', 'error', 'disabled'))
                );

                CREATE TABLE IF NOT EXISTS road_weather_meta (
                    station_id TEXT PRIMARY KEY,
                    last_attempt_at TEXT,
                    last_success_at TEXT,
                    last_error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_road_weather_current_station_parameter
                    ON road_weather_current (station_id, parameter);
                CREATE INDEX IF NOT EXISTS idx_road_weather_history_measured
                    ON road_weather_history (measured_at);
                CREATE INDEX IF NOT EXISTS idx_road_weather_history_fetched
                    ON road_weather_history (fetched_at);
                CREATE INDEX IF NOT EXISTS idx_road_weather_history_station_measured
                    ON road_weather_history (station_id, measured_at);
                """
            )

    def letzter_versuch(self, station_id: str) -> datetime | None:
        self.initialisiere()
        with self.verbinde() as verbindung:
            zeile = verbindung.execute(
                "SELECT last_attempt_at FROM road_weather_meta WHERE station_id = ?",
                (station_id,),
            ).fetchone()
        return parse_isoformat(zeile["last_attempt_at"] if zeile else None)

    def speichere_aktualisierung(
        self,
        station_id: str,
        ergebnisse: Mapping[str, dict[str, object]],
        versucht_um: datetime,
        letzter_fehler: str | None,
    ) -> None:
        self.initialisiere()
        with self.verbinde() as verbindung:
            for parameter, ergebnis in ergebnisse.items():
                self._speichere_parameter(verbindung, station_id, parameter, ergebnis)
            erfolgreich = any(
                ergebnis.get("status") in {"current", "stale", "unavailable"}
                and not ergebnis.get("error_message")
                for ergebnis in ergebnisse.values()
            )
            bestehend = verbindung.execute(
                "SELECT last_success_at FROM road_weather_meta WHERE station_id = ?",
                (station_id,),
            ).fetchone()
            letzter_erfolg = isoformat(versucht_um) if erfolgreich else (bestehend["last_success_at"] if bestehend else None)
            verbindung.execute(
                """
                INSERT INTO road_weather_meta (station_id, last_attempt_at, last_success_at, last_error)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    last_attempt_at = excluded.last_attempt_at,
                    last_success_at = excluded.last_success_at,
                    last_error = excluded.last_error
                """,
                (station_id, isoformat(versucht_um), letzter_erfolg, kürze_rohwert(letzter_fehler, 240)),
            )

    def _speichere_parameter(
        self,
        verbindung: sqlite3.Connection,
        station_id: str,
        parameter: str,
        ergebnis: dict[str, object],
    ) -> None:
        status = str(ergebnis.get("status") or "error")
        if status not in STATUSWERTE:
            status = "error"
        bestehend = verbindung.execute(
            "SELECT * FROM road_weather_current WHERE station_id = ? AND parameter = ?",
            (station_id, parameter),
        ).fetchone()

        if status == "error" and bestehend and _zeile_hat_wert(bestehend):
            if bestehend["status"] != "stale":
                verbindung.execute(
                    """
                    INSERT INTO road_weather_history (
                        station_id, parameter, numeric_value, text_value, normalized_value,
                        unit, original_value, original_unit, measured_at, fetched_at,
                        source_url, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'stale')
                    """,
                    (
                        station_id,
                        parameter,
                        bestehend["numeric_value"],
                        bestehend["text_value"],
                        bestehend["normalized_value"],
                        bestehend["unit"],
                        bestehend["original_value"],
                        bestehend["original_unit"],
                        bestehend["measured_at"],
                        isoformat(ergebnis.get("fetched_at") if isinstance(ergebnis.get("fetched_at"), datetime) else datetime.now(timezone.utc)),
                        bestehend["source_url"],
                    ),
                )
            verbindung.execute(
                """
                UPDATE road_weather_current
                SET status = 'stale', error_message = ?
                WHERE station_id = ? AND parameter = ?
                """,
                (kürze_rohwert(str(ergebnis.get("error_message") or "Temporärer Abruffehler"), 240), station_id, parameter),
            )
            return

        werte = {
            "station_id": station_id,
            "parameter": parameter,
            "station_name": ergebnis.get("station_name") or STATION["name"],
            "elevation_m": ergebnis.get("elevation_m") or STATION["elevation_m"],
            "numeric_value": ergebnis.get("numeric_value"),
            "text_value": kürze_rohwert(ergebnis.get("text_value") if isinstance(ergebnis.get("text_value"), str) else None, 160),
            "normalized_value": kürze_rohwert(ergebnis.get("normalized_value") if isinstance(ergebnis.get("normalized_value"), str) else None, 160),
            "unit": normalisiere_einheit(ergebnis.get("unit") if isinstance(ergebnis.get("unit"), str) else None),
            "original_value": kürze_rohwert(ergebnis.get("original_value") if isinstance(ergebnis.get("original_value"), str) else None, 160),
            "original_unit": normalisiere_einheit(ergebnis.get("original_unit") if isinstance(ergebnis.get("original_unit"), str) else None),
            "measured_at": isoformat(ergebnis.get("measured_at") if isinstance(ergebnis.get("measured_at"), datetime) else None),
            "fetched_at": isoformat(ergebnis.get("fetched_at") if isinstance(ergebnis.get("fetched_at"), datetime) else datetime.now(timezone.utc)),
            "source_url": ergebnis.get("source_url") if isinstance(ergebnis.get("source_url"), str) and ist_erlaubte_quell_url(ergebnis.get("source_url")) else None,
            "raw_title": kürze_rohwert(ergebnis.get("raw_title") if isinstance(ergebnis.get("raw_title"), str) else None),
            "status": status,
            "error_message": kürze_rohwert(ergebnis.get("error_message") if isinstance(ergebnis.get("error_message"), str) else None, 240),
        }

        if _historie_relevant_geändert(bestehend, werte):
            verbindung.execute(
                """
                INSERT INTO road_weather_history (
                    station_id, parameter, numeric_value, text_value, normalized_value,
                    unit, original_value, original_unit, measured_at, fetched_at,
                    source_url, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(
                    werte[name]
                    for name in (
                        "station_id", "parameter", "numeric_value", "text_value", "normalized_value",
                        "unit", "original_value", "original_unit", "measured_at", "fetched_at",
                        "source_url", "status",
                    )
                ),
            )

        verbindung.execute(
            """
            INSERT INTO road_weather_current (
                station_id, parameter, station_name, elevation_m, numeric_value,
                text_value, normalized_value, unit, original_value, original_unit,
                measured_at, fetched_at, source_url, raw_title, status, error_message
            ) VALUES (
                :station_id, :parameter, :station_name, :elevation_m, :numeric_value,
                :text_value, :normalized_value, :unit, :original_value, :original_unit,
                :measured_at, :fetched_at, :source_url, :raw_title, :status, :error_message
            )
            ON CONFLICT(station_id, parameter) DO UPDATE SET
                station_name = excluded.station_name,
                elevation_m = excluded.elevation_m,
                numeric_value = excluded.numeric_value,
                text_value = excluded.text_value,
                normalized_value = excluded.normalized_value,
                unit = excluded.unit,
                original_value = excluded.original_value,
                original_unit = excluded.original_unit,
                measured_at = excluded.measured_at,
                fetched_at = excluded.fetched_at,
                source_url = excluded.source_url,
                raw_title = excluded.raw_title,
                status = excluded.status,
                error_message = excluded.error_message
            """,
            werte,
        )

    def lade_aktuell(self, station_id: str) -> tuple[dict[str, sqlite3.Row], sqlite3.Row | None]:
        self.initialisiere()
        with self.verbinde() as verbindung:
            zeilen = verbindung.execute(
                "SELECT * FROM road_weather_current WHERE station_id = ?",
                (station_id,),
            ).fetchall()
            meta = verbindung.execute(
                "SELECT * FROM road_weather_meta WHERE station_id = ?",
                (station_id,),
            ).fetchone()
        return {zeile["parameter"]: zeile for zeile in zeilen}, meta

    def bereinige_historie(self, aufbewahrung_tage: int, jetzt: datetime | None = None) -> int:
        self.initialisiere()
        jetzt = jetzt or datetime.now(timezone.utc)
        grenze = isoformat(jetzt - timedelta(days=max(1, aufbewahrung_tage)))
        with self.verbinde() as verbindung:
            cursor = verbindung.execute(
                "DELETE FROM road_weather_history WHERE fetched_at < ?",
                (grenze,),
            )
            return cursor.rowcount


def _zeile_hat_wert(zeile: sqlite3.Row) -> bool:
    return zeile["numeric_value"] is not None or zeile["text_value"] is not None or zeile["normalized_value"] is not None


def _historie_relevant_geändert(zeile: sqlite3.Row | None, werte: Mapping[str, object]) -> bool:
    if zeile is None:
        return True
    return any(
        zeile[name] != werte[name]
        for name in ("numeric_value", "text_value", "normalized_value", "unit", "measured_at", "status")
    )


class StrassenwetterSammler:
    def __init__(
        self,
        konfiguration: Konfiguration,
        client: SichererHtmlClient | None = None,
        dwd_client: SichererDwdClient | None = None,
        speicher: StrassenwetterSpeicher | None = None,
        definitionen: Sequence[ParameterDefinition] = PARAMETER_DEFINITIONEN,
        logger: logging.Logger | None = None,
    ):
        self.konfiguration = konfiguration
        self.logger = logger or logging.getLogger(__name__)
        self.client = client or SichererHtmlClient(konfiguration, logger=self.logger)
        self.dwd_client = dwd_client or SichererDwdClient(konfiguration)
        self.speicher = speicher or StrassenwetterSpeicher(konfiguration.datenbank_pfad)
        self.definitionen = tuple(definitionen)

    def aktualisiere(self, erzwingen: bool = False, jetzt: datetime | None = None) -> dict[str, object]:
        jetzt = jetzt or datetime.now(timezone.utc)
        self.speicher.initialisiere()
        if not self.konfiguration.aktiviert:
            return {"status": "disabled", "updated": False, "message": "Externer Abruf ist deaktiviert."}
        if self.konfiguration.station_id != STATION["id"]:
            raise ValueError("Für diese Anzeige ist ausschließlich Station H426 zulässig")
        if not ist_erlaubte_quell_url(self.konfiguration.start_url):
            raise ValueError("ROAD_WEATHER_SOURCE_URL ist nicht zulässig")

        with ProzessSperre(self.konfiguration.sperr_pfad):
            letzter_versuch = self.speicher.letzter_versuch(self.konfiguration.station_id)
            if not erzwingen and letzter_versuch:
                alter = (jetzt - letzter_versuch.astimezone(jetzt.tzinfo or timezone.utc)).total_seconds()
                if alter < self.konfiguration.abrufintervall_sekunden:
                    return {"status": "skipped", "updated": False, "message": "Abrufintervall noch nicht erreicht."}
            return self._aktualisiere_gesperrt(jetzt)

    def _aktualisiere_gesperrt(self, jetzt: datetime) -> dict[str, object]:
        if ist_dwd_quell_url(self.konfiguration.start_url):
            return self._aktualisiere_dwd_gesperrt(jetzt)

        ergebnisse_nach_quelle: dict[str, dict[str, object]] = {}
        fehler: list[str] = []
        try:
            robots = self.client.lade_robots()
            if not robots.can_fetch(self.konfiguration.user_agent, self.konfiguration.start_url):
                raise ZugriffGesperrt("robots.txt erlaubt den Abruf der Quellseite nicht")
            start_antwort = self.client.hole_html(self.konfiguration.start_url)
        except ZugriffGesperrt as abruf_fehler:
            meldung = kürze_rohwert(str(abruf_fehler), 240) or "Zugriff eingeschränkt"
            self.logger.warning("strassenwetter_zugriff_eingeschraenkt station=%s fehler=%s", self.konfiguration.station_id, meldung)
            ergebnisse = self._fehler_für_alle(jetzt, self.konfiguration.start_url, meldung)
            self.speicher.speichere_aktualisierung(self.konfiguration.station_id, ergebnisse, jetzt, meldung)
            return {"status": "error", "updated": True, "errors": len(ergebnisse), "message": meldung}
        except AbrufFehler as abruf_fehler:
            meldung = kürze_rohwert(str(abruf_fehler), 240) or "Startseite nicht erreichbar"
            ergebnisse = self._fehler_für_alle(jetzt, self.konfiguration.start_url, meldung)
            self.speicher.speichere_aktualisierung(self.konfiguration.station_id, ergebnisse, jetzt, meldung)
            return {"status": "error", "updated": True, "errors": len(ergebnisse), "message": meldung}

        gefundene_urls = ermittle_parameter_urls(start_antwort.html, start_antwort.url, self.definitionen)
        gefundene_urls.update(self.konfiguration.quell_urls)

        for definition in self.definitionen:
            url = gefundene_urls.get(definition.quell_id)
            if definition.quell_id == "road_condition" and not url:
                url = start_antwort.url
            if not url or not ist_erlaubte_quell_url(url):
                meldung = "Aktueller Parameterpfad konnte im Quellmenü nicht eindeutig ermittelt werden"
                fehler.append(f"{definition.quell_id}: {meldung}")
                ergebnisse_nach_quelle[definition.quell_id] = self._fehler_ergebnis(jetzt, url or start_antwort.url, meldung)
                self.logger.warning("strassenwetter_parameterpfad_fehlt station=%s parameter=%s", self.konfiguration.station_id, definition.quell_id)
                continue
            if not robots.can_fetch(self.konfiguration.user_agent, url):
                meldung = "robots.txt erlaubt den Abruf dieser Parameterseite nicht"
                fehler.append(f"{definition.quell_id}: {meldung}")
                ergebnisse_nach_quelle[definition.quell_id] = self._fehler_ergebnis(jetzt, url, meldung)
                self.logger.warning("strassenwetter_robots_sperre station=%s parameter=%s", self.konfiguration.station_id, definition.quell_id)
                continue

            try:
                antwort = start_antwort if url == start_antwort.url else self.client.hole_html(url)
                parsed = parse_stations_html(
                    antwort.html,
                    definition,
                    self.konfiguration.station_id,
                    jetzt,
                    antwort.url,
                )
                if parsed is None:
                    ergebnisse_nach_quelle[definition.quell_id] = self._unavailable_ergebnis(jetzt, antwort.url)
                else:
                    parsed["status"] = _status_für_messzeit(parsed, jetzt, self.konfiguration.veraltet_nach_sekunden)
                    ergebnisse_nach_quelle[definition.quell_id] = parsed
            except ZugriffGesperrt as abruf_fehler:
                meldung = kürze_rohwert(str(abruf_fehler), 240) or "Zugriff eingeschränkt"
                fehler.append(f"{definition.quell_id}: {meldung}")
                ergebnisse_nach_quelle[definition.quell_id] = self._fehler_ergebnis(jetzt, url, meldung)
                self.logger.warning("strassenwetter_zugriff_eingeschraenkt station=%s parameter=%s fehler=%s", self.konfiguration.station_id, definition.quell_id, meldung)
                # Bei einem generellen Schutzsignal wird nicht weiter angefragt.
                for rest in self.definitionen[self.definitionen.index(definition) + 1 :]:
                    ergebnisse_nach_quelle[rest.quell_id] = self._fehler_ergebnis(jetzt, start_antwort.url, meldung)
                break
            except ParameterNichtGefunden as abruf_fehler:
                meldung = kürze_rohwert(str(abruf_fehler), 240) or "Parameterseite nicht verfügbar"
                fehler.append(f"{definition.quell_id}: {meldung}")
                ergebnisse_nach_quelle[definition.quell_id] = self._fehler_ergebnis(jetzt, url, meldung)
                self.logger.warning("strassenwetter_parameterseite_fehlt station=%s parameter=%s", self.konfiguration.station_id, definition.quell_id)
            except AbrufFehler as abruf_fehler:
                meldung = kürze_rohwert(str(abruf_fehler), 240) or "Technischer Abruffehler"
                fehler.append(f"{definition.quell_id}: {meldung}")
                ergebnisse_nach_quelle[definition.quell_id] = self._fehler_ergebnis(jetzt, url, meldung)
                self.logger.warning("strassenwetter_parameter_fehler station=%s parameter=%s fehler=%s", self.konfiguration.station_id, definition.quell_id, meldung)

        zusammengeführt = self._führe_parameter_zusammen(ergebnisse_nach_quelle, jetzt)
        letzter_fehler = "; ".join(fehler[:4]) if fehler else None
        self.speicher.speichere_aktualisierung(self.konfiguration.station_id, zusammengeführt, jetzt, letzter_fehler)
        gelöscht = self.speicher.bereinige_historie(self.konfiguration.aufbewahrung_tage, jetzt)
        return {
            "status": "partial" if fehler else "ok",
            "updated": True,
            "measurements": sum(1 for wert in zusammengeführt.values() if wert.get("numeric_value") is not None or wert.get("text_value") is not None),
            "unavailable": sum(1 for wert in zusammengeführt.values() if wert.get("status") == "unavailable"),
            "errors": len(fehler),
            "history_deleted": gelöscht,
        }

    def _aktualisiere_dwd_gesperrt(self, jetzt: datetime) -> dict[str, object]:
        try:
            antwort = self.dwd_client.hole_bufr(self.konfiguration.start_url)
            ergebnisse = dekodiere_dwd_bufr(
                antwort.inhalt,
                self.konfiguration.station_id,
                jetzt,
                antwort.url,
                self.konfiguration.veraltet_nach_sekunden,
            )
        except (AbrufFehler, ParameterNichtGefunden, ZugriffGesperrt) as abruf_fehler:
            meldung = kürze_rohwert(str(abruf_fehler), 240) or "DWD-Datensatz nicht abrufbar"
            self.logger.warning(
                "strassenwetter_dwd_fehler station=%s fehler=%s",
                self.konfiguration.station_id,
                meldung,
            )
            ergebnisse = self._fehler_für_alle(jetzt, self.konfiguration.start_url, meldung)
            self.speicher.speichere_aktualisierung(
                self.konfiguration.station_id,
                ergebnisse,
                jetzt,
                meldung,
            )
            return {
                "status": "error",
                "updated": True,
                "errors": len(ergebnisse),
                "message": meldung,
            }

        self.speicher.speichere_aktualisierung(
            self.konfiguration.station_id,
            ergebnisse,
            jetzt,
            None,
        )
        gelöscht = self.speicher.bereinige_historie(self.konfiguration.aufbewahrung_tage, jetzt)
        return {
            "status": "ok",
            "updated": True,
            "measurements": sum(
                1
                for wert in ergebnisse.values()
                if wert.get("numeric_value") is not None
                or wert.get("text_value") is not None
                or wert.get("normalized_value") is not None
            ),
            "unavailable": sum(1 for wert in ergebnisse.values() if wert.get("status") == "unavailable"),
            "errors": 0,
            "history_deleted": gelöscht,
        }

    def _führe_parameter_zusammen(
        self,
        quellergebnisse: Mapping[str, dict[str, object]],
        jetzt: datetime,
    ) -> dict[str, dict[str, object]]:
        gruppen: dict[str, list[tuple[ParameterDefinition, dict[str, object]]]] = {}
        for definition in self.definitionen:
            ergebnis = quellergebnisse.get(definition.quell_id) or self._fehler_ergebnis(jetzt, definition.quellseite, "Kein Abrufergebnis")
            gruppen.setdefault(definition.schlüssel, []).append((definition, ergebnis))

        zusammengeführt: dict[str, dict[str, object]] = {}
        for schlüssel, einträge in gruppen.items():
            mit_wert = [
                (definition, wert)
                for definition, wert in einträge
                if wert.get("numeric_value") is not None or wert.get("text_value") is not None or wert.get("normalized_value") is not None
            ]
            if mit_wert:
                definition, wert = max(mit_wert, key=lambda eintrag: eintrag[0].priorität)
                zusammengeführt[schlüssel] = _kanonisiere_wind(wert) if definition.parsertyp == "wind" else dict(wert)
            elif all(wert.get("status") == "unavailable" for _, wert in einträge):
                zusammengeführt[schlüssel] = dict(einträge[0][1])
            else:
                fehlerwert = next((wert for _, wert in einträge if wert.get("status") == "error"), einträge[0][1])
                zusammengeführt[schlüssel] = dict(fehlerwert)
        return zusammengeführt

    def _unavailable_ergebnis(self, jetzt: datetime, url: str) -> dict[str, object]:
        return {
            "station_name": STATION["name"], "elevation_m": STATION["elevation_m"],
            "numeric_value": None, "text_value": None, "normalized_value": None,
            "unit": None, "original_value": None, "original_unit": None,
            "measured_at": None, "fetched_at": jetzt, "source_url": url,
            "raw_title": None, "status": "unavailable", "error_message": None,
        }

    def _fehler_ergebnis(self, jetzt: datetime, url: str, meldung: str) -> dict[str, object]:
        ergebnis = self._unavailable_ergebnis(jetzt, url)
        ergebnis["status"] = "error"
        ergebnis["error_message"] = kürze_rohwert(meldung, 240)
        return ergebnis

    def _fehler_für_alle(self, jetzt: datetime, url: str, meldung: str) -> dict[str, dict[str, object]]:
        return {schlüssel: self._fehler_ergebnis(jetzt, url, meldung) for schlüssel in INTERNE_PARAMETER}


def _messwert_status(zeile: sqlite3.Row, jetzt: datetime, veraltet_nach: int) -> str:
    status = zeile["status"]
    if status == "current":
        gemessen_um = parse_isoformat(zeile["measured_at"])
        if gemessen_um is None or (jetzt - gemessen_um.astimezone(jetzt.tzinfo or timezone.utc)).total_seconds() > veraltet_nach:
            return "stale"
    return status


def _basis_api_eintrag(definition: ParameterDefinition, status: str) -> dict[str, object]:
    return {
        "name": definition.anzeigename,
        "category": definition.kategorie,
        "icon": definition.symbol,
        "value": None,
        "unit": definition.erwartete_einheit,
        "original_value": None,
        "original_unit": None,
        "measured_at": None,
        "fetched_at": None,
        "status": status,
    }


def _api_messwert(
    schlüssel: str,
    zeile: sqlite3.Row | None,
    status: str,
) -> dict[str, object]:
    definition = DEFINITION_NACH_SCHLÜSSEL[schlüssel]
    eintrag = _basis_api_eintrag(definition, status)
    if zeile is None:
        if schlüssel == "road_condition":
            eintrag["label"] = "Nicht gemeldet"
        elif schlüssel in {"wind_direction", "wind_gust_direction"}:
            eintrag.pop("value", None)
            eintrag.update({"degrees": None, "cardinal": None})
        elif schlüssel in {"wind_speed", "wind_gust"}:
            eintrag.pop("value", None)
            eintrag.update({"value_ms": None, "value_kmh": None})
        elif not definition.numerisch:
            eintrag["label"] = "Nicht gemeldet"
        return eintrag

    eintrag.update(
        {
            "unit": zeile["unit"] or definition.erwartete_einheit,
            "original_value": zeile["original_value"],
            "original_unit": zeile["original_unit"],
            "measured_at": zeile["measured_at"],
            "fetched_at": zeile["fetched_at"],
            "status": status,
        }
    )
    if schlüssel == "road_condition":
        normalisiert = zeile["normalized_value"]
        eintrag["value"] = normalisiert
        eintrag["label"] = STRASSENZUSTAND_ANZEIGEN.get(normalisiert, "Unbekannt") if normalisiert else "Nicht gemeldet"
    elif schlüssel in {"wind_direction", "wind_gust_direction"}:
        eintrag.pop("value", None)
        eintrag["degrees"] = zeile["numeric_value"]
        eintrag["cardinal"] = zeile["normalized_value"]
        eintrag["original_value"] = zeile["original_value"] or zeile["text_value"]
    elif schlüssel in {"wind_speed", "wind_gust"}:
        eintrag.pop("value", None)
        wert_ms = zeile["numeric_value"]
        eintrag["value_ms"] = round(wert_ms, 3) if wert_ms is not None else None
        eintrag["value_kmh"] = round(wert_ms * 3.6, 3) if wert_ms is not None else None
    elif definition.numerisch:
        eintrag["value"] = zeile["numeric_value"]
    else:
        eintrag["value"] = zeile["text_value"]
        eintrag["label"] = zeile["text_value"] or "Nicht gemeldet"
    return eintrag


def berechne_glättehinweis(messwerte: Mapping[str, Mapping[str, object]]) -> dict[str, str]:
    zustand = messwerte.get("road_condition", {}).get("value")
    if zustand in {"ice", "slippery", "frost"}:
        return {
            "level": "warning",
            "text": "Glättegefahr: Der gemeldete Straßenzustand weist auf Eis, Reif oder Glätte hin.",
        }

    temperaturen = [
        messwerte.get("surface_temperature_fast_lane", {}).get("value"),
        messwerte.get("surface_temperature_other_lanes", {}).get("value"),
    ]
    niedrige_temperatur = any(isinstance(wert, (int, float)) and wert <= 1.0 for wert in temperaturen)
    niederschlag_typ = str(messwerte.get("precipitation_type", {}).get("value") or "").casefold()
    niederschlag_summe = messwerte.get("precipitation_15min", {}).get("value")
    intensität = messwerte.get("precipitation_intensity", {}).get("value")
    feuchtigkeit = (
        zustand in {"damp", "wet", "not_dry"}
        or (niederschlag_typ and niederschlag_typ not in {"kein niederschlag", "keiner", "none", "unbekannt"})
        or isinstance(niederschlag_summe, (int, float)) and niederschlag_summe > 0
        or bool(intensität)
    )
    if niedrige_temperatur and feuchtigkeit:
        return {
            "level": "warning",
            "text": "Glättegefahr: Niedrige Belagstemperatur und gemeldete Feuchtigkeit oder Niederschlag treffen zusammen.",
        }

    beurteilungswerte = (
        messwerte.get("road_condition", {}).get("value"),
        *temperaturen,
        messwerte.get("precipitation_type", {}).get("value"),
        messwerte.get("precipitation_15min", {}).get("value"),
    )
    if sum(wert is not None for wert in beurteilungswerte) < 3:
        return {
            "level": "uncertain",
            "text": "Keine vollständige Beurteilung der Glättegefahr möglich.",
        }
    return {
        "level": "none",
        "text": "Aus den gemeldeten Messwerten ergibt sich derzeit kein Glättehinweis.",
    }


def lade_api_daten(
    konfiguration: Konfiguration,
    jetzt: datetime | None = None,
) -> dict[str, object]:
    jetzt = jetzt or datetime.now(timezone.utc)
    speicher = StrassenwetterSpeicher(konfiguration.datenbank_pfad)
    zeilen, meta = speicher.lade_aktuell(konfiguration.station_id)
    messwerte: dict[str, dict[str, object]] = {}
    for schlüssel in INTERNE_PARAMETER:
        zeile = zeilen.get(schlüssel)
        if not konfiguration.aktiviert:
            status = "disabled"
        elif zeile is None:
            status = "unavailable"
        else:
            status = _messwert_status(zeile, jetzt, konfiguration.veraltet_nach_sekunden)
        messwerte[schlüssel] = _api_messwert(schlüssel, zeile, status)

    vorhandene_status = [eintrag["status"] for eintrag in messwerte.values()]
    hat_wert = any(
        eintrag.get("value") is not None
        or eintrag.get("value_ms") is not None
        or eintrag.get("degrees") is not None
        for eintrag in messwerte.values()
    )
    if not konfiguration.aktiviert:
        gesamtstatus = "disabled"
    elif "current" in vorhandene_status:
        gesamtstatus = "current"
    elif hat_wert:
        gesamtstatus = "stale"
    elif "error" in vorhandene_status:
        gesamtstatus = "error"
    else:
        gesamtstatus = "unavailable"

    messzeiten = [parse_isoformat(zeile["measured_at"]) for zeile in zeilen.values()]
    gültige_messzeiten = [zeitpunkt for zeitpunkt in messzeiten if zeitpunkt is not None]
    gemessen_um = max(gültige_messzeiten) if gültige_messzeiten else None
    versucht_um = parse_isoformat(meta["last_attempt_at"] if meta else None)
    standard_quell_url = konfiguration.start_url if ist_erlaubte_quell_url(konfiguration.start_url) else STANDARD_QUELLSEITE
    quell_url = next(
        (
            zeile["source_url"]
            for zeile in zeilen.values()
            if zeile["source_url"] and ist_erlaubte_quell_url(zeile["source_url"])
        ),
        standard_quell_url,
    )
    ist_dwd = ist_dwd_quell_url(quell_url) or ist_dwd_quell_url(konfiguration.start_url)

    return {
        "station": dict(STATION),
        "measured_at": isoformat(gemessen_um),
        "fetched_at": isoformat(versucht_um),
        "status": gesamtstatus,
        "stale": gesamtstatus == "stale",
        "enabled": konfiguration.aktiviert,
        "measurements": messwerte,
        "slipperiness": berechne_glättehinweis(messwerte),
        "source": {
            "data_basis": "BMVBS und Straßenbauverwaltungen der Länder" if ist_dwd else "Bundesländer/DWD",
            "display_source": "Deutscher Wetterdienst (Open Data)" if ist_dwd else "Kachelmannwetter",
            "url": quell_url,
            "retrieval_type": "official_open_data" if ist_dwd else "public_web_page",
        },
        "error": kürze_rohwert(meta["last_error"] if meta else None, 240),
    }


def parameterkonfiguration_als_dict() -> list[dict[str, object]]:
    return [asdict(definition) for definition in PARAMETER_DEFINITIONEN]


# Copyright © 2026 Erik Schauer, do1ffe@darc.de
