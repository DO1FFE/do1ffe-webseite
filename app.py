from collections import Counter
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import json
import os
from pathlib import Path
import re
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import click
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from flask_compress import Compress

from services import road_weather

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["COMPRESS_MIMETYPES"] = [
    "application/javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
    "text/css",
    "text/html",
    "text/javascript",
    "text/xml",
]
app.config["COMPRESS_MIN_SIZE"] = 500
Compress(app)

KANONISCHE_BASIS_URL = "https://do1ffe.de"
COPYRIGHT_STARTJAHR = 2026
ROBOTS_INDEXIERBAR = (
    "index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1"
)
ROBOTS_NICHT_INDEXIERBAR = "noindex,follow,noarchive"
ROBOTS_FEHLERSEITE = "noindex,nofollow,nosnippet,noarchive"


@app.context_processor
def statische_dateien_mit_version():
    def statische_datei(dateiname):
        pfad = Path(app.static_folder or "") / dateiname
        try:
            version = int(pfad.stat().st_mtime)
        except OSError:
            version = int(time.time())
        return url_for("static", filename=dateiname, v=version)

    aktuelles_jahr = datetime.now(BERLINER_ZEITZONE).year
    copyright_jahre = str(COPYRIGHT_STARTJAHR)
    if aktuelles_jahr > COPYRIGHT_STARTJAHR:
        copyright_jahre = f"{COPYRIGHT_STARTJAHR} - {aktuelles_jahr}"

    return {
        "statische_datei": statische_datei,
        "copyright_jahre": copyright_jahre,
    }


@app.context_processor
def seo_strukturierte_daten():
    seite = SEO_SEITEN_NACH_ENDPOINT.get(request.endpoint or "")
    if not seite:
        return {
            "breadcrumb_jsonld": "",
            "seo_kanonische_url": "",
            "seo_robots": ROBOTS_FEHLERSEITE,
        }

    ist_indexierbar = (
        seite.get("indexierbar", True) and not bool(request.query_string)
    )
    seo_daten = {
        "breadcrumb_jsonld": "",
        "seo_kanonische_url": kanonische_url(seite["pfad"]),
        "seo_robots": (
            ROBOTS_INDEXIERBAR
            if ist_indexierbar
            else ROBOTS_NICHT_INDEXIERBAR
        ),
    }
    if seite["pfad"] == "/":
        return seo_daten

    elemente = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "DO1FFE",
            "item": kanonische_url("/"),
        }
    ]
    if seite.get("eltern_pfad"):
        elemente.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": seite["eltern_name"],
                "item": kanonische_url(seite["eltern_pfad"]),
            }
        )
    elemente.append(
        {
            "@type": "ListItem",
            "position": len(elemente) + 1,
            "name": seite["name"],
            "item": kanonische_url(seite["pfad"]),
        }
    )
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elemente,
    }
    seo_daten["breadcrumb_jsonld"] = json.dumps(
        breadcrumb,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return seo_daten


@app.before_request
def leite_www_auf_kanonischen_host_um():
    angefragter_host = request.host.partition(":")[0].casefold()
    if angefragter_host != "www.do1ffe.de":
        return None

    ziel = f"{KANONISCHE_BASIS_URL}{request.path}"
    if request.query_string:
        ziel = f"{ziel}?{request.query_string.decode('latin-1')}"
    return redirect(ziel, code=301)


SEO_SEITEN = (
    {
        "endpoint": "startseite",
        "pfad": "/",
        "name": "Startseite",
        "dateien": ("templates/startseite.html", "templates/layout.html"),
    },
    {
        "endpoint": "ov_l11",
        "pfad": "/ov-l11",
        "name": "OV L11",
        "dateien": ("templates/ov_l11.html", "templates/layout.html"),
    },
    {
        "endpoint": "ov_abend_2026_08_11",
        "pfad": "/ov-l11/ov-abend-2026-08-11",
        "name": "OV-Abend am 11.08.2026",
        "eltern_pfad": "/ov-l11",
        "eltern_name": "OV L11",
        "dateien": (
            "templates/ov_abend_2026_08_11.html",
            "templates/layout.html",
            "static/assets/ov-l11-radio.svg",
        ),
    },
    {
        "endpoint": "tesla_dashboard",
        "pfad": "/tesla-dashboard",
        "name": "Tesla-Dashboard",
        "dateien": ("templates/tesla_dashboard.html", "templates/layout.html"),
    },
    {
        "endpoint": "tempco2",
        "pfad": "/tempco2",
        "name": "TempCO2",
        "dateien": ("templates/tempco2.html", "templates/layout.html", "static/script.js"),
    },
    {
        "endpoint": "autobahn",
        "pfad": "/autobahn",
        "name": "Autobahnwetter",
        "dateien": (
            "templates/autobahn.html",
            "templates/layout.html",
            "static/autobahn.js",
            "services/road_weather.py",
        ),
    },
    {
        "endpoint": "dienste",
        "pfad": "/dienste",
        "name": "Dienste",
        "dateien": ("templates/github.html", "templates/layout.html", "app.py"),
    },
    {
        "endpoint": "meshcore",
        "pfad": "/meshcore",
        "name": "MeshCore",
        "dateien": ("templates/meshcore.html", "templates/layout.html", "app.py"),
    },
    {
        "endpoint": "funkbruecke",
        "pfad": "/Funkbruecke",
        "name": "FunkBrücke",
        "dateien": ("templates/funkbruecke.html", "templates/layout.html", "app.py"),
    },
    {
        "endpoint": "kontakt",
        "pfad": "/kontakt",
        "name": "Kontakt",
        "dateien": ("templates/kontakt.html", "templates/layout.html"),
    },
    {
        "endpoint": "impressum",
        "pfad": "/impressum",
        "name": "Impressum",
        "indexierbar": False,
        "dateien": ("templates/impressum.html", "templates/layout.html"),
    },
    {
        "endpoint": "datenschutz",
        "pfad": "/datenschutz",
        "name": "Datenschutzerklärung",
        "indexierbar": False,
        "dateien": ("templates/datenschutz.html", "templates/layout.html"),
    },
    {
        "endpoint": "ueber_mich",
        "pfad": "/ueber-mich",
        "name": "Über mich",
        "dateien": ("templates/ueber_mich.html", "templates/layout.html"),
    },
)
INDEXIERBARE_PFADE = tuple(
    seite["pfad"]
    for seite in SEO_SEITEN
    if seite.get("indexierbar", True)
)
SEO_SEITEN_NACH_ENDPOINT = {seite["endpoint"]: seite for seite in SEO_SEITEN}
BERLINER_ZEITZONE = ZoneInfo("Europe/Berlin")
MESHCORE_REPEATER_APK_ORDNER = Path("/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator")
MESHCORE_REPEATER_ARCHIV_ORDNER = Path("/home/do1ffe/meshcore-repeater-konfigurator/artifacts")
MESHCORE_BLE_UPDATER_ORDNER = Path("/home/do1ffe/software-downloads/Meshcore-BLE-Updater")
MESHCORE_REGIONEN_ORDNER = Path("/home/do1ffe/meshcore-repeater-konfigurator/regionen-vorschlaege")
MESHCORE_REGIONEN_API_URL = os.getenv(
    "MESHCORE_REGIONEN_API_URL",
    "https://downloads.do1ffe.de/api/MeshCoreRepeaterKonfigurator/regionen",
)
MESHCORE_REGIONEN_API_TIMEOUT_SEKUNDEN = 4
MESHCORE_KOMMANDO_BESCHREIBUNGEN_DATEI = Path(__file__).with_name("daten") / "meshcore-kommandos-de.json"
MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER = Path("/home/do1ffe/software-downloads")
MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI = MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER / ".download-zaehler.json"
TEMP_CO2_STANDARD_DATEI = Path(__file__).with_name("daten") / "tempco2-aktuell.json"
TEMP_CO2_STANDARD_HISTORIE_DATEI = Path(__file__).with_name("daten") / "tempco2-historie.jsonl"
TEMP_CO2_STANDARD_MAX_ALTER_SEKUNDEN = 1800
TEMP_CO2_MAX_GRAPH_MESSWERTE = 3000
TEMP_CO2_HISTORIE_ZEITRÄUME = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "tag": timedelta(days=1),
    "woche": timedelta(days=7),
    "monat": timedelta(days=31),
    "6monate": timedelta(days=183),
    "jahr": timedelta(days=365),
}
TEMP_CO2_SPERRE = Lock()
MESHCORE_REPEATER_APK_MUSTER = "MeshCoreRepeaterKonfigurator-*-release-signed.apk"
MESHCORE_REPEATER_HISTORIE_AB_VERSION = "1.0.22"
MESHCORE_REPEATER_MAX_HISTORIE_VERSIONEN = 2
MESHCORE_FLASHER_BASIS_URL = "https://flasher.meshcore.io"
MESHCORE_FLASHER_START_URL = f"{MESHCORE_FLASHER_BASIS_URL}/"
MESHCORE_FLASHER_RELEASES_URL = f"{MESHCORE_FLASHER_BASIS_URL}/releases"
MESHCORE_FLASHER_TIMEOUT_SEKUNDEN = 8
MESHCORE_FLASHER_CACHE_DAUER_SEKUNDEN = 30 * 60
MESHCORE_FLASHER_FALLBACK_VERSION = "1.16.0"
FUNKBRUECKE_DOWNLOAD_ORDNER = Path("/home/do1ffe/software-downloads/FunkBruecke")
FUNKBRUECKE_DOWNLOAD_BASIS_URL = "https://downloads.do1ffe.de/FunkBruecke"
FUNKBRUECKE_EXE_REGEX = re.compile(
    r"^FunkBruecke-v(?P<version>\d+(?:\.\d+)*(?:-[0-9A-Za-z.-]+)?)-(?P<datum>\d{8})-win-x64\.exe$"
)
FUNKBRUECKE_DOWNLOAD_ARTEFAKTE = [
    {
        "schlüssel": "windows",
        "titel": "Windows-Programm",
        "dateiname": "FunkBruecke-latest-win-x64.exe",
        "typ": "EXE",
        "beschreibung": "Aktuelle Windows-x64-Version des FunkBrücke-Prototyps. Das Programm startet mit leerem Stationszustand, zeigt den Funkbetrieb als Chatverlauf, legt Nachrichten in eine Warteschlange und lässt die Sendeautomatik nach Kanal-, Audio-, PTT- und Mesh-Prüfung arbeiten. FB2, FT-991A-CAT, A-D-Mesh-Weiterleitung über B und C, Moduswahl, Monitor, Bedienfenster und FB2L-Livekarte sind für Tests vorbereitet.",
        "primär": True,
    },
    {
        "schlüssel": "bedienung",
        "titel": "Bedienungsanleitung",
        "dateiname": "FunkBruecke-Bedienungsanleitung-latest.pdf",
        "typ": "PDF",
        "beschreibung": "Bedienungsanleitung mit echten, markierten Programmansichten. Sie erklärt die erste Einrichtung, das erste QSO, Warteschlange, automatische Aussendung, Empfang, Mesh, FB2L-Karte, Audio, FT-991A-Sicherheit und die wichtigsten Fenster aus Anwendersicht.",
        "primär": False,
    },
    {
        "schlüssel": "changelog",
        "titel": "Changelog",
        "dateiname": "Changelog.txt",
        "typ": "Text",
        "beschreibung": "Laufend gepflegte Änderungshistorie des Projekts.",
        "primär": False,
        "öffentlich": False,
    },
    {
        "schlüssel": "fb2",
        "titel": "FB2-Übertragung",
        "dateiname": "FB2-Uebertragung.md",
        "typ": "Markdown",
        "beschreibung": "Technische Beschreibung der FB2-Übertragung: Rahmenaufbau, Modusleiter, Direktnachrichten, automatische Antworten, Kompression, Kanalprüfung, Mesh-Weiterleitung, Nachbarmodus-Aushandlung und FB2L-Heartbeats.",
        "primär": False,
    },
    {
        "schlüssel": "fb2-frequenzen",
        "titel": "FB2-Frequenzprofile",
        "dateiname": "FB2-Frequenzprofile.md",
        "typ": "Markdown",
        "beschreibung": "Vorsichtige Startprofile für KW, UKW, Bandplanfenster und bekannte Sperrfrequenzen.",
        "primär": False,
    },
]
MESHCORE_REPEATER_APK_REGEX = re.compile(
    r"^MeshCoreRepeaterKonfigurator-(?P<version>\d+(?:\.\d+)*)-release-signed\.apk$"
)
MESHCORE_BLE_UPDATER_ARTEFAKTE = {
    "android": {
        "plattform": "Android",
        "titel": "Android APK",
        "muster": "Meshcore-BLE-Updater-v*-release.apk",
        "regex": re.compile(r"^Meshcore-BLE-Updater-v(?P<version>\d+(?:\.\d+)*)-release\.apk$"),
        "endpoint": "meshcore_ble_updater_android_version",
        "latest_endpoint": "meshcore_ble_updater_android",
        "mimetype": "application/vnd.android.package-archive",
        "hinweis": "Signierte APK für Android mit Bluetooth Low Energy.",
    },
    "windows": {
        "plattform": "Windows",
        "titel": "Windows EXE",
        "muster": "Meshcore-BLE-Updater-Win-v*.exe",
        "regex": re.compile(r"^Meshcore-BLE-Updater-Win-v(?P<version>\d+(?:\.\d+)*)\.exe$"),
        "endpoint": "meshcore_ble_updater_windows_version",
        "latest_endpoint": "meshcore_ble_updater_windows",
        "mimetype": "application/vnd.microsoft.portable-executable",
        "hinweis": "GUI für Windows x64 mit gebündelter Laufzeit.",
    },
    "ios": {
        "plattform": "iOS",
        "titel": "iOS IPA",
        "muster": "Meshcore-BLE-Updater-iOS-v*-unsigned.ipa",
        "regex": re.compile(r"^Meshcore-BLE-Updater-iOS-v(?P<version>\d+(?:\.\d+)*)-unsigned\.ipa$"),
        "endpoint": "meshcore_ble_updater_ios_version",
        "latest_endpoint": "meshcore_ble_updater_ios",
        "mimetype": "application/octet-stream",
        "hinweis": "Unsigned IPA aus dem macOS/Xcode-Build; benötigt eigene iOS-Signierung.",
    },
}
DOWNLOAD_ZÄHLER_SPERRE = Lock()
DOWNLOAD_ZÄHLER_QUELLEN = {"button", "qr", "historie"}
DOWNLOAD_ZÄHLER_ENTPRELL_FENSTER_SEKUNDEN = 15 * 60
MESHCORE_FLASHER_CACHE_SPERRE = Lock()
MESHCORE_FLASHER_CACHE = {
    "zeit": 0,
    "daten": None,
}
MESHCORE_REGIONEN_CACHE_SPERRE = Lock()
MESHCORE_REGIONEN_CACHE = {
    "daten": None,
}
GITHUB_BENUTZER = "DO1FFE"
GITHUB_API_BASIS = "https://api.github.com"
GITHUB_API_TIMEOUT_SEKUNDEN = 6
GITHUB_CACHE_DAUER_SEKUNDEN = 15 * 60
GITHUB_CACHE_SPERRE = Lock()
GITHUB_CACHE = {
    "zeit": 0,
    "daten": None,
}
UMGEBUNGSDATEI_GELADEN = False
DEUTSCHE_MONATE = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
REGIONENKARTE_FARBEN = [
    "#0f766e",
    "#2457a6",
    "#b86e00",
    "#7c3aed",
    "#be123c",
    "#047857",
    "#c2410c",
    "#4338ca",
]
STANDARD_MESHCORE_REGIONEN = [
    {
        "schlüssel": "essen-ruhrgebiet",
        "stadt": "Essen",
        "land": "Deutschland",
        "bundesland": "Nordrhein-Westfalen",
        "stadtName": "Essen",
        "scopes": ["europe", "eu", "de", "de-west", "de-nw", "ruhrgebiet"],
        "denyScopes": [],
    },
]
MESHCORE_PROFILWEITE_SETUP_KOMMANDOS = [
    "set rxdelay 2",
    "set txdelay 0.8",
    "set direct.txdelay 0.4",
    "set flood.max 17",
]
MESHCORE_SETUP_KOMMANDOS = [
    "set radio.rxgain on",
    "set repeat on",
    "set af 9",
    "set dutycycle 10",
    "set advert.interval 60",
    "set flood.advert.interval 3",
    "set multi.acks 1",
    "set int.thresh 0",
    "set path.hash.mode 1",
    "set loop.detect minimal",
    *MESHCORE_PROFILWEITE_SETUP_KOMMANDOS,
]
MESHCORE_STANDARD_HOME_REGION = "de-nw"
MESHCORE_STANDARD_DEFAULT_REGION = "de"


