const autobahnSeite = document.querySelector("[data-autobahn-seite]");

if (autobahnSeite) {
  const startdatenElement = autobahnSeite.querySelector("[data-autobahn-startdaten]");
  const gesamtstatus = document.querySelector("[data-autobahn-gesamtstatus]");
  const messzeit = document.querySelector("[data-autobahn-messzeit]");
  const abrufzeit = document.querySelector("[data-autobahn-abrufzeit]");
  const glätteKarte = document.querySelector("[data-autobahn-glätte]");
  const glätteText = document.querySelector("[data-autobahn-glätte-text]");
  const quelllink = document.querySelector("[data-autobahn-quelllink]");
  let aktuelleDaten = null;

  const statusBeschriftungen = {
    current: "Aktuell",
    stale: "Veraltet",
    unavailable: "Nicht gemeldet",
    error: "Abruffehler",
    disabled: "Abruf deaktiviert",
  };

  const wertStatusBeschriftungen = {
    current: "Aktuell gemeldet",
    stale: "Letzter verfügbarer Wert",
    unavailable: "Nicht gemeldet",
    error: "Momentan nicht abrufbar",
    disabled: "Externer Abruf deaktiviert",
  };

  const zahlenformat = (wert, nachkommastellen = 1) =>
    new Intl.NumberFormat("de-DE", {
      minimumFractionDigits: nachkommastellen,
      maximumFractionDigits: nachkommastellen,
    }).format(wert);

  const hatMesswert = (messwert) =>
    messwert && [messwert.value, messwert.value_ms, messwert.degrees, messwert.cardinal].some((wert) => wert !== null && wert !== undefined && wert !== "");

  const formatiereMesswert = (schlüssel, messwert) => {
    if (!messwert || !hatMesswert(messwert)) {
      return messwert?.status === "error" ? "Momentan nicht abrufbar" : "Nicht gemeldet";
    }

    if (schlüssel === "road_condition") {
      return messwert.label || messwert.original_value || "Unbekannt";
    }
    if (["wind_direction", "wind_gust_direction"].includes(schlüssel)) {
      const richtung = messwert.cardinal || messwert.original_value || "";
      const grad = Number(messwert.degrees);
      return Number.isFinite(grad) ? `${richtung} (${zahlenformat(grad, 0)}°)` : richtung;
    }
    if (["wind_speed", "wind_gust"].includes(schlüssel)) {
      const kmh = Number(messwert.value_kmh);
      const ms = Number(messwert.value_ms);
      if (!Number.isFinite(kmh)) {
        return "Nicht gemeldet";
      }
      const kmhNachkommastellen = Math.abs(kmh - Math.round(kmh)) < 0.05 ? 0 : 1;
      return `${zahlenformat(kmh, kmhNachkommastellen)} km/h · ${zahlenformat(ms, 1)} m/s`;
    }

    const wert = messwert.value;
    if (typeof wert === "string") {
      return messwert.label || wert;
    }
    const zahl = Number(wert);
    if (!Number.isFinite(zahl)) {
      return "Nicht gemeldet";
    }
    if (schlüssel === "visibility") {
      const meter = `${zahlenformat(zahl, 0)} m`;
      return zahl >= 1000 ? `${meter} · ${zahlenformat(zahl / 1000, 1)} km` : meter;
    }
    if (schlüssel === "relative_humidity") {
      return `${zahlenformat(zahl, Math.abs(zahl - Math.round(zahl)) < 0.05 ? 0 : 1)} %`;
    }
    if (["air_temperature", "dew_point", "surface_temperature_fast_lane", "surface_temperature_other_lanes", "ground_temperature_10cm", "ground_temperature_30cm"].includes(schlüssel)) {
      return `${zahlenformat(zahl, 1)} °C`;
    }
    if (["water_film", "precipitation_15min"].includes(schlüssel)) {
      const stellen = Math.abs(zahl) < 1 && zahl !== 0 ? 2 : 1;
      return `${zahlenformat(zahl, stellen)} mm`;
    }
    return `${zahlenformat(zahl, 1)}${messwert.unit ? ` ${messwert.unit}` : ""}`;
  };

  const formatiereZeitpunkt = (wert, leertext) => {
    if (!wert) {
      return leertext;
    }
    const datum = new Date(wert);
    if (Number.isNaN(datum.getTime())) {
      return leertext;
    }
    return `${new Intl.DateTimeFormat("de-DE", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: "Europe/Berlin",
    }).format(datum)} Uhr`;
  };

  const aktualitätsklasse = (daten) => {
    if (!daten.enabled) {
      return "disabled";
    }
    if (!daten.measured_at) {
      return daten.status === "error" ? "error" : "unavailable";
    }
    const alterMinuten = (Date.now() - new Date(daten.measured_at).getTime()) / 60000;
    if (!Number.isFinite(alterMinuten)) {
      return "unavailable";
    }
    if (alterMinuten <= 30) {
      return "current";
    }
    if (alterMinuten <= 60) {
      return "stale";
    }
    return "very-stale";
  };

  const setzeGesamtstatus = (daten) => {
    if (!gesamtstatus) {
      return;
    }
    const klasse = aktualitätsklasse(daten);
    gesamtstatus.className = `autobahn-status autobahn-status--${klasse}`;
    if (klasse === "very-stale") {
      gesamtstatus.textContent = "Älter als 60 Minuten";
    } else if (klasse === "stale") {
      gesamtstatus.textContent = "31 bis 60 Minuten alt";
    } else {
      gesamtstatus.textContent = statusBeschriftungen[daten.status] || statusBeschriftungen.unavailable;
    }
  };

  const setzeMesswert = (schlüssel, messwert) => {
    document.querySelectorAll(`[data-autobahn-messwert="${schlüssel}"]`).forEach((karte) => {
      karte.hidden = !hatMesswert(messwert);
      const wert = karte.querySelector("[data-autobahn-wert]");
      const status = karte.querySelector("[data-autobahn-wert-status]");
      if (wert) {
        wert.textContent = formatiereMesswert(schlüssel, messwert);
      }
      if (status) {
        status.textContent = wertStatusBeschriftungen[messwert?.status] || wertStatusBeschriftungen.unavailable;
      }
      Array.from(karte.classList)
        .filter((klasse) => klasse.startsWith("autobahn-messwert--") && !["autobahn-messwert--gross"].includes(klasse))
        .forEach((klasse) => karte.classList.remove(klasse));
      karte.classList.add(`autobahn-messwert--${messwert?.status || "unavailable"}`);
      if (schlüssel === "road_condition" && typeof messwert?.value === "string") {
        const erlaubteZustände = ["dry", "damp", "wet", "frost", "snow", "ice", "slippery", "not_dry", "unknown"];
        if (erlaubteZustände.includes(messwert.value)) {
          karte.classList.add(`autobahn-messwert--condition-${messwert.value}`);
        }
      }
    });
  };

  const aktualisiereMesswertbereiche = () => {
    document.querySelectorAll("[data-autobahn-messwertbereich]").forEach((bereich) => {
      bereich.hidden = !bereich.querySelector("[data-autobahn-messwert]:not([hidden])");
    });
  };

  const setzeGlättehinweis = (hinweis) => {
    if (!glätteKarte || !glätteText || !hinweis) {
      return;
    }
    glätteKarte.classList.remove("autobahn-glätte--warning", "autobahn-glätte--uncertain", "autobahn-glätte--none");
    const stufe = ["warning", "uncertain", "none"].includes(hinweis.level) ? hinweis.level : "uncertain";
    glätteKarte.classList.add(`autobahn-glätte--${stufe}`);
    glätteKarte.setAttribute("role", stufe === "warning" ? "alert" : "status");
    glätteText.textContent = hinweis.text || "Keine vollständige Beurteilung der Glättegefahr möglich.";
  };

  const setzeQuelllink = (quelle) => {
    if (!quelllink || !quelle?.url) {
      return;
    }
    try {
      const url = new URL(quelle.url);
      const erlaubteHosts = new Set(["opendata.dwd.de", "kachelmannwetter.com"]);
      if (url.protocol === "https:" && erlaubteHosts.has(url.hostname)) {
        quelllink.href = url.href;
        if (typeof quelle.display_source === "string" && quelle.display_source.trim()) {
          quelllink.textContent = quelle.display_source.trim();
        }
      }
    } catch {
      // Der serverseitig geprüfte Standardlink bleibt erhalten.
    }
  };

  const zeigeDaten = (daten) => {
    if (!daten || typeof daten !== "object" || typeof daten.measurements !== "object") {
      return;
    }
    aktuelleDaten = daten;
    setzeGesamtstatus(daten);
    if (messzeit) {
      messzeit.textContent = formatiereZeitpunkt(daten.measured_at, "Keine Messzeit vorhanden");
    }
    if (abrufzeit) {
      abrufzeit.textContent = formatiereZeitpunkt(daten.fetched_at, "Noch nicht abgerufen");
    }
    Object.entries(daten.measurements).forEach(([schlüssel, messwert]) => setzeMesswert(schlüssel, messwert));
    aktualisiereMesswertbereiche();
    setzeGlättehinweis(daten.slipperiness);
    setzeQuelllink(daten.source);
  };

  const ladeLokaleDaten = async () => {
    try {
      const antwort = await fetch(`/api/autobahn?t=${Date.now()}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!antwort.ok) {
        throw new Error(`HTTP ${antwort.status}`);
      }
      const daten = await antwort.json();
      zeigeDaten(daten);
    } catch {
      // Die bereits dargestellten lokalen Messwerte bleiben bei einem Fehler sichtbar.
    }
  };

  if (startdatenElement) {
    try {
      zeigeDaten(JSON.parse(startdatenElement.textContent || "{}"));
    } catch {
      // Die serverseitige Darstellung bleibt bei unerwarteten Daten sichtbar.
    }
  }

  ladeLokaleDaten();
  window.setInterval(() => ladeLokaleDaten(), 60 * 1000);
}

// Copyright © 2026 Erik Schauer, do1ffe@darc.de
