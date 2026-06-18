from collections import Counter
from datetime import datetime
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

from flask import Flask, abort, redirect, render_template, request, send_file

app = Flask(__name__)


KANONISCHE_BASIS_URL = "https://do1ffe.de"
INDEXIERBARE_PFADE = (
    "/",
    "/ov-l11",
    "/tesla-dashboard",
    "/github",
    "/meshcore",
    "/Funkbruecke",
    "/kontakt",
    "/impressum",
    "/datenschutz",
    "/ueber-mich",
    "/projekte",
)
BERLINER_ZEITZONE = ZoneInfo("Europe/Berlin")
MESHCORE_REPEATER_APK_ORDNER = Path("/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator")
MESHCORE_REPEATER_ARCHIV_ORDNER = Path("/home/do1ffe/meshcore-repeater-konfigurator/artifacts")
MESHCORE_BLE_UPDATER_ORDNER = Path("/home/do1ffe/software-downloads/Meshcore-BLE-Updater")
MESHCORE_REGIONEN_ORDNER = Path("/home/do1ffe/meshcore-repeater-konfigurator/regionen-vorschlaege")
MESHCORE_KOMMANDO_BESCHREIBUNGEN_DATEI = Path(__file__).with_name("daten") / "meshcore-kommandos-de.json"
MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER = Path("/home/do1ffe/software-downloads")
MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI = MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER / ".download-zaehler.json"
MESHCORE_REPEATER_APK_MUSTER = "MeshCoreRepeaterKonfigurator-*-release-signed.apk"
MESHCORE_REPEATER_HISTORIE_AB_VERSION = "1.0.22"
MESHCORE_REPEATER_MAX_HISTORIE_VERSIONEN = 2
FUNKBRUECKE_DOWNLOAD_ORDNER = Path("/home/do1ffe/software-downloads/FunkBruecke")
FUNKBRUECKE_DOWNLOAD_BASIS_URL = "https://downloads.do1ffe.de/FunkBruecke"
FUNKBRUECKE_EXE_REGEX = re.compile(
    r"^FunkBruecke-v(?P<version>\d+(?:\.\d+)*)-(?P<datum>\d{8})-win-x64\.exe$"
)
FUNKBRUECKE_DOWNLOAD_ARTEFAKTE = [
    {
        "schlüssel": "windows",
        "titel": "Windows-Programm",
        "dateiname": "FunkBruecke-latest-win-x64.exe",
        "typ": "EXE",
        "beschreibung": "Aktuelle Windows-x64-Version mit gebündelter Laufzeit, eingebettetem FunkBrücke-Icon, leerem Startzustand ohne Beispielstationen, verdichtetem Chat-Hauptfenster mit Zielauswahl, sichtbarem Sendemodus je TX-Paket, strenger OK/Wiederholen-Zuordnung zum Test-TX, Dauer-RX-Duplikatschutz, FT-991A-USB-Audioprüfung, FB2-Live-Ereignissen, nachvollziehbarer Mesh-Modusentscheidung, separatem Monitor für alle RX/TX-Daten, Geräte-, Automatik-, Detail-, Einstellungs- und Über-Fenstern sowie verzögerter CAT-/Audiogerätesuche nach dem sichtbaren Grundstart.",
        "primär": True,
    },
    {
        "schlüssel": "bedienung",
        "titel": "Bedienungsanleitung",
        "dateiname": "FunkBruecke-Bedienungsanleitung-latest.pdf",
        "typ": "PDF",
        "beschreibung": "Kurzer Einstieg mit echten Programmansichten, Chat-Hauptfenster, Zielauswahl ALLE/Gegenstation, TX-Eingabe, sichtbarem Sendemodus je TX-Paket, FB2-Live-Ereignismonitor, Mesh-Modusentscheidung mit Primär-Hop und Ersatz-Hop, separatem Monitor für alle RX/TX-Daten, Geräte-, Automatik-, Detail-, Einstellungs- und Über-Fenster, FB1-Live-RX, FB2-Auto-RX mit Duplikatschutz, Warteschlange, Start prüfen mit Empfang/Trockenlauf/echter CAT-PTT, Zwei-Stationen-Praxisstart, FT-991A-Hardwarepfad inklusive USB-Audioprüfung, gleicher Sicherheitslinie in Vor-TX, Fehlerhilfe, Sendeautomatik und Feldtestprotokoll, automatischem RX nach TX, Auto-OK ohne manuelle PTT, direkter Audio-QSO-Kette von 2-FSK robust bis OFDM schnell, profilabhängiger FB2-Mesh-Automatik bis OFDM schnell, Rückweg-ACK und 6-Hop-Praxisrundlauf.",
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
        "beschreibung": "Technischer Stand zur FB2-Modulation, Paketübertragung, Broadcast-Ziel ALLE ohne automatisches OK/ACK, Praxisstartstufe, echter CAT-PTT, Zwei-Stationen-Praxisstart, FT-991A-Hardwarepfad mit USB-Audioprüfung, gemeinsamer Sicherheitslinie für Vor-TX, Fehlerhilfe, Sendeautomatik und Feldtestprotokoll, Gesprächszustand, RX-Härtung, RX-Sortierung, FB2-Auto-RX mit Audiopufferprüfung und Duplikatschutz, geprüfter Warteschlangen-Sendeautomatik ohne manuelle PTT, automatischem RX nach TX, FB2-Live-Ereignissen, sichtbarem Sendemodus je TX-Paket, direkter Audio-QSO-Kette von 2-FSK robust bis OFDM schnell, Timeout-Wiederholung, strenger Rückmeldeprüfung, automatischer RX-/Kanalvorbereitung beim Einreihen, profilabhängiger FB2-Mesh-Automatik bis OFDM schnell, nachvollziehbarer Primär-/Ersatz-Hop-Moduswahl, adaptiver Moduskorrektur, neuester passender Nachbarspur, Ende-zu-Ende-Zustellbestätigung und 6-Hop-Praxisrundlauf.",
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
    {
        "schlüssel": "mesh",
        "titel": "FB1-/Mesh-Protokoll",
        "dateiname": "FB1-Mesh-Protokoll.md",
        "typ": "Markdown",
        "beschreibung": "Protokollnotizen für Mesh-Erreichbarkeit, Routing und Weiterleitung.",
        "primär": False,
    },
    {
        "schlüssel": "sinn",
        "titel": "Sinn und Zweck",
        "dateiname": "FunkBruecke-Sinn-und-Zweck-latest.pdf",
        "typ": "PDF",
        "beschreibung": "Laienverständliche Erklärung, wozu FunkBrücke im fertigen Zustand dienen soll.",
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
    "set flood.max 64",
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


@app.after_request
def verhindere_dynamischen_cache(antwort):
    dynamische_endpunkte = {
        "github",
        "projekte",
        "meshcore",
        "meshcore_repeater_konfigurator_changelog",
        "meshcore_ble_updater_android",
        "meshcore_ble_updater_android_version",
        "meshcore_ble_updater_windows",
        "meshcore_ble_updater_windows_version",
        "meshcore_ble_updater_ios",
        "meshcore_ble_updater_ios_version",
        "funkbruecke",
    }
    if request.endpoint in dynamische_endpunkte:
        antwort.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        antwort.headers["Pragma"] = "no-cache"
        antwort.headers["Expires"] = "0"
        antwort.headers["Surrogate-Control"] = "no-store"
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


def meshcore_profil_kommandos(scopes, deny_scopes, home_region, default_region):
    kommandos = list(MESHCORE_SETUP_KOMMANDOS)
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


def lade_meshcore_kommando_beschreibungen():
    try:
        daten = json.loads(MESHCORE_KOMMANDO_BESCHREIBUNGEN_DATEI.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return daten if isinstance(daten, dict) else {}


def meshcore_kommando_erklärung(kommando):
    beschreibungen = lade_meshcore_kommando_beschreibungen()
    exakte_kommandos = beschreibungen.get("exakteKommandos")
    if isinstance(exakte_kommandos, dict):
        beschreibung = exakte_kommandos.get(kommando)
        if isinstance(beschreibung, str) and beschreibung:
            return beschreibung
    präfix_kommandos = beschreibungen.get("präfixKommandos")
    if isinstance(präfix_kommandos, list):
        for eintrag in präfix_kommandos:
            if not isinstance(eintrag, dict):
                continue
            präfix = eintrag.get("präfix")
            beschreibung = eintrag.get("beschreibung")
            if isinstance(präfix, str) and isinstance(beschreibung, str) and kommando.startswith(präfix):
                return beschreibung.format(wert=kommando.removeprefix(präfix))
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


def meshcore_regionenkarte_punkte():
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
        if not region_id or not stadt_name or not land or not scopes:
            continue
        kommandos = meshcore_profil_kommandos(scopes, deny_scopes, home_region, default_region)
        punkte.append({
            "id": region_id,
            "stadt": stadt or stadt_name,
            "stadtName": stadt_name,
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


@app.route("/robots.txt")
def crawler_regeln():
    inhalt = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
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
    for pfad in INDEXIERBARE_PFADE:
        zeilen.extend(
            [
                "  <url>",
                f"    <loc>{escape(kanonische_url(pfad))}</loc>",
                "  </url>",
            ]
        )
    zeilen.append("</urlset>")
    return "\n".join(zeilen) + "\n", 200, {"Content-Type": "application/xml; charset=utf-8"}


@app.route("/")
def startseite():
    return render_template("startseite.html")


@app.route("/ov-l11")
def ov_l11():
    return render_template("ov_l11.html")


@app.route("/tesla-dashboard")
def tesla_dashboard():
    return render_template("tesla_dashboard.html")


@app.route("/github")
def github():
    return render_template("github.html", **lade_github_daten())


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
    return render_template("github.html", **lade_github_daten())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8020)