REPOSITORIES = [
    {
        "name": "tesla-dashboard",
        "meta": "Python · aktualisiert Apr 2026",
        "beschreibung": "Ein Dashboard für den Tesla: Fahrzeugdaten, Karte, Statistik und Statuswerte.",
        "url": "https://github.com/DO1FFE/tesla-dashboard",
    },
    {
        "name": "991a-remote",
        "meta": "Python · Funkstation",
        "beschreibung": "Remote-Steuerung rund um die Funkstation, passend zur FT-991A-Schiene.",
        "url": "https://github.com/DO1FFE/991a-remote",
    },
    {
        "name": "CoreScope",
        "meta": "Fork · MeshCore",
        "beschreibung": "MeshCore-Analyzer für Live-Pakete, Replay, Node Health, Decryption und Analytics.",
        "url": "https://github.com/DO1FFE/CoreScope",
    },
    {
        "name": "Adventskalender-Webseite",
        "meta": "Python · OV L11",
        "beschreibung": "Ein Adventskalender für den Amateurfunkclub des DARC e.V. OV L11.",
        "url": "https://github.com/DO1FFE/Adventskalender-Webseite",
    },
    {
        "name": "ptt",
        "meta": "Python · MIT",
        "beschreibung": "PTT-Steuerung über COM-Port mit RTS/DTS: klein, konkret, funkpraktisch.",
        "url": "https://github.com/DO1FFE/ptt",
    },
    {
        "name": "club-payment",
        "meta": "Python · Club",
        "beschreibung": "Zahlungsterminal für die Clubstation, also Software direkt aus dem Vereinsalltag.",
        "url": "https://github.com/DO1FFE/club-payment",
    },
    {
        "name": "meshcore-network-monitor",
        "meta": "Python · Mesh",
        "beschreibung": "Monitoring für MeshCore-Netze, wenn Funkwege beobachtet werden sollen.",
        "url": "https://github.com/DO1FFE/meshcore-network-monitor",
    },
    {
        "name": "UDP-Router",
        "meta": "Python · AX.25",
        "beschreibung": "AX.25 UDP-Router: Funktechnik plus Netzwerkdenken.",
        "url": "https://github.com/DO1FFE/UDP-Router",
    },
    {
        "name": "qo100-ft991a",
        "meta": "Python · QO-100",
        "beschreibung": "FT-991A und QO-100 in einem Repo-Namen: genau die richtige Schnittstelle.",
        "url": "https://github.com/DO1FFE/qo100-ft991a",
    },
]

