from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def startseite():
    return render_template('startseite.html')


@app.route('/ueber-mich')
def ueber_mich():
    return render_template('ueber_mich.html')


@app.route('/projekte')
def projekte():
    repos = [
        {
            'name': 'do1ffe-webseite',
            'beschreibung': 'Mehrseitige Flask-Webseite mit strukturierter Navigation und umfangreichen Inhalten.',
            'url': 'https://github.com/do1ffe/do1ffe-webseite',
        },
        {
            'name': 'tesla-dashboard',
            'beschreibung': 'Dashboard zur Visualisierung von Fahrzeugdaten mit Fokus auf Transparenz und Alltagstauglichkeit.',
            'url': 'https://tesla.do1ffe.de',
        },
        {
            'name': 'funk-skripte',
            'beschreibung': 'Werkzeuge und Automationen für Amateurfunk-Workflows, Auswertungen und Stationsbetrieb.',
            'url': 'https://github.com/do1ffe',
        },
    ]
    return render_template('projekte.html', repos=repos)


@app.route('/kontakt')
def kontakt():
    return render_template('kontakt.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8020)
