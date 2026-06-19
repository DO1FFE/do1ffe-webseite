import json
import os
from datetime import datetime, timezone
from xml.etree import ElementTree

import pytest

import app as webseite

app = webseite.app


@pytest.fixture(autouse=True)
def verwende_github_testdaten(monkeypatch):
    daten = {
        "repos": [
            {
                "name": "tesla-dashboard",
                "beschreibung": "Ein Dashboard für den Tesla.",
                "url": "https://github.com/DO1FFE/tesla-dashboard",
                "meta": "Python · aktualisiert 20.05.2026 · MIT",
                "sprache": "Python",
                "sterne": 7,
                "forks": 1,
                "offene_issues": 2,
                "aktualisiert": "20.05.2026",
                "aktualisiert_monat": "Mai 2026",
                "archiviert": False,
                "fork": False,
                "topics": ["dashboard"],
            },
            {
                "name": "CoreScope",
                "beschreibung": "MeshCore-Analyzer.",
                "url": "https://github.com/DO1FFE/CoreScope",
                "meta": "Fork · JavaScript · aktualisiert 18.05.2026",
                "sprache": "JavaScript",
                "sterne": 3,
                "forks": 2,
                "offene_issues": 0,
                "aktualisiert": "18.05.2026",
                "aktualisiert_monat": "Mai 2026",
                "archiviert": False,
                "fork": True,
                "topics": ["meshcore"],
            },
            {
                "name": "meshcore-network-monitor",
                "beschreibung": "Monitoring für MeshCore-Netze.",
                "url": "https://github.com/DO1FFE/meshcore-network-monitor",
                "meta": "Python · aktualisiert 16.05.2026",
                "sprache": "Python",
                "sterne": 4,
                "forks": 0,
                "offene_issues": 1,
                "aktualisiert": "16.05.2026",
                "aktualisiert_monat": "Mai 2026",
                "archiviert": False,
                "fork": False,
                "topics": ["meshcore"],
            },
        ],
        "repo_statistik": {
            "anzahl_öffentlich": 42,
            "anzahl_privat": 11,
            "private_repos_verfügbar": True,
            "angezeigte_repos": 3,
            "häufige_sprachen": "Python, JavaScript",
            "themen": "meshcore, dashboard",
            "aktivität": "zuletzt 20.05.2026 bei tesla-dashboard",
            "letzte_aktualisierung": "Mai 2026",
            "profil_url": "https://github.com/DO1FFE",
            "login": "DO1FFE",
            "quelle": "GitHub API",
            "live": True,
            "fehler": "",
            "abgerufen_um": "27.05.2026, 12:00",
        },
    }
    monkeypatch.setattr(webseite, "lade_github_daten", lambda: daten)


def richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch):
    download_basis = tmp_path / "software-downloads"
    download_ordner = download_basis / "MeshCoreRepeaterKonfigurator"
    archiv_ordner = tmp_path / "artifacts"
    download_ordner.mkdir(parents=True)
    archiv_ordner.mkdir()
    zähler_datei = download_basis / ".download-zaehler.json"
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER", download_basis)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_APK_ORDNER", download_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_ARCHIV_ORDNER", archiv_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI", zähler_datei)
    return download_ordner, archiv_ordner, zähler_datei