DIENSTE = [
    {
        "titel": "QR-Code-Generator",
        "domain": "qrcode.do1ffe.de",
        "kategorie": "Webwerkzeug",
        "beschreibung": (
            "QR-Code-Generator für URLs, Texte, E-Mail-Adressen, Telefonnummern, "
            "SMS-Vorlagen und Kontaktdaten. Eigene Codes können gestaltet, im Konto "
            "gespeichert und als PNG, JPG oder SVG heruntergeladen werden."
        ),
    },
    {
        "titel": "Tesla-Dashboard",
        "domain": "tesla.do1ffe.de",
        "kategorie": "Fahrzeugdaten",
        "beschreibung": (
            "Persönliches Dashboard für Fahrzeugstatus, Karte, Fahrdaten, "
            "Ladeinformationen, Temperaturen und Verlaufsauswertungen. Die Seite "
            "macht die wichtigsten Werte des Tesla sichtbar, ohne direkt auf die "
            "Tesla-App angewiesen zu sein."
        ),
    },
    {
        "titel": "Live-ÖPNV-Karte Essen",
        "domain": "rb.do1ffe.de",
        "kategorie": "Karte",
        "beschreibung": (
            "Live-Karte für Busse und Bahnen in Essen. Wenn echte Fahrzeugpositionen "
            "verfügbar sind, werden sie bevorzugt angezeigt; sonst werden Positionen "
            "aus GTFS-Realtime, Haltefolge und Prognosen nachvollziehbar geschätzt."
        ),
    },
    {
        "titel": "FunkBrücke FB2L",
        "domain": "fb2l.do1ffe.de",
        "kategorie": "Amateurfunk",
        "beschreibung": (
            "Livekarte für FunkBrücke-Stationen, Heartbeats, Nachbarwege und "
            "Mesh-Verbindungen. Die Ansicht zeigt, welche Stationen aktuell melden "
            "und welche Funkwege zwischen ihnen plausibel nutzbar sind."
        ),
    },
    {
        "titel": "Wetter Essen",
        "domain": "wetter.do1ffe.de",
        "kategorie": "Wetter",
        "beschreibung": (
            "Wetterübersicht für Essen mit Tagesansicht, Mehrtagesprognose und "
            "Kurzfristwerten. Neben der normalen Vorschau werden je nach Datenlage "
            "auch stündliche Werte, Wetterlage und Regenwahrscheinlichkeit angezeigt."
        ),
    },
    {
        "titel": "Frauen-WM 2027 Tippspiel",
        "domain": "wm2027.do1ffe.de",
        "kategorie": "Spiel",
        "beschreibung": (
            "Browser-Tippspiel zur Frauen-Weltmeisterschaft 2027 in Brasilien. "
            "Spielplan, Gruppen, Rangliste und private Tippgruppen kommen in einer "
            "gemeinsamen Oberfläche zusammen; die WM 2026 bleibt im Archiv erhalten."
        ),
    },
    {
        "titel": "Google-Geburtstagsimport",
        "domain": "calendar.do1ffe.de",
        "kategorie": "Webwerkzeug",
        "beschreibung": (
            "Überträgt Geburtstage und andere datierte Felder aus Google Kontakten "
            "nach eigener Freigabe in einen separaten Google Kalender. Der Abgleich "
            "wird bewusst gestartet und lässt sich anschließend wieder widerrufen."
        ),
    },
    {
        "titel": "Virtual Essen",
        "domain": "virtual.do1ffe.de",
        "kategorie": "Spiel",
        "beschreibung": (
            "Browserbasiertes Online-Spiel mit Essen-Karte, Login, Avatar, Chat "
            "und ersten Lebenssimulations-Elementen. Das Projekt verbindet eine "
            "2D-/2.5D-Spielwelt mit serverseitiger Echtzeitlogik."
        ),
    },
    {
        "titel": "Lernshack",
        "domain": "lernshack.do1ffe.de",
        "kategorie": "Amateurfunk",
        "beschreibung": (
            "Lernplattform für angehende Funkamateure mit Missionen, Übungen, "
            "Fortschrittssystem und virtuellem Funkgerät. Der Schwerpunkt liegt "
            "auf Klasse-N-Inhalten und einem spielbaren Einstieg in Funkpraxis."
        ),
    },
    {
        "titel": "RT3-zu-AnyTone-Konverter",
        "domain": "rt3any.do1ffe.de",
        "kategorie": "Funkwerkzeug",
        "beschreibung": (
            "Konverter für Retevis-RT3- und Tytera-MD-380-Codeplugs in ein "
            "AnyTone-Importpaket. Statt eine firmwareabhängige RDT-Datei zu "
            "erzeugen, nutzt das Werkzeug robuste CSV- und LST-Importdateien."
        ),
    },
    {
        "titel": "SofortGeschenk",
        "domain": "sofortgeschenk.do1ffe.de",
        "kategorie": "Webwerkzeug",
        "beschreibung": (
            "Webanwendung für personalisierte PDF-Geschenke. Nach Produktauswahl, "
            "Textangaben und Zahlung wird ein individuelles PDF erzeugt und als "
            "Download bereitgestellt."
        ),
    },
    {
        "titel": "IntroGen",
        "domain": "introgen.do1ffe.de",
        "kategorie": "Medien",
        "beschreibung": (
            "Generator für Video-Intros und Abspänne mit Vorlagen, Vorschau und "
            "MP4-Export. Die Anwendung richtet sich an einfache Video-Projekte, "
            "bei denen ein fertiger Einstieg oder Abschluss schnell erzeugt werden soll."
        ),
    },
    {
        "titel": "BNetzA-Rufzeichensuche",
        "domain": "rufzeichen.do1ffe.de",
        "kategorie": "Amateurfunk",
        "beschreibung": (
            "Rufzeichensuche auf Basis der veröffentlichten Amateurfunkliste der "
            "Bundesnetzagentur. Die PDF-Daten werden lokal aufbereitet und für "
            "schnelle Recherchen in einer kompakten Weboberfläche bereitgestellt."
        ),
    },
]


@app.after_request
def verhindere_dynamischen_cache(antwort):
    dynamische_endpunkte = {
        "meshcore",
        "meshcore_repeater_konfigurator_changelog",
        "meshcore_ble_updater_android",
        "meshcore_ble_updater_android_version",
        "meshcore_ble_updater_windows",
        "meshcore_ble_updater_windows_version",
        "meshcore_ble_updater_ios",
        "meshcore_ble_updater_ios_version",
        "funkbruecke",
        "tempco2_aktueller_messwert",
        "tempco2_historie",
        "tempco2_messwert_empfangen",
        "autobahn",
    }
    if request.endpoint in dynamische_endpunkte:
        antwort.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        antwort.headers["Pragma"] = "no-cache"
        antwort.headers["Expires"] = "0"
        antwort.headers["Surrogate-Control"] = "no-store"
    elif request.endpoint == "static" and antwort.status_code == 200:
        antwort.headers["Cache-Control"] = (
            "public, max-age=3600, stale-while-revalidate=86400"
        )

    seite = SEO_SEITEN_NACH_ENDPOINT.get(request.endpoint or "")
    if antwort.status_code >= 400:
        antwort.headers["X-Robots-Tag"] = ROBOTS_FEHLERSEITE
    elif request.path.startswith(("/api/", "/downloads/")):
        antwort.headers["X-Robots-Tag"] = "noindex,nofollow,nosnippet,noarchive"
    elif seite and request.query_string:
        antwort.headers["X-Robots-Tag"] = ROBOTS_NICHT_INDEXIERBAR
    elif seite and not seite.get("indexierbar", True):
        antwort.headers["X-Robots-Tag"] = ROBOTS_NICHT_INDEXIERBAR

    if antwort.mimetype == "text/html":
        antwort.headers.setdefault("Content-Language", "de")
    return antwort


def github_api_token():
    lade_umgebungsdatei()
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_API_TOKEN")


def lade_umgebungsdatei():
    global UMGEBUNGSDATEI_GELADEN
    if UMGEBUNGSDATEI_GELADEN:
        return
    UMGEBUNGSDATEI_GELADEN = True
    umgebungsdatei = Path(__file__).with_name(".env")
    if not umgebungsdatei.is_file():
        return
    try:
        zeilen = umgebungsdatei.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for zeile in zeilen:
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        schlüssel, wert = zeile.split("=", 1)
        schlüssel = schlüssel.strip()
        wert = wert.strip().strip("\"'")
        if schlüssel and schlüssel not in os.environ:
            os.environ[schlüssel] = wert


def strassenwetter_konfiguration():
    lade_umgebungsdatei()
    return road_weather.Konfiguration.aus_umgebung()


@app.cli.command("road-weather-update")
@click.option("--force", "erzwingen", is_flag=True, help="15-Minuten-Sperre für einen administrativen Test ignorieren.")
def strassenwetter_aktualisieren(erzwingen=False):
    """Lädt erlaubte Straßenwetterwerte in den lokalen SQLite-Speicher."""

    konfiguration = strassenwetter_konfiguration()
    try:
        ergebnis = road_weather.StrassenwetterSammler(konfiguration).aktualisiere(erzwingen=erzwingen)
    except (RuntimeError, ValueError) as fehler:
        raise click.ClickException(str(fehler)) from fehler
    click.echo(json.dumps(ergebnis, ensure_ascii=False, sort_keys=True))
    if ergebnis.get("status") == "error":
        raise click.ClickException(str(ergebnis.get("message") or "Straßenwetter-Abruf fehlgeschlagen"))


@app.cli.command("road-weather-cleanup")
def strassenwetter_historie_bereinigen():
    """Löscht ausschließlich abgelaufene Straßenwetter-Historieneinträge."""

    konfiguration = strassenwetter_konfiguration()
    anzahl = road_weather.StrassenwetterSpeicher(konfiguration.datenbank_pfad).bereinige_historie(
        konfiguration.aufbewahrung_tage
    )
    click.echo(f"{anzahl} abgelaufene Historieneinträge gelöscht.")


