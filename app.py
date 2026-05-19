from datetime import datetime
from pathlib import Path
import re

from flask import Flask, abort, render_template, send_file

app = Flask(__name__)


MESHCORE_REPEATER_APK_ORDNER = Path("/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator")
MESHCORE_REPEATER_APK_MUSTER = "MeshCoreRepeaterKonfigurator-*-release-signed.apk"
MESHCORE_REPEATER_APK_REGEX = re.compile(
    r"^MeshCoreRepeaterKonfigurator-(?P<version>\d+(?:\.\d+)*)-release-signed\.apk$"
)


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


def apk_sortierschlüssel(datei):
    version = apk_version(datei)
    teile = [int(teil) for teil in version.split(".") if teil.isdigit()]
    aufgefüllt = tuple((teile + [0, 0, 0, 0])[:4])
    try:
        geändert = datei.stat().st_mtime
    except OSError:
        geändert = 0
    return aufgefüllt, geändert


def finde_neuste_repeater_apk():
    if not MESHCORE_REPEATER_APK_ORDNER.exists():
        return None
    dateien = [
        datei
        for datei in MESHCORE_REPEATER_APK_ORDNER.glob(MESHCORE_REPEATER_APK_MUSTER)
        if datei.is_file()
    ]
    if not dateien:
        return None
    return max(dateien, key=apk_sortierschlüssel)


def formatiere_dateigröße(größe):
    if größe >= 1024 * 1024:
        return f"{größe / (1024 * 1024):.1f} MiB".replace(".", ",")
    return f"{größe / 1024:.0f} KiB"


def meshcore_repeater_apk_info():
    datei = finde_neuste_repeater_apk()
    if datei is None:
        return None
    try:
        status = datei.stat()
    except OSError:
        return None
    return {
        "dateiname": datei.name,
        "größe": formatiere_dateigröße(status.st_size),
        "geändert": datetime.fromtimestamp(status.st_mtime).strftime("%d.%m.%Y, %H:%M"),
        "version": apk_version(datei),
    }


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
    return render_template("meshcore.html", repeater_apk=meshcore_repeater_apk_info())


@app.route("/downloads/meshcore-repeater-konfigurator.apk")
def meshcore_repeater_konfigurator_apk():
    datei = finde_neuste_repeater_apk()
    if datei is None:
        abort(404)
    return send_file(
        datei,
        as_attachment=True,
        download_name=datei.name,
        mimetype="application/vnd.android.package-archive",
        max_age=0,
    )


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
