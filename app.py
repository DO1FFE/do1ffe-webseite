from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from threading import Lock
import time

from flask import Flask, abort, render_template, request, send_file

app = Flask(__name__)


MESHCORE_REPEATER_APK_ORDNER = Path("/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator")
MESHCORE_REPEATER_ARCHIV_ORDNER = Path("/home/do1ffe/meshcore-repeater-konfigurator/artifacts")
MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER = Path("/home/do1ffe/software-downloads")
MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI = MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER / ".download-zaehler.json"
MESHCORE_REPEATER_APK_MUSTER = "MeshCoreRepeaterKonfigurator-*-release-signed.apk"
MESHCORE_REPEATER_HISTORIE_AB_VERSION = "1.0.22"
MESHCORE_REPEATER_APK_REGEX = re.compile(
    r"^MeshCoreRepeaterKonfigurator-(?P<version>\d+(?:\.\d+)*)-release-signed\.apk$"
)
DOWNLOAD_ZÄHLER_SPERRE = Lock()
DOWNLOAD_ZÄHLER_QUELLEN = {"button", "qr", "historie"}
DOWNLOAD_ZÄHLER_ENTPRELL_FENSTER_SEKUNDEN = 15 * 60


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


def download_entprell_schlüssel(version):
    return ":".join([version, download_quelle(), download_client_fingerprint()])


def download_ist_neu_genug(version, jetzt=None):
    jetzt = time.time() if jetzt is None else jetzt
    schlüssel = download_entprell_schlüssel(version)
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
        if not download_ist_neu_genug(version):
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
        "geändert": datetime.fromtimestamp(status.st_mtime).strftime("%d.%m.%Y, %H:%M"),
        "größe": formatiere_dateigröße(status.st_size),
        "verfügbar": True,
        "version": version,
    }


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


def download_soll_gezählt_werden():
    return download_quelle() in DOWNLOAD_ZÄHLER_QUELLEN


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
    return render_template("github.html", repos=REPOSITORIES)


@app.route("/meshcore")
def meshcore():
    repeater_apk, repeater_apk_historie = meshcore_repeater_apk_übersicht()
    return render_template(
        "meshcore.html",
        repeater_apk=repeater_apk,
        repeater_apk_historie=repeater_apk_historie,
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


@app.route("/kontakt")
def kontakt():
    return render_template("kontakt.html")


@app.route("/ueber-mich")
def über_mich():
    return render_template("ov_l11.html")


@app.route("/projekte")
def projekte():
    return render_template("github.html", repos=REPOSITORIES)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8020)
