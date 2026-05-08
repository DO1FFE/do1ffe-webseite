from app import app


def test_alle_seiten_erreichbar():
    klient = app.test_client()
    for route in ['/', '/ueber-mich', '/projekte', '/kontakt']:
        antwort = klient.get(route)
        assert antwort.status_code == 200


def test_projektseite_enthaelt_github_link():
    klient = app.test_client()
    antwort = klient.get('/projekte')
    html = antwort.get_data(as_text=True)
    assert 'https://github.com/do1ffe' in html
    assert 'tesla-dashboard' in html
