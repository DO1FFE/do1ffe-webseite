# do1ffe-webseite

Mehrseitige Flask-Webseite fuer DO1FFE mit inhaltlichem Fokus auf Amateurfunk,
DARC e.V. OV L11, Tesla-Dashboard, GitHub-Repositories und MeshCore.

## Seitenstruktur

- `/` Startseite als Technik-Notizbuch und Themenuebersicht
- `/ov-l11` DARC e.V. Ortsverband L11, Clubleben, Termine und Frequenzen
- `/tesla-dashboard` Erklaerung zum Dashboard unter `tesla.do1ffe.de`
- `/github` Auswahl oeffentlicher GitHub-Repositories
- `/meshcore` LoRa-Mesh, Off-Grid-Kommunikation und Monitoring
- `/kontakt` Kontakt und weiterfuehrende Einstiege

Die alten Einstiege `/ueber-mich` und `/projekte` bleiben als kompatible Routen erreichbar.

## Starten

```bash
pip install -r requirements.txt
python app.py
```

Danach ist die Seite unter `http://0.0.0.0:8020` erreichbar.

## Tests

```bash
python -m pytest
```
