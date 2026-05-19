import json

import app as webseite

app = webseite.app


def richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch):
    download_ordner = tmp_path / "downloads"
    archiv_ordner = tmp_path / "artifacts"
    download_ordner.mkdir()
    archiv_ordner.mkdir()
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_APK_ORDNER", download_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_ARCHIV_ORDNER", archiv_ordner)
    monkeypatch.setattr(webseite, "MESHCORE_REPEATER_DOWNLOAD_ZÄHLER_DATEI", tmp_path / "download-zaehler.json")
    return download_ordner, archiv_ordner, tmp_path / "download-zaehler.json"


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
    assert "/downloads/meshcore-repeater-konfigurator.apk" in html
    assert "Gedacht für Android-Handys" in html
    assert "meshcore-repeater-konfigurator-apk-qr.png" in html
    assert "MeshCore Repeater-Konfigurator direkt herunterladen" in html


def test_meshcoreseite_blendet_historie_vor_1_0_22_aus(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.20-release-signed.apk").write_bytes(b"alt")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk").write_bytes(b"mittel")
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")
    zähler_datei.write_text(json.dumps({"1.0.20": 3, "1.0.21": 10, "1.0.22": 4}), encoding="utf-8")

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
    zähler_datei.write_text(json.dumps({"1.0.21": 10, "1.0.22": 7, "1.0.23": 2}), encoding="utf-8")

    klient = app.test_client()
    antwort = klient.get("/meshcore")
    html = antwort.get_data(as_text=True)

    assert "V1.0.23" in html
    assert "Vergangene Versionen" in html
    assert "V1.0.22" in html
    assert "7 Downloads" in html
    assert "V1.0.21" not in html
    assert "10 Downloads" not in html


def test_repeater_konfigurator_download_liefert_neuste_apk_und_zählt(tmp_path, monkeypatch):
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
    assert json.loads(zähler_datei.read_text(encoding="utf-8"))["1.0.22"] == 1


def test_repeater_konfigurator_download_zählt_versioniert(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")
    (archiv_ordner / "MeshCoreRepeaterKonfigurator-1.0.21-release-signed.apk").write_bytes(b"alt")
    zähler_datei.write_text(json.dumps({"1.0.21": 9}), encoding="utf-8")

    klient = app.test_client()
    antwort = klient.get("/downloads/meshcore-repeater-konfigurator/v1.0.21.apk")

    assert antwort.status_code == 200
    assert antwort.data == b"alt"
    assert json.loads(zähler_datei.read_text(encoding="utf-8"))["1.0.21"] == 10


def test_repeater_konfigurator_head_zählt_nicht(tmp_path, monkeypatch):
    download_ordner, archiv_ordner, zähler_datei = richte_repeater_apk_testdaten_ein(tmp_path, monkeypatch)
    (download_ordner / "MeshCoreRepeaterKonfigurator-1.0.22-release-signed.apk").write_bytes(b"neu")

    klient = app.test_client()
    antwort = klient.head("/downloads/meshcore-repeater-konfigurator.apk")

    assert antwort.status_code == 200
    assert not zähler_datei.exists()