def hole_github_json(pfad, parameter=None):
    parameter = parameter or {}
    abfrage = f"?{urlencode(parameter)}" if parameter else ""
    anfrage = Request(
        f"{GITHUB_API_BASIS}{pfad}{abfrage}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "do1ffe-webseite",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    token = github_api_token()
    if token:
        anfrage.add_header("Authorization", f"Bearer {token}")
    with urlopen(anfrage, timeout=GITHUB_API_TIMEOUT_SEKUNDEN) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def parse_github_zeitpunkt(wert):
    if not wert:
        return None
    try:
        return datetime.fromisoformat(wert.replace("Z", "+00:00")).astimezone(BERLINER_ZEITZONE)
    except ValueError:
        return None


def formatiere_datum(zeitpunkt):
    if not zeitpunkt:
        return "unbekannt"
    return zeitpunkt.strftime("%d.%m.%Y")


def formatiere_monat_jahr(zeitpunkt):
    if not zeitpunkt:
        return "unbekannt"
    return f"{DEUTSCHE_MONATE[zeitpunkt.month - 1]} {zeitpunkt.year}"


def github_lizenz_name(repo):
    lizenz = repo.get("license")
    if not isinstance(lizenz, dict):
        return ""
    spdx = lizenz.get("spdx_id")
    if spdx and spdx != "NOASSERTION":
        return spdx
    return lizenz.get("name") or ""


def github_private_repo_anzahl():
    if not github_api_token():
        return None
    profil = hole_github_json("/user")
    login = str(profil.get("login") or "")
    if login.casefold() != GITHUB_BENUTZER.casefold():
        return None
    anzahl = profil.get("owned_private_repos")
    if anzahl is None:
        anzahl = profil.get("total_private_repos")
    try:
        return max(0, int(anzahl))
    except (TypeError, ValueError):
        return zähle_private_github_repos()


def zähle_private_github_repos():
    anzahl = 0
    for seite in range(1, 11):
        daten = hole_github_json(
            "/user/repos",
            {
                "per_page": 100,
                "page": seite,
                "visibility": "private",
                "affiliation": "owner",
                "sort": "updated",
                "direction": "desc",
            },
        )
        if not isinstance(daten, list):
            break
        anzahl += sum(1 for repo in daten if repo.get("private"))
        if len(daten) < 100:
            break
    return anzahl


def normalisiere_github_repo(repo):
    aktualisiert = parse_github_zeitpunkt(repo.get("updated_at"))
    sprache = repo.get("language") or "keine Hauptsprache"
    meta_teile = []
    if repo.get("fork"):
        meta_teile.append("Fork")
    meta_teile.append(sprache)
    meta_teile.append(f"aktualisiert {formatiere_datum(aktualisiert)}")
    lizenz = github_lizenz_name(repo)
    if lizenz:
        meta_teile.append(lizenz)
    return {
        "name": repo.get("name") or "Unbenanntes Repository",
        "beschreibung": repo.get("description") or "Keine Beschreibung auf GitHub hinterlegt.",
        "url": repo.get("html_url") or f"https://github.com/{GITHUB_BENUTZER}",
        "meta": " · ".join(meta_teile),
        "sprache": sprache,
        "sterne": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "offene_issues": int(repo.get("open_issues_count") or 0),
        "aktualisiert": formatiere_datum(aktualisiert),
        "aktualisiert_monat": formatiere_monat_jahr(aktualisiert),
        "aktualisiert_sortierung": aktualisiert or datetime.min.replace(tzinfo=BERLINER_ZEITZONE),
        "archiviert": bool(repo.get("archived")),
        "fork": bool(repo.get("fork")),
        "privat": bool(repo.get("private")),
        "topics": [str(topic) for topic in repo.get("topics") or []],
    }


def github_fallback_repos():
    repos = []
    for repo in REPOSITORIES:
        repos.append(
            {
                "name": repo["name"],
                "beschreibung": repo["beschreibung"],
                "url": repo["url"],
                "meta": repo["meta"],
                "sprache": repo["meta"].split(" · ", 1)[0],
                "sterne": 0,
                "forks": 0,
                "offene_issues": 0,
                "aktualisiert": "unbekannt",
                "aktualisiert_monat": "unbekannt",
                "aktualisiert_sortierung": datetime.min.replace(tzinfo=BERLINER_ZEITZONE),
                "archiviert": False,
                "fork": repo["meta"].casefold().startswith("fork"),
                "privat": False,
                "topics": [],
            }
        )
    return repos


def sammle_github_repos():
    repos = []
    for seite in range(1, 11):
        daten = hole_github_json(
            f"/users/{GITHUB_BENUTZER}/repos",
            {
                "per_page": 100,
                "page": seite,
                "sort": "updated",
                "direction": "desc",
            },
        )
        if not isinstance(daten, list):
            break
        repos.extend(daten)
        if len(daten) < 100:
            break
    return repos


def baue_github_statistik(profil, repos, live=True, fehler="", private_repos_anzahl=None):
    sprachen = Counter(repo["sprache"] for repo in repos if repo["sprache"] != "keine Hauptsprache")
    topics = Counter(topic for repo in repos for topic in repo["topics"])
    neustes_repo = max(repos, key=lambda repo: repo["aktualisiert_sortierung"], default=None)
    öffentliche_repos = profil.get("public_repos") if isinstance(profil, dict) else None
    if öffentliche_repos is None:
        öffentliche_repos = len(repos)
    häufige_sprachen = ", ".join(sprache for sprache, _ in sprachen.most_common(3)) or "keine Hauptsprache gepflegt"
    themen = ", ".join(topic for topic, _ in topics.most_common(5)) or "keine GitHub-Topics gepflegt"
    if neustes_repo:
        aktivität = f"zuletzt {neustes_repo['aktualisiert']} bei {neustes_repo['name']}"
        letzte_aktualisierung = neustes_repo["aktualisiert_monat"]
    else:
        aktivität = "keine öffentlichen Repositories gefunden"
        letzte_aktualisierung = "unbekannt"
    return {
        "anzahl_öffentlich": int(öffentliche_repos or 0),
        "anzahl_privat": private_repos_anzahl,
        "private_repos_verfügbar": private_repos_anzahl is not None,
        "angezeigte_repos": len(repos),
        "häufige_sprachen": häufige_sprachen,
        "themen": themen,
        "aktivität": aktivität,
        "letzte_aktualisierung": letzte_aktualisierung,
        "profil_url": (profil or {}).get("html_url") or f"https://github.com/{GITHUB_BENUTZER}",
        "login": (profil or {}).get("login") or GITHUB_BENUTZER,
        "quelle": "GitHub API" if live else "Fallback",
        "live": live,
        "fehler": fehler,
        "abgerufen_um": datetime.now(BERLINER_ZEITZONE).strftime("%d.%m.%Y, %H:%M"),
    }


def lade_github_daten_live():
    profil = hole_github_json(f"/users/{GITHUB_BENUTZER}")
    try:
        private_repos_anzahl = github_private_repo_anzahl()
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        private_repos_anzahl = None
    repos = [
        repo
        for repo in (normalisiere_github_repo(repo) for repo in sammle_github_repos())
        if not repo["privat"]
    ]
    repos.sort(key=lambda repo: repo["aktualisiert_sortierung"], reverse=True)
    return {
        "repos": repos,
        "repo_statistik": baue_github_statistik(
            profil,
            repos,
            live=True,
            private_repos_anzahl=private_repos_anzahl,
        ),
    }


def lade_github_daten():
    jetzt = time.time()
    zwischenspeicher = GITHUB_CACHE.get("daten")
    if zwischenspeicher and jetzt - GITHUB_CACHE.get("zeit", 0) < GITHUB_CACHE_DAUER_SEKUNDEN:
        return zwischenspeicher
    with GITHUB_CACHE_SPERRE:
        zwischenspeicher = GITHUB_CACHE.get("daten")
        if zwischenspeicher and jetzt - GITHUB_CACHE.get("zeit", 0) < GITHUB_CACHE_DAUER_SEKUNDEN:
            return zwischenspeicher
        try:
            daten = lade_github_daten_live()
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as fehler:
            if zwischenspeicher:
                return zwischenspeicher
            repos = github_fallback_repos()
            daten = {
                "repos": repos,
                "repo_statistik": baue_github_statistik(
                    {},
                    repos,
                    live=False,
                    fehler=f"{type(fehler).__name__}: {fehler}",
                ),
            }
        GITHUB_CACHE["zeit"] = jetzt
        GITHUB_CACHE["daten"] = daten
        return daten


def öffentliche_dienste():
    dienste = []
    for dienst in DIENSTE:
        eintrag = dict(dienst)
        eintrag["url"] = f"https://{dienst['domain']}/"
        dienste.append(eintrag)
    return dienste


def dienst_statistik(dienste):
    kategorien = Counter(dienst["kategorie"] for dienst in dienste)
    return {
        "anzahl": len(dienste),
        "kategorien": ", ".join(kategorie for kategorie, _ in kategorien.most_common()),
    }


def apk_version(datei):
    treffer = MESHCORE_REPEATER_APK_REGEX.match(datei.name)
    if not treffer:
        return ""
    return treffer.group("version")


def versions_sortierschlüssel(version):
    teile = [int(teil) for teil in version.split(".") if teil.isdigit()]
    return tuple((teile + [0, 0, 0, 0])[:4])


def apk_sortierschlüssel(datei):
    version = apk_version(datei)
    try:
        geändert = datei.stat().st_mtime
    except OSError:
        geändert = 0
    return versions_sortierschlüssel(version), geändert


def meshcore_ble_updater_version(datei, artefakt_schlüssel=None):
    artefakte = (
        {artefakt_schlüssel: MESHCORE_BLE_UPDATER_ARTEFAKTE.get(artefakt_schlüssel)}
        if artefakt_schlüssel
        else MESHCORE_BLE_UPDATER_ARTEFAKTE
    )
    for artefakt in artefakte.values():
        if not artefakt:
            continue
        treffer = artefakt["regex"].match(datei.name)
        if treffer:
            return treffer.group("version")
    return ""


def meshcore_ble_updater_sortierschlüssel(datei, artefakt_schlüssel=None):
    version = meshcore_ble_updater_version(datei, artefakt_schlüssel)
    try:
        geändert = datei.stat().st_mtime
    except OSError:
        geändert = 0
    return versions_sortierschlüssel(version), geändert


def ist_version_in_download_historie(version):
    return versions_sortierschlüssel(version) >= versions_sortierschlüssel(MESHCORE_REPEATER_HISTORIE_AB_VERSION)


def sammle_repeater_apks():
    dateien_nach_version = {}
    for ordner in [MESHCORE_REPEATER_ARCHIV_ORDNER, MESHCORE_REPEATER_APK_ORDNER]:
        if not ordner.exists():
            continue
        for datei in ordner.glob(MESHCORE_REPEATER_APK_MUSTER):
            if not datei.is_file():
                continue
            version = apk_version(datei)
            if version:
                dateien_nach_version[version] = datei
    return dateien_nach_version


def finde_neuste_repeater_apk():
    dateien = list(sammle_repeater_apks().values())
    if not dateien:
        return None
    return max(dateien, key=apk_sortierschlüssel)


def finde_repeater_apk_version(version):
    if not re.fullmatch(r"\d+(?:\.\d+)*", version or ""):
        return None
    return sammle_repeater_apks().get(version)


def sammle_meshcore_ble_updater_dateien():
    dateien = {}
    if not MESHCORE_BLE_UPDATER_ORDNER.exists():
        return dateien
    for schlüssel, artefakt in MESHCORE_BLE_UPDATER_ARTEFAKTE.items():
        passende_dateien = [
            datei
            for datei in MESHCORE_BLE_UPDATER_ORDNER.glob(artefakt["muster"])
            if datei.is_file() and meshcore_ble_updater_version(datei, schlüssel)
        ]
        if passende_dateien:
            dateien[schlüssel] = max(
                passende_dateien,
                key=lambda datei: meshcore_ble_updater_sortierschlüssel(datei, schlüssel),
            )
    return dateien


def finde_neuste_meshcore_ble_updater_datei(artefakt_schlüssel):
    return sammle_meshcore_ble_updater_dateien().get(artefakt_schlüssel)


def finde_meshcore_ble_updater_datei_version(artefakt_schlüssel, version):
    if not re.fullmatch(r"\d+(?:\.\d+)*", version or ""):
        return None
    artefakt = MESHCORE_BLE_UPDATER_ARTEFAKTE.get(artefakt_schlüssel)
    if not artefakt or not MESHCORE_BLE_UPDATER_ORDNER.exists():
        return None
    for datei in MESHCORE_BLE_UPDATER_ORDNER.glob(artefakt["muster"]):
        if datei.is_file() and meshcore_ble_updater_version(datei, artefakt_schlüssel) == version:
            return datei
    return None


def leerer_download_zähler():
    return {
        "schema": 1,
        "dateien": {},
    }


def normalisiere_download_zähler(daten):
    if not isinstance(daten, dict):
        return leerer_download_zähler()
    dateien = daten.get("dateien")
    if not isinstance(dateien, dict):
        dateien = {}
    return {
        "schema": 1,
        "dateien": dateien,
    }


def lade_download_zähler():
    if not MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI.exists():
        return leerer_download_zähler()
    try:
        daten = json.loads(MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return leerer_download_zähler()
    return normalisiere_download_zähler(daten)


def speichere_download_zähler(zähler):
    MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI.parent.mkdir(parents=True, exist_ok=True)
    temporär = MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI.with_suffix(".tmp")
    temporär.write_text(
        json.dumps(zähler, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporär.replace(MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI)


def download_versionskennung(datei):
    try:
        status = datei.stat()
    except OSError:
        return ""
    return f"{status.st_size}:{status.st_mtime_ns}"


def download_relativer_pfad(datei):
    try:
        return datei.relative_to(MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER).as_posix()
    except ValueError:
        return f"MeshCoreRepeaterKonfigurator/{datei.name}"


def download_zähler_eintrag(zähler, datei):
    dateien = zähler.get("dateien")
    if not isinstance(dateien, dict):
        return None
    eintrag = dateien.get(download_relativer_pfad(datei))
    if not isinstance(eintrag, dict):
        return None
    return eintrag


def download_anzahl(zähler, datei):
    eintrag = download_zähler_eintrag(zähler, datei)
    if not eintrag or eintrag.get("versionskennung") != download_versionskennung(datei):
        return 0
    try:
        return max(0, int(eintrag.get("downloads") or 0))
    except (TypeError, ValueError):
        return 0


def download_anzahl_für_übersicht(zähler, datei, zähler_nach_version):
    genaue_anzahl = download_anzahl(zähler, datei)
    try:
        datei.relative_to(MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER)
        return genaue_anzahl
    except ValueError:
        pass
    version = apk_version(datei)
    return zähler_nach_version.get(version, genaue_anzahl)


def downloads_nach_version_aus_zähler(zähler):
    dateien = zähler.get("dateien")
    if not isinstance(dateien, dict):
        return {}
    ergebnis = {}
    for pfad, eintrag in dateien.items():
        if not isinstance(pfad, str) or not isinstance(eintrag, dict):
            continue
        version = apk_version(Path(pfad))
        if not version:
            continue
        try:
            ergebnis[version] = max(0, int(eintrag.get("downloads") or 0))
        except (TypeError, ValueError):
            ergebnis[version] = 0
    return ergebnis


def download_entprell_datei():
    return MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI.with_name("download-zaehler-entprellung.json")


def lade_download_entprellung():
    datei = download_entprell_datei()
    if not datei.exists():
        return {}
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(daten, dict):
        return {}
    einträge = daten.get("einträge", daten)
    if not isinstance(einträge, dict):
        return {}
    ergebnis = {}
    for schlüssel, zeitstempel in einträge.items():
        try:
            ergebnis[str(schlüssel)] = float(zeitstempel)
        except (TypeError, ValueError):
            continue
    return ergebnis


def speichere_download_entprellung(einträge):
    datei = download_entprell_datei()
    datei.parent.mkdir(parents=True, exist_ok=True)
    temporär = datei.with_suffix(".tmp")
    temporär.write_text(
        json.dumps({"einträge": einträge}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporär.replace(datei)


def download_quelle():
    return request.args.get("quelle", "").strip().casefold()


def download_client_fingerprint():
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
    ip = forwarded_for or request.remote_addr or ""
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    roh = "\n".join([ip, user_agent, accept_language])
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def download_entprell_schlüssel(version, datei=None):
    datei_schlüssel = download_relativer_pfad(datei) if datei is not None else ""
    return ":".join([version, datei_schlüssel, download_quelle(), download_client_fingerprint()])


def download_ist_neu_genug(version, datei=None, jetzt=None):
    jetzt = time.time() if jetzt is None else jetzt
    schlüssel = download_entprell_schlüssel(version, datei)
    einträge = lade_download_entprellung()
    frist = jetzt - DOWNLOAD_ZÄHLER_ENTPRELL_FENSTER_SEKUNDEN
    einträge = {
        alter_schlüssel: alter_zeitstempel
        for alter_schlüssel, alter_zeitstempel in einträge.items()
        if alter_zeitstempel >= frist
    }
    letzter_zeitstempel = einträge.get(schlüssel)
    einträge[schlüssel] = jetzt
    speichere_download_entprellung(einträge)
    return letzter_zeitstempel is None or letzter_zeitstempel < frist


def erhöhe_download_zähler(version, datei):
    with DOWNLOAD_ZÄHLER_SPERRE:
        if not download_ist_neu_genug(version, datei):
            return None
        zähler = lade_download_zähler()
        dateien = zähler.setdefault("dateien", {})
        relativer_pfad = download_relativer_pfad(datei)
        versionskennung = download_versionskennung(datei)
        eintrag = dateien.get(relativer_pfad)
        if (
            isinstance(eintrag, dict)
            and eintrag.get("versionskennung") == versionskennung
        ):
            downloads = download_anzahl(zähler, datei)
        else:
            downloads = 0
        dateien[relativer_pfad] = {
            "downloads": downloads + 1,
            "versionskennung": versionskennung,
        }
        speichere_download_zähler(zähler)
        return downloads + 1


def formatiere_dateigröße(größe):
    if größe >= 1024 * 1024:
        return f"{größe / (1024 * 1024):.1f} MiB".replace(".", ",")
    return f"{größe / 1024:.0f} KiB"


def formatiere_dateizeit_aus_status(status):
    return datetime.fromtimestamp(
        status.st_mtime,
        BERLINER_ZEITZONE,
    ).strftime("%d.%m.%Y, %H:%M")


def funkbruecke_versionierte_exes():
    if not FUNKBRUECKE_DOWNLOAD_ORDNER.exists():
        return []
    dateien = []
    for datei in FUNKBRUECKE_DOWNLOAD_ORDNER.glob("FunkBruecke-v*-win-x64.exe"):
        if datei.is_file() and FUNKBRUECKE_EXE_REGEX.match(datei.name):
            dateien.append(datei)
    return sorted(dateien, key=funkbruecke_exe_sortierschlüssel, reverse=True)


def funkbruecke_exe_sortierschlüssel(datei):
    treffer = FUNKBRUECKE_EXE_REGEX.match(datei.name)
    if not treffer:
        return ((), 0, 0)
    try:
        geändert = datei.stat().st_mtime
    except OSError:
        geändert = 0
    return (
        versions_sortierschlüssel(treffer.group("version")),
        int(treffer.group("datum")),
        geändert,
    )


def funkbruecke_versionsinfo():
    dateien = funkbruecke_versionierte_exes()
    if not dateien:
        return {
            "version": "aktuelle Beta",
            "datum": "",
            "dateiname": "",
        }
    datei = dateien[0]
    treffer = FUNKBRUECKE_EXE_REGEX.match(datei.name)
    if not treffer:
        return {
            "version": "aktuelle Beta",
            "datum": "",
            "dateiname": datei.name,
        }
    datum_roh = treffer.group("datum")
    try:
        datum = datetime.strptime(datum_roh, "%Y%m%d").strftime("%d.%m.%Y")
    except ValueError:
        datum = ""
    return {
        "version": f"v{treffer.group('version')}",
        "datum": datum,
        "dateiname": datei.name,
    }


def baue_funkbruecke_download_info(artefakt):
    datei = FUNKBRUECKE_DOWNLOAD_ORDNER / artefakt["dateiname"]
    basis = {
        **artefakt,
        "url": f"{FUNKBRUECKE_DOWNLOAD_BASIS_URL}/{artefakt['dateiname']}",
        "größe": "",
        "geändert": "",
        "verfügbar": False,
    }
    if not datei.is_file():
        return basis
    try:
        status = datei.stat()
    except OSError:
        return basis
    basis.update({
        "größe": formatiere_dateigröße(status.st_size),
        "geändert": formatiere_dateizeit_aus_status(status),
        "verfügbar": True,
    })
    return basis


def funkbruecke_download_daten():
    downloads = [baue_funkbruecke_download_info(artefakt) for artefakt in FUNKBRUECKE_DOWNLOAD_ARTEFAKTE]
    haupt_download = next((download for download in downloads if download["primär"]), None)
    dokumente = [
        download
        for download in downloads
        if not download["primär"] and download.get("öffentlich", True)
        and download["verfügbar"]
    ]
    return {
        "funkbruecke_version": funkbruecke_versionsinfo(),
        "funkbruecke_haupt_download": haupt_download,
        "funkbruecke_dokumente": dokumente,
        "funkbruecke_download_basis_url": FUNKBRUECKE_DOWNLOAD_BASIS_URL,
    }


def baue_apk_info(version, datei, downloads):
    if datei is None:
        return {
            "dateiname": "",
            "downloads": downloads,
            "geändert": "",
            "größe": "",
            "verfügbar": False,
            "version": version,
        }
    try:
        status = datei.stat()
    except OSError:
        return None
    return {
        "dateiname": datei.name,
        "downloads": downloads,
        "geändert": datetime.fromtimestamp(
            status.st_mtime,
            BERLINER_ZEITZONE,
        ).strftime("%d.%m.%Y, %H:%M"),
        "größe": formatiere_dateigröße(status.st_size),
        "verfügbar": True,
        "version": version,
    }


def baue_meshcore_ble_updater_info(artefakt_schlüssel, datei, downloads):
    artefakt = MESHCORE_BLE_UPDATER_ARTEFAKTE[artefakt_schlüssel]
    version = meshcore_ble_updater_version(datei, artefakt_schlüssel) if datei is not None else ""
    basis = {
        "dateiname": "",
        "downloads": downloads,
        "endpoint": artefakt["endpoint"],
        "geändert": "",
        "größe": "",
        "hinweis": artefakt["hinweis"],
        "latest_endpoint": artefakt["latest_endpoint"],
        "plattform": artefakt["plattform"],
        "titel": artefakt["titel"],
        "verfügbar": False,
        "version": version,
        "schlüssel": artefakt_schlüssel,
    }
    if datei is None:
        return basis
    try:
        status = datei.stat()
    except OSError:
        return None
    basis.update({
        "dateiname": datei.name,
        "geändert": datetime.fromtimestamp(
            status.st_mtime,
            BERLINER_ZEITZONE,
        ).strftime("%d.%m.%Y, %H:%M"),
        "größe": formatiere_dateigröße(status.st_size),
        "verfügbar": True,
    })
    return basis


def meshcore_ble_updater_übersicht():
    dateien = sammle_meshcore_ble_updater_dateien()
    zähler = lade_download_zähler()
    infos = []
    for schlüssel in MESHCORE_BLE_UPDATER_ARTEFAKTE:
        datei = dateien.get(schlüssel)
        downloads = download_anzahl(zähler, datei) if datei is not None else 0
        info = baue_meshcore_ble_updater_info(schlüssel, datei, downloads)
        if info is not None:
            infos.append(info)
    versionen = [
        info["version"]
        for info in infos
        if info["verfügbar"] and info["version"]
    ]
    aktuelle_version = max(versionen, key=versions_sortierschlüssel) if versionen else ""
    return {
        "version": aktuelle_version,
        "downloads": infos,
        "verfügbar": any(info["verfügbar"] for info in infos),
    }


def repeater_changelog_datei():
    return MESHCORE_REPEATER_APK_ORDNER / "Changelog.txt"


def repeater_changelog_verfügbar():
    return repeater_changelog_datei().is_file()


def textwert(wert, maximale_länge=160):
    if not isinstance(wert, str):
        return ""
    return " ".join(wert.strip().split())[:maximale_länge]


def text_liste(wert):
    if isinstance(wert, str):
        return [wert] if wert else []
    if isinstance(wert, list):
        return [eintrag for eintrag in wert if isinstance(eintrag, str) and eintrag]
    return []


def lade_regionen_json_dateien():
    if not MESHCORE_REGIONEN_ORDNER.is_dir():
        return []
    daten = []
    for datei in sorted(MESHCORE_REGIONEN_ORDNER.glob("region-*.json")):
        try:
            eintrag = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(eintrag, dict):
            daten.append(eintrag)
    return daten


def erster_text(wert, standard=""):
    texte = text_liste(wert)
    if texte:
        return texte[0]
    text = textwert(wert)
    return text or standard


def meshcore_profil_kommandos(scopes, deny_scopes, home_region, default_region, set_kommandos=None):
    kommandos = list(set_kommandos or MESHCORE_SETUP_KOMMANDOS)
    for scope in scopes:
        kommandos.append(f"region put {scope}")
        kommandos.append(f"region allowf {scope}")
    for scope in deny_scopes:
        kommandos.append(f"region denyf {scope}")
    if home_region:
        kommandos.append(f"region home {home_region}")
    if default_region:
        kommandos.append(f"region default {default_region}")
    kommandos.append("region save")
    return kommandos


def meshcore_profilweite_setup_kommandos_ergänzen(kommandos):
    erzwungene_schlüssel = {
        kommando.split(maxsplit=2)[1]
        for kommando in MESHCORE_PROFILWEITE_SETUP_KOMMANDOS
    }
    freie_kommandos = [
        kommando
        for kommando in kommandos
        if len(kommando.split(maxsplit=2)) < 2
        or kommando.split(maxsplit=2)[1] not in erzwungene_schlüssel
    ]
    return freie_kommandos + list(MESHCORE_PROFILWEITE_SETUP_KOMMANDOS)


def lade_meshcore_kommando_beschreibungen():
    try:
        daten = json.loads(MESHCORE_KOMMANDO_BESCHREIBUNGEN_DATEI.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return daten if isinstance(daten, dict) else {}


def formatiere_meshcore_beschreibung(vorlage, **werte):
    if not isinstance(vorlage, str) or not vorlage:
        return ""
    try:
        return vorlage.format(**werte)
    except (KeyError, ValueError):
        return ""


def meshcore_parameter_kommando_erklärung(kommando, beschreibungen):
    teile = kommando.split(maxsplit=2)
    if len(teile) < 2 or teile[0] not in {"get", "set"}:
        return ""

    aktion, parameter = teile[:2]
    wert = teile[2] if len(teile) == 3 else ""
    parameter_kommandos = beschreibungen.get("parameterKommandos")
    parameter_beschreibung = (
        parameter_kommandos.get(parameter)
        if isinstance(parameter_kommandos, dict)
        else None
    )
    if isinstance(parameter_beschreibung, dict):
        schlüssel = "lesen" if aktion == "get" else "setzen"
        beschreibung = formatiere_meshcore_beschreibung(
            parameter_beschreibung.get(schlüssel),
            parameter=parameter,
            wert=wert,
        )
        if beschreibung:
            return beschreibung

    fallback = beschreibungen.get("fallback")
    vorlage = fallback.get(aktion) if isinstance(fallback, dict) else ""
    return formatiere_meshcore_beschreibung(
        vorlage,
        parameter=parameter,
        wert=wert,
    )


def meshcore_kommando_erklärung(kommando):
    beschreibungen = lade_meshcore_kommando_beschreibungen()
    exakte_kommandos = beschreibungen.get("exakteKommandos")
    if isinstance(exakte_kommandos, dict):
        beschreibung = exakte_kommandos.get(kommando)
        if isinstance(beschreibung, str) and beschreibung:
            return beschreibung

    parameter_beschreibung = meshcore_parameter_kommando_erklärung(
        kommando,
        beschreibungen,
    )
    if parameter_beschreibung:
        return parameter_beschreibung

    präfix_kommandos = beschreibungen.get("präfixKommandos")
    if isinstance(präfix_kommandos, list):
        for eintrag in präfix_kommandos:
            if not isinstance(eintrag, dict):
                continue
            präfix = eintrag.get("präfix")
            beschreibung = eintrag.get("beschreibung")
            if isinstance(präfix, str) and isinstance(beschreibung, str) and kommando.startswith(präfix):
                formatierte_beschreibung = formatiere_meshcore_beschreibung(
                    beschreibung,
                    wert=kommando.removeprefix(präfix),
                )
                if formatierte_beschreibung:
                    return formatierte_beschreibung
    fallback = beschreibungen.get("fallback")
    if isinstance(fallback, dict):
        beschreibung = fallback.get(kommando) or fallback.get("*")
        if isinstance(beschreibung, str) and beschreibung:
            return beschreibung
    return "Sendet dieses Kommando an den verbundenen Repeater."


def meshcore_kommando_details(kommandos):
    return [
        {
            "kommando": kommando,
            "erklärung": meshcore_kommando_erklärung(kommando),
        }
        for kommando in kommandos
    ]


def meshcore_regionenkarte_fallback_punkte():
    punkte = []
    datenquellen = {}
    for daten in [*STANDARD_MESHCORE_REGIONEN, *lade_regionen_json_dateien()]:
        region_id = textwert(daten.get("schlüssel") or daten.get("id"))
        if region_id:
            datenquellen[region_id] = daten
    for daten in datenquellen.values():
        region_id = textwert(daten.get("schlüssel") or daten.get("id"))
        stadt_name = textwert(daten.get("stadtName"))
        stadt = textwert(daten.get("stadt") or stadt_name)
        land = textwert(daten.get("land"))
        bundesland = textwert(daten.get("bundesland"))
        scopes = text_liste(daten.get("scopes"))
        deny_scopes = text_liste(daten.get("denyScopes"))
        home_region = erster_text(
            daten.get("homeRegionen") if "homeRegionen" in daten else daten.get("homeRegion"),
            MESHCORE_STANDARD_HOME_REGION,
        )
        default_region = erster_text(
            daten.get("defaultRegionen") if "defaultRegionen" in daten else daten.get("defaultRegion"),
            MESHCORE_STANDARD_DEFAULT_REGION,
        )
        set_kommandos = meshcore_profilweite_setup_kommandos_ergänzen(
            text_liste(daten.get("setKommandos")) or MESHCORE_SETUP_KOMMANDOS
        )
        if not region_id or not stadt_name or not land or not scopes:
            continue
        kommandos = meshcore_profil_kommandos(
            scopes,
            deny_scopes,
            home_region,
            default_region,
            set_kommandos,
        )
        punkte.append({
            "id": region_id,
            "stadt": stadt or stadt_name,
            "stadtName": stadt_name,
            "istStadt": True,
            "land": land,
            "bundesland": bundesland,
            "allow": scopes,
            "disallow": deny_scopes,
            "home": home_region,
            "default": default_region,
            "kommandos": kommandos,
            "kommandoDetails": meshcore_kommando_details(kommandos),
            "farbe": REGIONENKARTE_FARBEN[(len(punkte)) % len(REGIONENKARTE_FARBEN)],
        })
    return sorted(
        punkte,
        key=lambda punkt: (
            punkt["land"].casefold(),
            punkt["bundesland"].casefold(),
            punkt["stadtName"].casefold(),
        ),
    )


def hole_meshcore_regionen_api():
    anfrage = Request(
        MESHCORE_REGIONEN_API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "do1ffe-webseite",
        },
    )
    with urlopen(anfrage, timeout=MESHCORE_REGIONEN_API_TIMEOUT_SEKUNDEN) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def normalisiere_meshcore_regionen_api(daten):
    if not isinstance(daten, dict) or not isinstance(daten.get("profile"), list):
        raise ValueError("Die Regionen-API enthält keine Profilliste.")

    gemeinsame_einstellungen = daten.get("gemeinsameEinstellungen")
    if not isinstance(gemeinsame_einstellungen, dict):
        gemeinsame_einstellungen = {}
    basis_kommandos = set(text_liste(gemeinsame_einstellungen.get("basisKommandos")))

    punkte = []
    for profil in daten["profile"]:
        if not isinstance(profil, dict):
            continue
        region_id = textwert(profil.get("id"))
        name = textwert(profil.get("name") or profil.get("stadt"))
        stadt_name = textwert(profil.get("stadt"))
        land = textwert(profil.get("land"))
        bundesland = textwert(profil.get("bundesland"))
        scopes = text_liste(profil.get("allowScopes") or profil.get("scopes"))
        deny_scopes = text_liste(profil.get("denyScopes"))
        home_region = erster_text(
            profil.get("homeRegionen") if "homeRegionen" in profil else profil.get("homeRegion"),
            MESHCORE_STANDARD_HOME_REGION,
        )
        default_region = erster_text(
            profil.get("defaultRegionen") if "defaultRegionen" in profil else profil.get("defaultRegion"),
            MESHCORE_STANDARD_DEFAULT_REGION,
        )
        kommandos = [
            kommando
            for kommando in text_liste(profil.get("kommandos"))
            if kommando not in basis_kommandos
        ]
        if not region_id or not name or not land or not scopes or not kommandos:
            continue

        punkte.append({
            "id": region_id,
            "stadt": name,
            "stadtName": stadt_name,
            "istStadt": bool(stadt_name),
            "land": land,
            "bundesland": bundesland,
            "allow": scopes,
            "disallow": deny_scopes,
            "home": home_region,
            "default": default_region,
            "kommandos": kommandos,
            "kommandoDetails": meshcore_kommando_details(kommandos),
            "farbe": REGIONENKARTE_FARBEN[len(punkte) % len(REGIONENKARTE_FARBEN)],
        })

    if not punkte:
        raise ValueError("Die Regionen-API enthält keine gültigen Profile.")

    return sorted(
        punkte,
        key=lambda punkt: (
            punkt["land"].casefold(),
            2 if punkt["istStadt"] else 1 if punkt["bundesland"] else 0,
            punkt["bundesland"].casefold(),
            punkt["stadt"].casefold(),
        ),
    )


def meshcore_regionenkarte_punkte():
    zwischenspeicher = MESHCORE_REGIONEN_CACHE.get("daten")
    if MESHCORE_REGIONEN_API_URL:
        try:
            punkte = normalisiere_meshcore_regionen_api(hole_meshcore_regionen_api())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            punkte = zwischenspeicher
        else:
            with MESHCORE_REGIONEN_CACHE_SPERRE:
                MESHCORE_REGIONEN_CACHE["daten"] = punkte

        if punkte:
            return punkte

    return meshcore_regionenkarte_fallback_punkte()


def meshcore_repeater_apk_übersicht():
    dateien_nach_version = sammle_repeater_apks()
    zähler = lade_download_zähler()
    zähler_nach_version = downloads_nach_version_aus_zähler(zähler)
    infos = []
    for version in sorted(dateien_nach_version, key=versions_sortierschlüssel, reverse=True):
        datei = dateien_nach_version.get(version)
        info = baue_apk_info(version, datei, download_anzahl_für_übersicht(zähler, datei, zähler_nach_version))
        if info is not None:
            infos.append(info)
    if not infos:
        return None, []
    fehlende_versionen = set(zähler_nach_version) - set(dateien_nach_version)
    historie = [info for info in infos[1:] if ist_version_in_download_historie(info["version"])]
    for version in sorted(fehlende_versionen, key=versions_sortierschlüssel, reverse=True):
        if not ist_version_in_download_historie(version):
            continue
        historie.append(baue_apk_info(version, None, zähler_nach_version.get(version, 0)))
    historie = sorted(
        [info for info in historie if info is not None],
        key=lambda info: versions_sortierschlüssel(info["version"]),
        reverse=True,
    )[:MESHCORE_REPEATER_MAX_HISTORIE_VERSIONEN]
    return infos[0], historie


def meshcore_flasher_versions_sortierschlüssel(version):
    treffer = re.search(r"(\d+(?:\.\d+)*)", str(version or ""))
    if not treffer:
        return ()
    return tuple(int(teil) for teil in treffer.group(1).split("."))


def bereinige_meshcore_flasher_version(version):
    treffer = re.search(r"(\d+(?:\.\d+)*)", str(version or ""))
    return treffer.group(1) if treffer else ""


def ermittle_meshcore_sensecap_solar_repeater_firmware(releases):
    versionen = []
    dateimuster = re.compile(r"SenseCap_Solar_[rR]epeater.*?\.(?:zip|uf2)$")
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("type") != "repeater":
            continue
        dateien = release.get("files")
        if not isinstance(dateien, list):
            continue
        if any(dateimuster.search(str(datei.get("name") or "")) for datei in dateien if isinstance(datei, dict)):
            version = bereinige_meshcore_flasher_version(release.get("version"))
            if version:
                versionen.append(version)

    if not versionen:
        return None

    version = max(versionen, key=meshcore_flasher_versions_sortierschlüssel)
    return {
        "version": version,
        "verfügbar": True,
        "quelle": "meshcore.io",
        "url": MESHCORE_FLASHER_START_URL,
        "abgerufen_um": datetime.now(BERLINER_ZEITZONE).strftime("%d.%m.%Y, %H:%M"),
        "fehler": "",
    }


def hole_meshcore_flasher_releases():
    anfrage = Request(
        MESHCORE_FLASHER_RELEASES_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "do1ffe-webseite",
        },
    )
    with urlopen(anfrage, timeout=MESHCORE_FLASHER_TIMEOUT_SEKUNDEN) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def meshcore_repeater_firmware_fallback(fehler=""):
    return {
        "version": MESHCORE_FLASHER_FALLBACK_VERSION,
        "verfügbar": False,
        "quelle": "Fallback",
        "url": MESHCORE_FLASHER_START_URL,
        "abgerufen_um": "",
        "fehler": fehler,
    }


def lade_meshcore_repeater_firmware():
    jetzt = time.time()
    zwischenspeicher = MESHCORE_FLASHER_CACHE.get("daten")
    if zwischenspeicher and jetzt - MESHCORE_FLASHER_CACHE.get("zeit", 0) < MESHCORE_FLASHER_CACHE_DAUER_SEKUNDEN:
        return zwischenspeicher

    with MESHCORE_FLASHER_CACHE_SPERRE:
        zwischenspeicher = MESHCORE_FLASHER_CACHE.get("daten")
        if zwischenspeicher and jetzt - MESHCORE_FLASHER_CACHE.get("zeit", 0) < MESHCORE_FLASHER_CACHE_DAUER_SEKUNDEN:
            return zwischenspeicher

        try:
            daten = ermittle_meshcore_sensecap_solar_repeater_firmware(hole_meshcore_flasher_releases())
            if daten is None:
                raise ValueError("Keine SenseCAP-Solar-Repeater-Firmware in den MeshCore-Releases gefunden.")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as fehler:
            daten = zwischenspeicher or meshcore_repeater_firmware_fallback(f"{type(fehler).__name__}: {fehler}")

        MESHCORE_FLASHER_CACHE["zeit"] = jetzt
        MESHCORE_FLASHER_CACHE["daten"] = daten
        return daten


def sende_repeater_apk(datei):
    version = apk_version(datei)
    if not version:
        abort(404)
    if request.method == "GET" and download_soll_gezählt_werden():
        erhöhe_download_zähler(version, datei)
    return send_file(
        datei,
        as_attachment=True,
        download_name=datei.name,
        mimetype="application/vnd.android.package-archive",
        max_age=0,
    )


def sende_meshcore_ble_updater_datei(artefakt_schlüssel, datei):
    artefakt = MESHCORE_BLE_UPDATER_ARTEFAKTE.get(artefakt_schlüssel)
    if not artefakt:
        abort(404)
    version = meshcore_ble_updater_version(datei, artefakt_schlüssel)
    if not version:
        abort(404)
    if request.method == "GET" and download_soll_gezählt_werden():
        erhöhe_download_zähler(version, datei)
    return send_file(
        datei,
        as_attachment=True,
        download_name=datei.name,
        mimetype=artefakt["mimetype"],
        max_age=0,
    )


def download_soll_gezählt_werden():
    return download_quelle() in DOWNLOAD_ZÄHLER_QUELLEN


def kanonische_url(pfad):
    return f"{KANONISCHE_BASIS_URL}{pfad}"


def projekt_dateipfad(relativer_pfad):
    return Path(__file__).resolve().parent / relativer_pfad


def sitemap_lastmod(seite):
    zeitpunkte = []
    for relativer_pfad in seite.get("dateien", ()):
        try:
            zeitpunkte.append(projekt_dateipfad(relativer_pfad).stat().st_mtime)
        except OSError:
            continue
    if not zeitpunkte:
        try:
            zeitpunkte.append(Path(__file__).stat().st_mtime)
        except OSError:
            zeitpunkte.append(time.time())
    return datetime.fromtimestamp(max(zeitpunkte), timezone.utc).date().isoformat()


def tempco2_upload_token():
    lade_umgebungsdatei()
    return os.environ.get("TEMP_CO2_UPLOAD_TOKEN", "").strip()


def tempco2_daten_datei():
    lade_umgebungsdatei()
    pfad = os.environ.get("TEMP_CO2_DATEN_DATEI", "").strip()
    return Path(pfad) if pfad else TEMP_CO2_STANDARD_DATEI


def tempco2_historie_datei():
    lade_umgebungsdatei()
    pfad = os.environ.get("TEMP_CO2_HISTORIE_DATEI", "").strip()
    return Path(pfad) if pfad else TEMP_CO2_STANDARD_HISTORIE_DATEI


def tempco2_max_alter_sekunden():
    lade_umgebungsdatei()
    wert = os.environ.get("TEMP_CO2_MAX_ALTER_SEKUNDEN", "").strip()
    if not wert:
        return TEMP_CO2_STANDARD_MAX_ALTER_SEKUNDEN
    try:
        return max(30, int(wert))
    except ValueError:
        return TEMP_CO2_STANDARD_MAX_ALTER_SEKUNDEN


def tempco2_token_aus_anfrage():
    autorisierung = request.headers.get("Authorization", "").strip()
    if autorisierung.casefold().startswith("bearer "):
        return autorisierung[7:].strip()
    return request.headers.get("X-TempCO2-Token", "").strip()


def tempco2_token_ist_gültig():
    erwarteter_token = tempco2_upload_token()
    if not erwarteter_token:
        return False
    return hmac.compare_digest(erwarteter_token, tempco2_token_aus_anfrage())


def tempco2_utc_jetzt_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def tempco2_parse_utc(wert):
    if not isinstance(wert, str) or not wert.strip():
        return None
    try:
        zeitpunkt = datetime.fromisoformat(wert.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    return zeitpunkt.astimezone(timezone.utc)


def tempco2_zahl(daten, schlüssel, minimum, maximum, typ=float):
    try:
        wert = typ(daten.get(schlüssel))
    except (TypeError, ValueError):
        raise ValueError(f"Ungültiger Wert für {schlüssel}.") from None
    if wert < minimum or wert > maximum:
        raise ValueError(f"Wert für {schlüssel} außerhalb des gültigen Bereichs.")
    return wert


def tempco2_text(daten, schlüssel, standard=""):
    wert = daten.get(schlüssel, standard)
    if wert is None:
        return standard
    return str(wert).strip()


def tempco2_normalisiere_messwert(daten):
    if not isinstance(daten, dict):
        raise ValueError("JSON-Objekt erwartet.")

    empfangen_utc = tempco2_utc_jetzt_iso()
    zeit_utc = tempco2_text(daten, "zeit_utc", empfangen_utc) or empfangen_utc
    if tempco2_parse_utc(zeit_utc) is None:
        zeit_utc = empfangen_utc

    return {
        "zeit_utc": zeit_utc,
        "empfangen_utc": empfangen_utc,
        "geraete_adresse": tempco2_text(daten, "geraete_adresse"),
        "geraetename": tempco2_text(daten, "geraetename") or None,
        "temperatur_c": round(tempco2_zahl(daten, "temperatur_c", -40, 85, float), 1),
        "luftfeuchtigkeit_prozent": int(tempco2_zahl(daten, "luftfeuchtigkeit_prozent", 0, 100, int)),
        "co2_ppm": int(tempco2_zahl(daten, "co2_ppm", 0, 9999, int)),
        "batterie_prozent": int(tempco2_zahl(daten, "batterie_prozent", 0, 100, int)),
        "rssi_dbm": int(tempco2_zahl(daten, "rssi_dbm", -127, 20, int)),
    }


def tempco2_speichere_messwert(messwert):
    datei = tempco2_daten_datei()
    datei.parent.mkdir(parents=True, exist_ok=True)
    temporär = datei.with_suffix(".tmp")
    temporär.write_text(
        json.dumps(messwert, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporär.replace(datei)


def tempco2_speichere_historie(messwert):
    datei = tempco2_historie_datei()
    datei.parent.mkdir(parents=True, exist_ok=True)
    with datei.open("a", encoding="utf-8") as verlauf:
        verlauf.write(json.dumps(messwert, ensure_ascii=False, sort_keys=True) + "\n")


def tempco2_lade_messwert():
    datei = tempco2_daten_datei()
    if not datei.is_file():
        return None
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(daten, dict):
        return None
    return daten


def tempco2_lade_historie(seit_utc):
    datei = tempco2_historie_datei()
    if not datei.is_file():
        return []

    messwerte = []
    try:
        with datei.open("r", encoding="utf-8") as datenstrom:
            for zeile in datenstrom:
                if not zeile.strip():
                    continue
                try:
                    messwert = json.loads(zeile)
                except json.JSONDecodeError:
                    continue
                if not isinstance(messwert, dict):
                    continue
                zeitpunkt = tempco2_parse_utc(messwert.get("empfangen_utc"))
                if zeitpunkt is None or zeitpunkt < seit_utc:
                    continue
                messwerte.append(messwert)
    except OSError:
        return []

    return sorted(messwerte, key=lambda eintrag: eintrag.get("empfangen_utc", ""))


def tempco2_verdichte_historie(messwerte):
    if len(messwerte) <= TEMP_CO2_MAX_GRAPH_MESSWERTE:
        return messwerte, False

    schritt = max(1, (len(messwerte) + TEMP_CO2_MAX_GRAPH_MESSWERTE - 1) // TEMP_CO2_MAX_GRAPH_MESSWERTE)
    letzter_index = len(messwerte) - 1
    verdichtet = [
        messwert
        for index, messwert in enumerate(messwerte)
        if index == 0 or index == letzter_index or index % schritt == 0
    ]
    return verdichtet, True


def tempco2_ist_aktuell(messwert):
    empfangen = tempco2_parse_utc(messwert.get("empfangen_utc"))
    if empfangen is None:
        return False
    alter = (datetime.now(timezone.utc) - empfangen).total_seconds()
    return 0 <= alter <= tempco2_max_alter_sekunden()


@app.route("/api/tempco2/aktuell")
def tempco2_aktueller_messwert():
    with TEMP_CO2_SPERRE:
        messwert = tempco2_lade_messwert()
    if not messwert or not tempco2_ist_aktuell(messwert):
        return {
            "verfuegbar": False,
            "max_alter_sekunden": tempco2_max_alter_sekunden(),
        }
    antwort = dict(messwert)
    antwort["verfuegbar"] = True
    antwort["max_alter_sekunden"] = tempco2_max_alter_sekunden()
    return antwort


@app.route("/api/tempco2/historie")
def tempco2_historie():
    zeitraum = request.args.get("zeitraum", "tag").strip().casefold()
    dauer = TEMP_CO2_HISTORIE_ZEITRÄUME.get(zeitraum)
    if dauer is None:
        abort(400)

    seit_utc = datetime.now(timezone.utc) - dauer
    with TEMP_CO2_SPERRE:
        messwerte = tempco2_lade_historie(seit_utc)
    messwerte_gesamt = len(messwerte)
    messwerte, verdichtet = tempco2_verdichte_historie(messwerte)

    return {
        "zeitraum": zeitraum,
        "messwerte": messwerte,
        "messwerte_gesamt": messwerte_gesamt,
        "verdichtet": verdichtet,
    }


@app.route("/api/tempco2/messwert", methods=["POST"])
def tempco2_messwert_empfangen():
    if not tempco2_upload_token():
        abort(503)
    if not tempco2_token_ist_gültig():
        abort(403)

    try:
        messwert = tempco2_normalisiere_messwert(request.get_json(silent=True))
    except ValueError:
        abort(400)

    with TEMP_CO2_SPERRE:
        tempco2_speichere_messwert(messwert)
        tempco2_speichere_historie(messwert)

    return {
        "ok": True,
        "empfangen_utc": messwert["empfangen_utc"],
    }


@app.route("/api/autobahn")
def autobahn_api():
    daten = road_weather.lade_api_daten(strassenwetter_konfiguration())
    antwort = jsonify(daten)
    antwort.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=840"
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    return antwort


@app.route("/autobahn")
def autobahn():
    daten = road_weather.lade_api_daten(strassenwetter_konfiguration())
    return render_template("autobahn.html", strassenwetter=daten)


@app.route("/robots.txt")
def crawler_regeln():
    inhalt = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /downloads/",
            f"Sitemap: {kanonische_url('/sitemap.xml')}",
            "",
        ]
    )
    return inhalt, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/sitemap.xml")
def sitemap_xml():
    zeilen = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for seite in SEO_SEITEN:
        if not seite.get("indexierbar", True):
            continue
        zeilen.extend(
            [
                "  <url>",
                f"    <loc>{escape(kanonische_url(seite['pfad']))}</loc>",
                f"    <lastmod>{sitemap_lastmod(seite)}</lastmod>",
                "  </url>",
            ]
        )
    zeilen.append("</urlset>")
    return "\n".join(zeilen) + "\n", 200, {"Content-Type": "application/xml; charset=utf-8"}


@app.errorhandler(404)
def seite_nicht_gefunden(_fehler):
    return (
        render_template(
            "fehler.html",
            fehlercode=404,
            fehler_titel="Seite nicht gefunden | DO1FFE",
            fehler_beschreibung="Die angeforderte Seite ist unter dieser Adresse nicht verfügbar.",
            fehler_ueberschrift="Diese Seite funkt nicht mehr auf dieser Adresse.",
            fehler_text=(
                "Der Link ist veraltet, unvollständig oder führt zu einer Seite, "
                "die hier nicht veröffentlicht ist."
            ),
            seo_kanonische_url="",
            seo_robots=ROBOTS_FEHLERSEITE,
            breadcrumb_jsonld="",
        ),
        404,
    )


@app.errorhandler(500)
def interner_serverfehler(_fehler):
    return (
        render_template(
            "fehler.html",
            fehlercode=500,
            fehler_titel="Technischer Fehler | DO1FFE",
            fehler_beschreibung="Die angeforderte Seite konnte vorübergehend nicht ausgeliefert werden.",
            fehler_ueberschrift="Die Technik braucht gerade einen kurzen Neustart im Kopf.",
            fehler_text=(
                "Bitte versuche es später erneut. Es werden keine internen "
                "Fehlerdetails auf der Webseite ausgegeben."
            ),
            seo_kanonische_url="",
            seo_robots=ROBOTS_FEHLERSEITE,
            breadcrumb_jsonld="",
        ),
        500,
    )


@app.route("/")
def startseite():
    return render_template("startseite.html")


@app.route("/ov-l11")
def ov_l11():
    return render_template("ov_l11.html")


@app.route("/ov-l11/ov-abend-2026-08-11")
def ov_abend_2026_08_11():
    return render_template("ov_abend_2026_08_11.html")


@app.route("/tesla-dashboard")
def tesla_dashboard():
    return render_template("tesla_dashboard.html")


@app.route("/tempco2")
def tempco2():
    return render_template("tempco2.html")


@app.route("/dienste")
def dienste():
    dienste_liste = öffentliche_dienste()
    return render_template(
        "github.html",
        dienste=dienste_liste,
        dienst_statistik=dienst_statistik(dienste_liste),
    )


@app.route("/github")
def github():
    return redirect(url_for("dienste"), code=301)


@app.route("/api/meshcore/repeater-firmware")
def meshcore_repeater_firmware_api():
    firmware = lade_meshcore_repeater_firmware()
    antwort = dict(firmware)
    antwort["label"] = "Aktuelle Repeater-Firmware von meshcore.io:"
    return antwort, 200, {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@app.route("/meshcore")
def meshcore():
    repeater_apk, repeater_apk_historie = meshcore_repeater_apk_übersicht()
    return render_template(
        "meshcore.html",
        repeater_apk=repeater_apk,
        repeater_apk_historie=repeater_apk_historie,
        meshcore_ble_updater=meshcore_ble_updater_übersicht(),
        repeater_changelog_verfügbar=repeater_changelog_verfügbar(),
        regionenkarte_punkte=meshcore_regionenkarte_punkte(),
        meshcore_repeater_firmware=lade_meshcore_repeater_firmware(),
    )


@app.route("/Funkbruecke")
def funkbruecke():
    return render_template("funkbruecke.html", **funkbruecke_download_daten())


@app.route("/funkbruecke")
def funkbruecke_klein():
    return redirect("/Funkbruecke", code=301)


@app.route("/downloads/meshcore-repeater-konfigurator/Changelog.txt")
def meshcore_repeater_konfigurator_changelog():
    datei = repeater_changelog_datei()
    if not datei.is_file():
        abort(404)
    return send_file(
        datei,
        as_attachment=False,
        download_name="Changelog.txt",
        mimetype="text/plain",
        max_age=0,
    )


@app.route("/downloads/meshcore-repeater-konfigurator.apk")
def meshcore_repeater_konfigurator_apk():
    datei = finde_neuste_repeater_apk()
    if datei is None:
        abort(404)
    return sende_repeater_apk(datei)


@app.route("/downloads/meshcore-repeater-konfigurator/v<version>.apk")
def meshcore_repeater_konfigurator_apk_version(version):
    datei = finde_repeater_apk_version(version)
    if datei is None:
        abort(404)
    return sende_repeater_apk(datei)


@app.route("/downloads/meshcore-ble-updater/android.apk")
def meshcore_ble_updater_android():
    datei = finde_neuste_meshcore_ble_updater_datei("android")
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("android", datei)


@app.route("/downloads/meshcore-ble-updater/v<version>/android.apk")
def meshcore_ble_updater_android_version(version):
    datei = finde_meshcore_ble_updater_datei_version("android", version)
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("android", datei)


@app.route("/downloads/meshcore-ble-updater/windows.exe")
def meshcore_ble_updater_windows():
    datei = finde_neuste_meshcore_ble_updater_datei("windows")
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("windows", datei)


@app.route("/downloads/meshcore-ble-updater/v<version>/windows.exe")
def meshcore_ble_updater_windows_version(version):
    datei = finde_meshcore_ble_updater_datei_version("windows", version)
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("windows", datei)


@app.route("/downloads/meshcore-ble-updater/ios-unsigned.ipa")
def meshcore_ble_updater_ios():
    datei = finde_neuste_meshcore_ble_updater_datei("ios")
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("ios", datei)


@app.route("/downloads/meshcore-ble-updater/v<version>/ios-unsigned.ipa")
def meshcore_ble_updater_ios_version(version):
    datei = finde_meshcore_ble_updater_datei_version("ios", version)
    if datei is None:
        abort(404)
    return sende_meshcore_ble_updater_datei("ios", datei)


@app.route("/kontakt")
def kontakt():
    return render_template("kontakt.html")


@app.route("/impressum")
def impressum():
    return render_template("impressum.html")


@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")


@app.route("/ueber-mich")
def ueber_mich():
    return render_template("ueber_mich.html")


@app.route("/projekte")
def projekte():
    return redirect(url_for("dienste"), code=301)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8020)

# Copyright © 2026 Erik Schauer, do1ffe@darc.de
