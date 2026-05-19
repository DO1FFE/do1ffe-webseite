# do1ffe-webseite

Mehrseitige Flask-Webseite für DO1FFE mit inhaltlichem Fokus auf Amateurfunk,
DARC e.V. OV L11, Tesla-Dashboard, GitHub-Repositories und MeshCore.

## Seitenstruktur

- `/` Startseite als Technik-Notizbuch und Themenübersicht
- `/ov-l11` DARC e.V. Ortsverband L11, Clubleben, Termine und Frequenzen
- `/tesla-dashboard` Erklärung zum Dashboard unter `tesla.do1ffe.de`
- `/github` Auswahl öffentlicher GitHub-Repositories
- `/meshcore` LoRa-Mesh, Off-Grid-Kommunikation und Monitoring
- `/meshcore#app` direkter Sprung zur Android-App
- `/downloads/meshcore-repeater-konfigurator.apk` aktuelle APK des MeshCore Repeater-Konfigurators
- `/downloads/meshcore-repeater-konfigurator/v<version>.apk` historische APK-Version
- `/kontakt` Kontakt und weiterführende Einstiege

Die alten Einstiege `/ueber-mich` und `/projekte` bleiben als kompatible Routen erreichbar.

## Downloads

Die MeshCore-Seite verlinkt die jeweils neueste signierte APK aus:

```text
/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator/
```

Historische Versionen werden zusätzlich aus folgendem Artefaktordner gelesen:

```text
/home/do1ffe/meshcore-repeater-konfigurator/artifacts/
```

Erwartet werden Dateinamen nach dem Muster:

```text
MeshCoreRepeaterKonfigurator-<version>-release-signed.apk
```

Die Download-Zähler werden je Version in folgender JSON-Datei gespeichert:

```text
/home/do1ffe/software-downloads/MeshCoreRepeaterKonfigurator/download-zaehler.json
```

Die sichtbare Download-Historie beginnt mit Version `1.0.22`.

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