def richte_meshcore_ble_updater_testdaten_ein(tmp_path, monkeypatch):
    download_basis = tmp_path / "software-downloads"
    updater_ordner = download_basis / "Meshcore-BLE-Updater"
    repeater_ordner = download_basis / "MeshCoreRepeaterKonfigurator"
    archiv_ordner = tmp_path / "artifacts"
    updater_ordner.mkdir(parents=True)
    repeater_ordner.mkdir()
    archiv_ordner.mkdir()
    zähler_datei = download_basis / ".download-zaehler.json"
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_DOWNLOAD_BASIS_ORDNER", download_basis)
    monkeypatch.setattr(webseite, "MESHCORE_BLE_UPDATER_ORDNER", updater_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_APK_ORDNER", repeater_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_ARCHIV_ORDNER", archiv_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI", zähler_datei)
    return updater_ordner, zähler_datei


def richte_regionenkarte_testdaten_ein(tmp_path, monkeypatch):
    regionen_ordner = tmp_path / "regionen-vorschlaege"
    regionen_ordner.mkdir()
    monkeypatch.setattr(webseite, "MESHCORE_REGIONEN_ORDNER", regionen_ordner)
    return regionen_ordner


def schreibe_download_zähler(zähler_datei, einträge):
    daten = {"schema": 1, "dateien": {}}
    for datei, downloads in einträge.items():
        daten["dateien"][webseite.download_relativer_pfad(datei)] = {
            "downloads": downloads,
            "versionskennung": webseite.download_versionskennung(datei),
        }
    zähler_datei.write_text(json.dumps(daten), encoding="utf-8")


def lies_downloads(zähler_datei, datei):
    daten = json.loads(zähler_datei.read_text(encoding="utf-8"))
    eintrag = daten["dateien"][webseite.download_relativer_pfad(datei)]
    return eintrag["downloads"]


def test_alle_hauptseiten_erreichbar():
    klient = app.test_client()
    for route in [
        "/",
        "/ov-l11",
        "/tesla-dashboard",
        "/github",
        "/meshcore",
        "/kontakt",
        "/impressum",
        "/datenschutz",
        "/ueber-mich",
        "/projekte",
        "/Funkbruecke",
    ]:
        antwort = klient.get(route)
        assert antwort.status_code == 200


def test_startseite_verlinkt_unterseiten():
    klient = app.test_client()
    antwort = klient.get("/")
    html = antwort.get_data(as_text=True)

    assert "/ueber-mich" in html
    assert "/ov-l11" in html
    assert "/tesla-dashboard" in html
    assert "/github" in html
    assert "/meshcore" in html
    assert "Erik Schauer, DO1FFE aus Essen" in html
    assert "33 öffentliche Repositories" not in html


def test_ueber_mich_erzählt_persönlich_ohne_private_repos():
    klient = app.test_client()
    antwort = klient.get("/ueber-mich")
    html = antwort.get_data(as_text=True)
    text = " ".join(html.split())

    assert antwort.status_code == 200
    assert "Erik Schauer, DO1FFE aus Essen" in text
    assert "Rufzeichen" in text
    assert "JO31MK" in text
    assert "Amateurfunk" in text
    assert "Softwareentwicklung" in text
    assert "Tesla Model S 90D von 2016" in text
    assert "rollender Technikträger" in text
    assert "free Supercharging" in text
    assert "ohne dass mir der Strom separat berechnet wird" in text
    assert "rund 525 PS kombinierte Motorleistung" in text
    assert "Allradantrieb durch zwei Elektromotoren" in text
    assert "0 auf 100 km/h in etwa 4,4 Sekunden" in text
    assert "bis zu 250 km/h Höchstgeschwindigkeit" in text
    assert "große 90-kWh-Akkuklasse" in text
    assert "Yaesu FTM-500D" in text
    assert "Glasklebeantenne für 2 m und 70 cm" in text
    assert "mobile Einsätze schnell verfügbar" in text
    assert "Relais und Direktverbindungen" in text
    assert "festes Mobilgerät statt losem Handfunkgerät" in text
    assert "ohne auffällige Außenmontage" in text
    assert "V2L-Adapter" in text
    assert "220/230 V" in text
    assert "mobilen Energiequelle" in text
    assert "bis zu 4 kW Ausgangsleistung laut Adapterangabe" in text
    assert "Kühlbox, Licht, Ladegeräte, Funkzubehör und kleine Werkzeuge" in text
    assert "tragbar mit Griff für Camping" in text
    assert "Vehicle-to-Load" in text
    assert "V2L ganz einfach erklärt" in text
    assert "Auto wird zur" in text
    assert "Steckdose" in text
    assert "Haushaltsstecker" in text
    assert "Ladesäule" in text
    assert "Das Auto gibt Strom wieder ab" in text
    assert "Kaffee-Vollautomat" in text
    assert "bis zu 4 kW Ausgangsleistung" in text
    assert "Kühlschrank" in text
    assert "Beleuchtung" in text
    assert "20 Prüfungen" in text
    assert "einschalten, nutzen, sauber ausschalten" in text
    assert "tragbares Gehäuse mit Griff" in text
    assert "Backup-USB für Softwareupdates" in text
    assert "Tesla-Updates die Entladefunktion beeinflussen" in text
    assert "zwischen 20 % und 95 %" in text
    assert "Tesla Model 3, Model Y, Model S und Model X" in text
    assert "CCS-Funktion" in text
    assert "drei 18650-Akkuzellen" in text
    assert "Gleichstrom aus dem Fahrzeug" in text
    assert "Wechselrichter" in text
    assert "Haushalts-Wechselstrom" in text
    assert "DC zu AC" in text
    assert "keine Ersatz-Stromversorgung für ein ganzes Haus" in text
    assert "wie viel" in text
    assert "Leistung der Adapter liefern darf" in text
    assert "Auto da, Adapter dran" in text
    assert "Gerät läuft" in text
    assert "Kompressor-Kühlbox" in text
    assert "Siemens EQ-700 classic" in text
    assert "Vollausstattung" in text
    assert "kalte Getränke auch bei warmem Wetter" in text
    assert "Kaffee-Vollautomat statt Thermoskanne" in text
    assert "Stromversorgung über den V2L-Adapter möglich" in text
    assert "Fieldday-ähnliche Einsätze" in text
    assert "https://github.com/DO1FFE" in text
    assert "Private Repos" not in text


def test_footer_verlinkt_impressum_und_datenschutz():
    klient = app.test_client()
    antwort = klient.get("/")
    html = antwort.get_data(as_text=True)

    assert "/impressum" in html
    assert "/datenschutz" in html
    assert "Datenschutzerklärung" in html


def test_funkbruecke_seite_zeigt_aktuellen_prototypstand():
    klient = app.test_client()
    antwort = klient.get("/Funkbruecke")
    html = antwort.get_data(as_text=True)
    html = " ".join(html.split())

    assert antwort.status_code == 200

    erwartete_texte = [
        "Derzeit noch ein Prototyp",
        "v0.9.",
        "Text eingeben, Zielrufzeichen wählen",
        "Der Nutzer schreibt eine Nachricht",
        "Nachrichtenprogramm für Funkbetrieb",
        "gemischte RX/TX-Verlauf wie in einem Chat",
        "Das eigentliche Senden und Empfangen soll automatisch laufen.",
        "separates Monitorfenster",
        "Einstellungen",
        "Über-Informationen",
        "Echte CAT-PTT bleibt bewusst freigabepflichtig",
        "Trockenlauf und lokale Audiotests senden nicht unbeaufsichtigt auf HF",
        "frei wählbarer Audioein- und Audioausgang",
        "Audioquellen werden nicht auf bestimmte Gerätenamen begrenzt",
        "Jeder Windows-Eingang und jeder Windows-Ausgang",
        "FB2L-Webkarte",
        "FB2L-Livekarte",
        "FB2L-Heartbeat",
        "App-Lage",
        "Audio-RX, FB2-Dauer-RX, TX, PTT",
        "FB2L-Server nimmt nur kompakte Heartbeats",
        "https://fb2l.do1ffe.de",
        "60 Minuten dunkelgrau",
        "Verbindungen per TTL",
        "Quelle, Rest-TTL",
        "gültig-bis",
        "grauer-Nachlauf-bis",
        "reine Nachbarprofile",
        "Modusleiter",
        "2-FSK",
        "4-FSK",
        "8-FSK",
        "16/32/64-MFSK",
        "OFDM",
        "sichtbarem TX-Modus",
        "geplanten Sendemodus",
        "Baken und Modusproben bleiben sparsam und robust",
        "Jedes TX-Paket zeigt den geplanten Modus",
        "Nach einer Aussendung geht die Station automatisch wieder auf Empfang",
        "Baken laufen sparsam in 2-FSK robust",
        "Nutzpakete wählen danach den schnellsten passenden Modus",
        "produktive Sendemotor",
        "Aushandlung wird dabei mit dem folgenden Nutzpaket",
        "adaptive Moduswahl",
        "Rückweg-ACK",
        "A-D-Relaisfall über",
        "Hop-Warteschlangen",
        "Routen bis sechs Hops",
        "Mesh-Routen sind auf sechs Hops begrenzt",
        "Nur die Station, die als nächster Hop genannt ist",
        "Mesh-Karte",
        "Stationsprofile",
        "Locator",
        "funkbruecke-logo.png",
        "funkbruecke-mesh-karte.png",
        "FB-Monogramm",
        "Anleitungen, Frequenzprofile und technische Dokumente.",
    ]

    for text in erwartete_texte:
        assert text in html

    assert "Changelog" not in html
    assert "Changelog ansehen" not in html
    assert "Seit v0.9." not in html


def test_layout_setzt_seo_metadaten():
    klient = app.test_client()
    antwort = klient.get("/ov-l11")
    html = antwort.get_data(as_text=True)

    assert (
        '<meta name="robots" '
        'content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">'
    ) in html
    assert '<link rel="canonical" href="https://do1ffe.de/ov-l11">' in html
    assert '<meta property="og:site_name" content="DO1FFE">' in html
    assert '<meta name="twitter:card" content="summary">' in html


def test_robots_txt_erlaubt_vollständige_indexierung():
    klient = app.test_client()
    antwort = klient.get("/robots.txt")
    text = antwort.get_data(as_text=True)

    assert antwort.status_code == 200
    assert antwort.content_type == "text/plain; charset=utf-8"
    assert "User-agent: *" in text
    assert "Allow: /" in text
    assert "Disallow" not in text
    assert "Sitemap: https://do1ffe.de/sitemap.xml" in text


def test_sitemap_listet_indexierbare_hauptseiten():
    klient = app.test_client()
    antwort = klient.get("/sitemap.xml")

    assert antwort.status_code == 200
    assert antwort.content_type == "application/xml; charset=utf-8"

    wurzel = ElementTree.fromstring(antwort.get_data(as_text=True))
    namensraum = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = [element.text for element in wurzel.findall(f"{namensraum}url/{namensraum}loc")]

    assert urls == [
        "https://do1ffe.de/",
        "https://do1ffe.de/ov-l11",
        "https://do1ffe.de/tesla-dashboard",
        "https://do1ffe.de/github",
        "https://do1ffe.de/meshcore",
        "https://do1ffe.de/Funkbruecke",
        "https://do1ffe.de/kontakt",
        "https://do1ffe.de/impressum",
        "https://do1ffe.de/datenschutz",
        "https://do1ffe.de/ueber-mich",
        "https://do1ffe.de/projekte",
    ]


def test_ov_l11_zeigt_sommerpause_und_anmeldung():
    klient = app.test_client()
    antwort = klient.get("/ov-l11")
    html = antwort.get_data(as_text=True)

    assert "Sommerpause" in html
    assert "11.08.2026" in html
    assert "Dienstag, 11.08.2026 um 19 Uhr" in html
    assert "https://treff.lima11.de" in html
    assert "application/ld+json" in html
    assert "2026-08-11T19:00:00+02:00" in html


def test_impressum_enthält_anbieterangaben():
    klient = app.test_client()
    antwort = klient.get("/impressum")
    html = antwort.get_data(as_text=True)

    assert "Angaben gemäß § 5 DDG" in html
    assert "Erik Schauer" in html
    assert "Franziskanerhöhe 9" in html
    assert "45139 Essen" in html
    assert "do1ffe@darc.de" in html


def test_datenschutz_enthält_webseite_downloads_und_google_play_apps():
    klient = app.test_client()
    antwort = klient.get("/datenschutz")
    html = antwort.get_data(as_text=True)

    assert "Datenschutzerklärung" in html
    assert "Google Play" in html
    assert "MeshCore Repeater-Konfigurator" in html
    assert "Downloadzähler" in html
    assert "Bluetooth Low Energy" in html
    assert "Art. 6 Abs. 1 lit. f DSGVO" in html


def test_githubseite_enthält_repo_auswahl():
    klient = app.test_client()
    antwort = klient.get("/github")
    html = antwort.get_data(as_text=True)

    assert "tesla-dashboard" in html
    assert "CoreScope" in html
    assert "meshcore-network-monitor" in html
    assert "42 öffentliche Repositories" in html
    assert "Private Repos" in html
    assert "Python, JavaScript" in html
    assert "zuletzt 20.05.2026 bei tesla-dashboard" in html
    assert "Stars" in html
    assert "11 gezählt, nicht verlinkt" in html
    assert "https://github.com/DO1FFE" in html


def test_github_private_repo_anzahl_nutzt_nur_passenden_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_github_json(pfad, parameter=None):
        assert pfad == "/user"
        return {
            "login": "DO1FFE",
            "owned_private_repos": 12,
            "total_private_repos": 14,
        }

    monkeypatch.setattr(webseite, "hole_github_json", fake_github_json)

    assert webseite.github_private_repo_anzahl() == 12


def test_github_private_repo_anzahl_zählt_private_repos_wenn_profilwert_fehlt(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_github_json(pfad, parameter=None):
        if pfad == "/user":
            return {
                "login": "DO1FFE",
            }
        assert pfad == "/user/repos"
        assert parameter["visibility"] == "private"
        assert parameter["affiliation"] == "owner"
        return [
            {"name": "privat-1", "private": True},
            {"name": "privat-2", "private": True},
            {"name": "sichtbar", "private": False},
        ]

    monkeypatch.setattr(webseite, "hole_github_json", fake_github_json)

    assert webseite.github_private_repo_anzahl() == 2


def test_github_private_repo_anzahl_ignoriert_fremden_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_github_json(pfad, parameter=None):
        assert pfad == "/user"
        return {
            "login": "anderer-benutzer",
            "owned_private_repos": 99,
        }

    monkeypatch.setattr(webseite, "hole_github_json", fake_github_json)

    assert webseite.github_private_repo_anzahl() is None


def test_github_live_daten_verlinken_keine_privaten_repos(monkeypatch):
    def fake_github_json(pfad, parameter=None):
        if pfad == "/users/DO1FFE":
            return {
                "login": "DO1FFE",
                "html_url": "https://github.com/DO1FFE",
                "public_repos": 1,
            }
        if pfad == "/users/DO1FFE/repos":
            return [
                {
                    "name": "sichtbar",
                    "description": "Öffentliches Repo.",
                    "html_url": "https://github.com/DO1FFE/sichtbar",
                    "updated_at": "2026-06-14T12:00:00Z",
                    "language": "Python",
                    "stargazers_count": 1,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "archived": False,
                    "fork": False,
                    "private": False,
                    "topics": ["funk"],
                },
                {
                    "name": "privat",
                    "description": "Privates Repo.",
                    "html_url": "https://github.com/DO1FFE/privat",
                    "updated_at": "2026-06-14T13:00:00Z",
                    "language": "Python",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "archived": False,
                    "fork": False,
                    "private": True,
                    "topics": ["intern"],
                },
            ]
        raise AssertionError(pfad)

    monkeypatch.setattr(webseite, "hole_github_json", fake_github_json)
    monkeypatch.setattr(webseite, "github_private_repo_anzahl", lambda: 1)

    daten = webseite.lade_github_daten_live()

    assert [repo["name"] for repo in daten["repos"]] == ["sichtbar"]
    assert daten["repos"][0]["url"] == "https://github.com/DO1FFE/sichtbar"
    assert daten["repo_statistik"]["anzahl_privat"] == 1


def test_meshcoreseite_bewirbt_lokale_einstiege():
    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "https://meshcore-essen.de/" in html
    assert "https://corescope.lima11.de/#/home" in html
    assert "MeshCore-Essen" in html
    assert "CoreScope Essen" in html


def test_meshcoreseite_verlinkt_repeater_konfigurator_apk():
    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert 'class="download-panel reveal" id="app"' in html
    assert "data-download-count" in html
    assert "data-download-version" in html
    assert 'href="#app"' in html
    assert "/downloads/meshcore-repeater-konfigurator/v" in html
    assert "quelle=button" in html
    assert "Gedacht für Android-Handys" in html
    assert "meshcore-repeater-konfigurator-apk-qr.png" in html
    assert "MeshCore Repeater-Konfigurator direkt herunterladen" in html


def test_meshcoreseite_bietet_meshcore_ble_updater_downloads_an(tmp_path, monkeypatch):
    updater_ordner, zähler_datei = richte_meshcore_ble_updater_testdaten_ein(tmp_path, monkeypatch)
    (updater_ordner / "Meshcore-BLE-Updater-v1.4.0-release.apk").write_bytes(b"android")
    (updater_ordner / "Meshcore-BLE-Updater-Win-v1.4.0.exe").write_bytes(b"windows")
    (updater_ordner / "Meshcore-BLE-Updater-iOS-v1.4.0-unsigned.ipa").write_bytes(b"ios")

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert 'id="ble-updater"' in html
    assert 'href="#ble-updater"' in html
    assert "Meshcore BLE Updater herunterladen" in html
    assert "V1.4.0" in html
    assert "/downloads/meshcore-ble-updater/v1.4.0/android.apk?quelle=button" in html
    assert "/downloads/meshcore-ble-updater/v1.4.0/windows.exe?quelle=button" in html
    assert "/downloads/meshcore-ble-updater/v1.4.0/ios-unsigned.ipa?quelle=button" in html
    assert "Die iOS-IPA ist aktuell unsigned" in html
    assert "https://github.com/DO1FFE/Meshcore-BLE-Updater" in html


def test_meshcoreseite_zeigt_oeffentliche_regionenkarte_ohne_gps_marker(tmp_path, monkeypatch):
    regionen_ordner = richte_regionenkarte_testdaten_ein(tmp_path, monkeypatch)
    (regionen_ordner / "region-deutschland-nordrhein-westfalen-bochum.json").write_text(
        json.dumps({
            "schlüssel": "deutschland-nordrhein-westfalen-bochum",
            "stadt": "Bochum",
            "stadtName": "Bochum",
            "land": "Deutschland",
            "bundesland": "Nordrhein-Westfalen",
            "scopes": ["de", "de-nw", "ruhrgebiet"],
            "denyScopes": ["*"],
            "latitude": 51.4818,
            "longitude": 7.2162,
        }),
        encoding="utf-8",
    )

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "leaflet.css" in html
    assert "leaflet.js" in html
    assert 'id="appkarte"' in html
    assert 'id="meshcore-regionenkarte"' in html
    assert "regionenkarteDaten" in html
    assert "Promise.all" in html
    assert "fitBounds(grenzen.pad(0.3)" in html
    assert "Bochum" in html
    assert "ruhrgebiet" in html
    assert "Disallow" in html
    assert "region put de" in html
    assert "region allowf de-nw" in html
    assert "region denyf *" in html
    assert "region home de-nw" in html
    assert "region default de" in html
    assert "region save" in html
    assert "set repeat on" in html
    assert "Kommando" in html
    assert "Erklärung" in html
    assert "Aktiviert die Repeat-Funktion" in html
    assert "Bei „*“ verwirft MeshCore Pakete ohne Region-Transport-Code." in html
    assert "Speichert die seit dem Neustart geänderte Regionskonfiguration dauerhaft." in html
    assert "region list allowed" not in html
    assert "<code>board</code>" not in html
    assert "L.circleMarker" not in html
    assert "51.4818" not in html
    assert "7.2162" not in html


def test_meshcoreseite_nutzt_regionen_json_vor_standardprofil(tmp_path, monkeypatch):
    regionen_ordner = richte_regionenkarte_testdaten_ein(tmp_path, monkeypatch)
    (regionen_ordner / "region-essen-ruhrgebiet.json").write_text(
        json.dumps({
            "schlüssel": "essen-ruhrgebiet",
            "stadt": "Essen",
            "stadtName": "Essen",
            "land": "Deutschland",
            "bundesland": "Nordrhein-Westfalen",
            "scopes": ["europe", "eu", "de", "de-nw"],
            "denyScopes": ["*"],
            "homeRegionen": ["de-nw"],
            "defaultRegionen": ["de"],
            "latitude": 51.4556,
            "longitude": 7.0116,
        }),
        encoding="utf-8",
    )

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "region denyf *" in html
    assert "region allowf ruhrgebiet" not in html


def test_meshcoreseite_verlinkt_changelog_und_deaktiviert_cache(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.30-release-signed.apk").write_bytes(b"neu")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.29-release-signed.apk").write_bytes(b"alt")
    (download_ordner / "Changelog.txt").write_text("V1.0.30\n- Änderung\n", encoding="utf-8")

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "Changelog" in html
    assert "/downloads/meshcore-repeater-konfigurator/Changelog.txt" in html
    assert "Änderung" not in html
    assert antwort.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert antwort.headers["Pragma"] == "no-cache"
    assert antwort.headers["Expires"] == "0"
    assert antwort.headers["Surrogate-Control"] == "no-store"


def test_repeater_konfigurator_changelog_liefert_textdatei(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "Changelog.txt").write_text("V1.0.30\n- Änderung\n", encoding="utf-8")

    klient = app.test_client()
    antwort = klient.get("/downloads/meshcore-repeater-konfigurator/Changelog.txt")

    assert antwort.status_code == 200
    assert antwort.get_data(as_text=True) == "V1.0.30\n- Änderung\n"
    assert antwort.content_type.startswith("text/plain")
    assert antwort.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert antwort.headers["Pragma"] == "no-cache"
    assert antwort.headers["Expires"] == "0"
    assert antwort.headers["Surrogate-Control"] == "no-store"


def test_meshcoreseite_zeigt_apk_stand_in_berliner_zeit(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    apk = download_ordner / "MeshCoreRepeaterKonfigurator-1.0.29-release-signed.apk"
    apk.write_bytes(b"neu")
    zeitstempel = datetime(2026, 5, 26, 8, 44, tzinfo=timezone.utc).timestamp()
    os.utime(apk, (zeitstempel, zeitstempel))

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "26.05.2026, 10:44" in html
    assert "26.05.2026, 08:44" not in html


def test_meshcoreseite_blendet_historie_vor_1_0_22_aus(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.20-release-signed.apk").write_bytes(b"alt")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk").write_bytes(b"mittel")
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")
    schreibe_download_zähler(zähler_datei, {
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.20-release-signed.apk": 3,
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk": 10,
        download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk": 4,
    })

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "Aktuelle Version" in html
    assert "V1.0.22" in html
    assert "Vergangene Versionen" not in html
    assert "V1.0.21" not in html
    assert "10 Downloads" not in html
    assert "V1.0.20" not in html
    assert "3 Downloads" not in html


def test_meshcoreseite_zeigt_historie_ab_1_0_22(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk").write_bytes(b"alt")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"mittel")
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk").write_bytes(b"neu")
    schreibe_download_zähler(zähler_datei, {
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk": 10,
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk": 7,
        download_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk": 2,
    })

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "V1.0.23" in html
    assert "Vergangene Versionen" in html
    assert "V1.0.22" in html
    assert "7 Downloads" in html
    assert "V1.0.21" not in html
    assert "10 Downloads" not in html


def test_meshcoreseite_zeigt_maximal_zwei_historische_versionen(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"alt")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk").write_bytes(b"mittel")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.24-release-signed.apk").write_bytes(b"neuer")
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.25-release-signed.apk").write_bytes(b"neu")
    schreibe_download_zähler(zähler_datei, {
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk": 5,
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk": 6,
        archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.24-release-signed.apk": 7,
        download_ordner / "MeshCoreRepeaterKonfigurator-1.0.25-release-signed.apk": 8,
    })

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "V1.0.25" in html
    assert "V1.0.24" in html
    assert "V1.0.23" in html
    assert "V1.0.22" not in html
    assert "5 Downloads" not in html


def test_meshcoreseite_zeigt_historischen_zähler_aus_downloadportal(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    alte_download_apk = download_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk"
    alte_download_apk.write_bytes(b"alt")
    schreibe_download_zähler(zähler_datei, {alte_download_apk: 4})
    alte_download_apk.unlink()
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.24-release-signed.apk").write_bytes(b"neu")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.23-release-signed.apk").write_bytes(b"alt")

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "V1.0.24" in html
    assert "V1.0.23" in html
    assert "4 Downloads" in html


def test_repeater_konfigurator_download_liefert_neuste_apk_ohne_quelle_und_zählt_nicht(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    alte_apk = archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.9-release-signed.apk"
    neue_apk = download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk"
    alte_apk.write_bytes(b"alt")
    neue_apk.write_bytes(b"neu")

    klient = app.test_client()
    antwort = klient.get("/downloads/meshcore-repeater-konfigurator.apk")

    assert antwort.status_code == 200
    assert antwort.data == b"neu"
    assert "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk" in antwort.headers["Content-Disposition"]
    assert not zähler_datei.exists()


def test_repeater_konfigurator_download_zählt_mit_erlaubter_quelle(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    neue_apk = download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk"
    neue_apk.write_bytes(b"neu")

    klient = app.test_client()
    antwort = klient.get("/downloads/meshcore-repeater-konfigurator.apk?quelle=button")

    assert antwort.status_code == 200
    assert antwort.data == b"neu"
    assert lies_downloads(zähler_datei, neue_apk) == 1


def test_repeater_konfigurator_download_entprellt_mehrfach_gets(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    neue_apk = download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk"
    neue_apk.write_bytes(b"neu")

    klient = app.test_client()
    erste_antwort = klient.get("/downloads/meshcore-repeater-konfigurator.apk?quelle=button")
    zweite_antwort = klient.get("/downloads/meshcore-repeater-konfigurator.apk?quelle=button")

    assert erste_antwort.status_code == 200
    assert zweite_antwort.status_code == 200
    assert lies_downloads(zähler_datei, neue_apk) == 1


def test_repeater_konfigurator_download_zählt_versioniert(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")
    alte_apk = archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk"
    alte_apk.write_bytes(b"alt")
    schreibe_download_zähler(zähler_datei, {alte_apk: 9})

    klient = app.test_client()
    antwort = klient.get("/downloads/meshcore-repeater-konfigurator/v1.0.21.apk?quelle=historie")

    assert antwort.status_code == 200
    assert antwort.data == b"alt"
    assert lies_downloads(zähler_datei, alte_apk) == 10


def test_repeater_konfigurator_head_zählt_nicht(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")

    klient = app.test_client()
    antwort = klient.head("/downloads/meshcore-repeater-konfigurator.apk?quelle=button")

    assert antwort.status_code == 200
    assert not zähler_datei.exists()


def test_meshcore_ble_updater_downloads_liefern_artefakte_und_zählen_getrennt(tmp_path, monkeypatch):
    updater_ordner, zähler_datei = richte_meshcore_ble_updater_testdaten_ein(tmp_path, monkeypatch)
    android = updater_ordner / "Meshcore-BLE-Updater-v1.4.0-release.apk"
    windows = updater_ordner / "Meshcore-BLE-Updater-Win-v1.4.0.exe"
    ios = updater_ordner / "Meshcore-BLE-Updater-iOS-v1.4.0-unsigned.ipa"
    android.write_bytes(b"android")
    windows.write_bytes(b"windows")
    ios.write_bytes(b"ios")

    klient = app.test_client()
    android_antwort = klient.get("/downloads/meshcore-ble-updater/android.apk?quelle=button")
    windows_antwort = klient.get("/downloads/meshcore-ble-updater/windows.exe?quelle=button")
    ios_antwort = klient.get("/downloads/meshcore-ble-updater/ios-unsigned.ipa?quelle=button")

    assert android_antwort.status_code == 200
    assert windows_antwort.status_code == 200
    assert ios_antwort.status_code == 200
    assert android_antwort.data == b"android"
    assert windows_antwort.data == b"windows"
    assert ios_antwort.data == b"ios"
    assert "Meshcore-BLE-Updater-v1.4.0-release.apk" in android_antwort.headers["Content-Disposition"]
    assert "Meshcore-BLE-Updater-Win-v1.4.0.exe" in windows_antwort.headers["Content-Disposition"]
    assert "Meshcore-BLE-Updater-iOS-v1.4.0-unsigned.ipa" in ios_antwort.headers["Content-Disposition"]
    assert lies_downloads(zähler_datei, android) == 1
    assert lies_downloads(zähler_datei, windows) == 1
    assert lies_downloads(zähler_datei, ios) == 1

# Copyright © 2026 Erik Schauer, do1ffe@darc.de
