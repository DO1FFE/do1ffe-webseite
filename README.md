# do1ffe-webseite

Mehrseitige Flask-Webseite für DO1FFE mit inhaltlichem Fokus auf Amateurfunk,
DARC e.V. OV L11, Tesla-Dashboard, öffentliche Dienste und MeshCore.

## Seitenstruktur

- `/` Startseite als Technik-Notizbuch und Themenübersicht
- `/ueber-mich` persönliche Seite zu Erik Schauer, DO1FFE
- `/ov-l11` DARC e.V. Ortsverband L11, Clubleben, Termine und Frequenzen
- `/tesla-dashboard` Erklärung zum Dashboard unter `tesla.do1ffe.de`
- `/autobahn` lokale Straßenwetter-Anzeige für Station H426 Essen-Ost
- `/dienste` kuratierte Auswahl öffentlich freigegebener Subdomains
- `/meshcore` LoRa-Mesh, Off-Grid-Kommunikation und Monitoring
- `/meshcore#app` direkter Sprung zur Android-App
- `/downloads/meshcore-repeater-konfigurator.apk` aktuelle APK des MeshCore Repeater-Konfigurators als kompatibler Alias
- `/downloads/meshcore-repeater-konfigurator/v<version>.apk` historische APK-Version
- `/kontakt` Kontakt und weiterführende Einstiege

Die alten Einstiege `/github` und `/projekte` leiten kompatibel auf `/dienste` weiter.

## Downloads

Die MeshCore-Seite verlinkt die jeweils neueste signierte APK über den expliziten
Versionslink `/downloads/meshcore-repeater-konfigurator/v<version>.apk`.
Der Alias `/downloads/meshcore-repeater-konfigurator.apk` bleibt kompatibel.
Die Dateien liegen unter:

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

## Suchmaschinen und kanonische URLs

Die kanonische Basis ist `https://do1ffe.de`. Aufrufe über `www.do1ffe.de`
werden dauerhaft auf die entsprechende Non-www-URL umgeleitet. Öffentliche
Inhaltsseiten liefern je eine kanonische URL, individuelle Metadaten und
strukturierte Daten aus. `robots.txt` verweist auf die XML-Sitemap und schließt
API-Pfade vom Crawling aus. Downloadpfade dürfen gecrawlt werden, damit
Suchmaschinen ihren ausschließenden `X-Robots-Tag` auswerten können. API- und
Downloadantworten tragen diesen `X-Robots-Tag`.

Impressum und Datenschutzerklärung bleiben intern verlinkt und erreichbar,
werden aber bewusst mit `noindex,follow` ausgeliefert und stehen daher nicht in
der Sitemap. Fehlerseiten liefern den tatsächlichen HTTP-Status, keine
kanonische URL und `noindex`.

## Straßenwetter Essen-Ost

`/autobahn` zeigt ausschließlich lokal gespeicherte Messwerte der Station H426
„Essen-Ost“ am Autobahndreieck A40/A52. Die maschinenlesbare, nur lesende
Schnittstelle liegt unter `/api/autobahn`. Fehlende Parameter bleiben `null`;
es werden weder benachbarte Stationen noch Vorhersagen als Ersatz verwendet.

Beim ersten Zugriff oder CLI-Aufruf werden die SQLite-Tabellen
`road_weather_current`, `road_weather_history` und `road_weather_meta` unter
`daten/strassenwetter.sqlite3` automatisch angelegt. Eine separate Migration
ist bei dieser bislang datenbanklosen Anwendung nicht erforderlich. Alte
Historieneinträge werden ausschließlich aus `road_weather_history` entfernt.

### Amtliche Datenquelle

Die aktive Aktualisierung verwendet die offiziellen, viertelstündlichen
GMA-Messdaten des Deutschen Wetterdienstes im BUFR-Format. Der DWD stellt diese
Daten als Open Data nutzungsentgeltfrei und ohne Nutzungsbeschränkungen bereit.
Als Datenbasis werden entsprechend der DWD-Vorgabe das BMVBS und die
Straßenbauverwaltungen der Länder genannt. Die ursprüngliche HTML-Quelle wird
nicht automatisiert abgefragt, weil deren veröffentlichte Nutzungsbedingungen
automatisierte Skriptabrufe untersagen.

