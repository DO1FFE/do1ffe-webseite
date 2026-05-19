from app import app


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
