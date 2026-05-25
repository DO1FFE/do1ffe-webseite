import json

import app as webseite

app = webseite.app


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
        "/ueber-mich",
        "/projekte",
    ]:
        antwort = klient.get(route)
        assert antwort.status_code == 200


def test_startseite_verlinkt_unterseiten():
    klient = app.test_client()
    antwort = klient.get("/")
    html = antwort.get_data(as_text=True)

    assert "/ov-l11" in html
    assert "/tesla-dashboard" in html
    assert "/github" in html
    assert "/meshcore" in html


def test_githubseite_enthält_repo_auswahl():
    klient = app.test_client()
    antwort = klient.get("/github")
    html = antwort.get_data(as_text=True)

    assert "tesla-dashboard" in html
    assert "CoreScope" in html
    assert "meshcore-network-monitor" in html
    assert "https://github.com/do1ffe" in html


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