Zur BUFR-Dekodierung wird das offizielle ecCodes-Werkzeug benötigt:

```bash
sudo apt-get install libeccodes-tools
```

### Konfiguration

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `ROAD_WEATHER_ENABLED` | `false` | externen Abruf ausdrücklich aktivieren |
| `ROAD_WEATHER_STATION_ID` | `H426` | feste Stations-ID; andere Werte werden abgelehnt |
| `ROAD_WEATHER_CONTACT_EMAIL` | leer | echte Betreiberadresse für den User-Agent |
| `ROAD_WEATHER_FETCH_INTERVAL` | `900` | Mindestabstand in Sekunden; Werte unter 900 werden angehoben |
| `ROAD_WEATHER_REQUEST_TIMEOUT` | `10` | Timeout-Limit, maximal 10 Sekunden |
| `ROAD_WEATHER_STALE_AFTER` | `1800` | Grenze für veraltete Messungen in Sekunden |
| `ROAD_WEATHER_HISTORY_RETENTION_DAYS` | `90` | Aufbewahrung der Historie |
| `ROAD_WEATHER_DATABASE` | `daten/strassenwetter.sqlite3` | SQLite-Datei |
| `ROAD_WEATHER_LOCK_FILE` | `daten/strassenwetter.lock` | dateibasierte Prozesssperre |
| `ROAD_WEATHER_SOURCE_URL` | DWD Open Data, KM/NW, `LATEST` | amtlicher aktueller BUFR-Datensatz |
| `ROAD_WEATHER_SOURCE_URLS_JSON` | `{}` | nur für den deaktivierten HTML-Fallback |
| `ROAD_WEATHER_MAX_RESPONSE_BYTES` | `2097152` | maximale Quellantwortgröße |

Quell- und Weiterleitungsziele werden unabhängig von der Konfiguration auf
HTTPS, den exakten Host `opendata.dwd.de`, das NRW-Verzeichnis `KM` und den
passenden Dateinamen begrenzt. Der BUFR-Datensatz wird lokal mit ecCodes
dekodiert; ausschließlich die exakte Stationskennung H426 wird übernommen.

### Aktualisierung und Betrieb

Eine manuelle, intervallgeschützte Aktualisierung erfolgt mit:

```bash
flask --app app road-weather-update
```

Nur für administrative Tests kann `--force` die lokale 15-Minuten-Prüfung
ignorieren. Die Webseite und `/api/autobahn` lösen niemals selbst einen
externen Abruf aus. Historienbereinigung ist zusätzlich möglich mit:

```bash
flask --app app road-weather-cleanup
```

Für den Produktivbetrieb liegen eine systemd-Service- und Timer-Konfiguration
unter `deployment/` bereit. `do1ffe-strassenwetter.timer` startet den getrennten
Aktualisierungsprozess passend zu den Messintervallen täglich um Minute 02, 17,
32 und 47. Der zweiminütige Puffer gibt dem DWD Zeit zur Bereitstellung der
Messung von Minute 00, 15, 30 beziehungsweise 45. Die Prozesssperre verhindert
zusätzlich gleichzeitige Aktualisierungen aus mehreren Prozessen. Ein
Cron-Beispiel bleibt als Alternative erhalten.

### Fehlerbehandlung und Einschränkungen

- Temporäre Netzfehler lassen den letzten gültigen Wert als `stale` bestehen.
- Eine erreichbare Parameterseite ohne H426 liefert `unavailable`, nie den Wert
  einer anderen Station und nie `0` als Ersatz.
- HTTP 401, 403 und 429 werden nicht umgangen; weitere Abrufe werden
  kontrolliert beendet.
- Änderungen an den DWD-BUFR-Tabellen können eine Anpassung des Decoders
  erfordern.
- H426 meldet nicht zwangsläufig alle 19 auswählbaren Messgrößen.
- Das Abrufintervall beträgt mindestens 15 Minuten.
- Die Anzeige ersetzt keine amtlichen Verkehrs- oder Unwetterwarnungen.

Die Tests einschließlich lokaler HTML-Fixtures werden wie gewohnt mit
`python3 -m pytest` ausgeführt. Sie benötigen weder Internetzugriff noch echte
Messwerte.
