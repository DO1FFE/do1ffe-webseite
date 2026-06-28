const header = document.querySelector("[data-header]");
const nav = document.querySelector("[data-nav]");
const toggle = document.querySelector("[data-nav-toggle]");
const farbschemaSchalter = document.querySelector("[data-theme-toggle]");
const farbschemaSchalterText = document.querySelector("[data-theme-toggle-label]");
const year = document.querySelector("[data-year]");
const tempCo2Anzeige = document.querySelector("[data-tempco2]");
const tempCo2Temperatur = document.querySelector("[data-tempco2-temp]");
const tempCo2Luftfeuchtigkeit = document.querySelector("[data-tempco2-humidity]");
const tempCo2Co2 = document.querySelector("[data-tempco2-co2]");
const tempCo2Seitenwerte = document.querySelector("[data-tempco2-page-current]");
const tempCo2SeitenLeer = document.querySelector("[data-tempco2-page-empty]");
const tempCo2SeitenTemperatur = document.querySelector("[data-tempco2-page-temp]");
const tempCo2SeitenLuftfeuchtigkeit = document.querySelector("[data-tempco2-page-humidity]");
const tempCo2SeitenCo2 = document.querySelector("[data-tempco2-page-co2]");
const tempCo2SeitenZeit = document.querySelector("[data-tempco2-page-time]");
const tempCo2SeitenDatum = document.querySelector("[data-tempco2-page-date]");
const tempCo2LageCo2 = document.querySelector("[data-tempco2-lage-co2]");
const tempCo2LageTemperatur = document.querySelector("[data-tempco2-lage-temp]");
const tempCo2LageLuftfeuchtigkeit = document.querySelector("[data-tempco2-lage-luft]");
const tempCo2Diagramme = document.querySelectorAll("[data-tempco2-chart]");
const tempCo2TabButtons = document.querySelectorAll("[data-tempco2-tab]");
const tempCo2TabPanels = document.querySelectorAll("[data-tempco2-tab-panel]");
let tempCo2AktuelleDaten = null;
let tempCo2TrendMesswerte = [];
const tempCo2DiagrammStatus = new Map();
const tempCo2DiagrammCacheMillis = 55 * 1000;
const tempCo2MaxSichtbareMesspunkte = 90;

document.body.classList.remove("no-js");

if (year) {
  year.textContent = new Date().getFullYear().toString();
}

const farbschemaSpeicherSchlüssel = "farbschema";
const systemFarbschemaAbfrage = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

const liesGespeichertesFarbschema = () => {
  try {
    return localStorage.getItem(farbschemaSpeicherSchlüssel);
  } catch {
    return null;
  }
};

const speichereFarbschema = (farbschema) => {
  try {
    localStorage.setItem(farbschemaSpeicherSchlüssel, farbschema);
  } catch {
    // Ohne lokalen Speicher funktioniert der Schalter trotzdem für die aktuelle Seite.
  }
};

const ermittleGewünschtesFarbschema = () => {
  const gespeichertesFarbschema = liesGespeichertesFarbschema();
  if (["hell", "dunkel"].includes(gespeichertesFarbschema)) {
    return gespeichertesFarbschema;
  }
  return systemFarbschemaAbfrage?.matches ? "dunkel" : "hell";
};

const setzeFarbschema = (farbschema, optionen = {}) => {
  const istDunkel = farbschema === "dunkel";
  const beschriftung = istDunkel ? "Hellmodus aktivieren" : "Dunkelmodus aktivieren";
  document.documentElement.dataset.theme = istDunkel ? "dark" : "light";
  document.documentElement.style.colorScheme = istDunkel ? "dark" : "light";

  if (farbschemaSchalter) {
    farbschemaSchalter.setAttribute("aria-pressed", istDunkel.toString());
    farbschemaSchalter.setAttribute("aria-label", beschriftung);
    farbschemaSchalter.setAttribute("title", beschriftung);
  }
  if (farbschemaSchalterText) {
    farbschemaSchalterText.textContent = istDunkel ? "Hell" : "Dunkel";
  }
  if (optionen.speichern) {
    speichereFarbschema(farbschema);
  }
};

setzeFarbschema(ermittleGewünschtesFarbschema());

if (farbschemaSchalter) {
  farbschemaSchalter.addEventListener("click", () => {
    const nächstesFarbschema = document.documentElement.dataset.theme === "dark" ? "hell" : "dunkel";
    setzeFarbschema(nächstesFarbschema, { speichern: true });
  });
}

if (systemFarbschemaAbfrage) {
  const reagiereAufSystemFarbschema = (event) => {
    if (liesGespeichertesFarbschema()) {
      return;
    }
    setzeFarbschema(event.matches ? "dunkel" : "hell");
  };

  if (systemFarbschemaAbfrage.addEventListener) {
    systemFarbschemaAbfrage.addEventListener("change", reagiereAufSystemFarbschema);
  } else if (systemFarbschemaAbfrage.addListener) {
    systemFarbschemaAbfrage.addListener(reagiereAufSystemFarbschema);
  }
}

const syncHeader = () => {
  if (!header) return;
  header.classList.toggle("is-scrolled", window.scrollY > 24);
};

syncHeader();
window.addEventListener("scroll", syncHeader, { passive: true });

if (toggle && nav) {
  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", isOpen.toString());
  });

  nav.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

const tempCo2TabIdAusHash = () => {
  if (!window.location.hash) {
    return "";
  }

  const panel = document.getElementById(window.location.hash.slice(1));
  if (panel instanceof HTMLElement && panel.matches("[data-tempco2-tab-panel]")) {
    return panel.getAttribute("data-tempco2-tab-panel") || "";
  }
  return "";
};

const aktiviereTempCo2Tab = (tabId, optionen = {}) => {
  if (!tabId || tempCo2TabButtons.length === 0 || tempCo2TabPanels.length === 0) {
    return;
  }

  let aktivesPanel = null;
  tempCo2TabPanels.forEach((panel) => {
    const istAktiv = panel.getAttribute("data-tempco2-tab-panel") === tabId;
    panel.hidden = !istAktiv;
    panel.classList.toggle("is-active", istAktiv);
    if (istAktiv) {
      aktivesPanel = panel;
    }
  });

  tempCo2TabButtons.forEach((button) => {
    const istAktiv = button.getAttribute("data-tempco2-tab") === tabId;
    button.classList.toggle("is-active", istAktiv);
    button.setAttribute("aria-selected", istAktiv.toString());
    button.setAttribute("tabindex", istAktiv ? "0" : "-1");
    if (istAktiv && optionen.fokus) {
      button.focus({ preventScroll: true });
    }
  });

  if (optionen.scrollen && aktivesPanel) {
    window.requestAnimationFrame(() => aktivesPanel.scrollIntoView({ block: "start" }));
  }

  if (aktivesPanel) {
    window.requestAnimationFrame(() => ladeTempCo2Diagramm(aktivesPanel));
  }
};

if (tempCo2TabButtons.length && tempCo2TabPanels.length) {
  aktiviereTempCo2Tab(tempCo2TabIdAusHash() || "tag");

  tempCo2TabButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      const tabId = button.getAttribute("data-tempco2-tab");
      aktiviereTempCo2Tab(tabId || "");
      const panelId = button.getAttribute("aria-controls");
      if (panelId) {
        window.history.replaceState(null, "", `#${panelId}`);
      }
    });

    button.addEventListener("keydown", (event) => {
      const tasten = ["ArrowLeft", "ArrowRight", "Home", "End"];
      if (!tasten.includes(event.key)) {
        return;
      }

      event.preventDefault();
      let nächsterIndex = index;
      if (event.key === "ArrowLeft") {
        nächsterIndex = (index - 1 + tempCo2TabButtons.length) % tempCo2TabButtons.length;
      } else if (event.key === "ArrowRight") {
        nächsterIndex = (index + 1) % tempCo2TabButtons.length;
      } else if (event.key === "Home") {
        nächsterIndex = 0;
      } else if (event.key === "End") {
        nächsterIndex = tempCo2TabButtons.length - 1;
      }

      const nächsterButton = tempCo2TabButtons[nächsterIndex];
      aktiviereTempCo2Tab(nächsterButton.getAttribute("data-tempco2-tab") || "", { fokus: true });
    });
  });

  window.addEventListener("hashchange", () => {
    const tabId = tempCo2TabIdAusHash();
    if (tabId) {
      aktiviereTempCo2Tab(tabId, { scrollen: true });
    }
  });
}

const formatiereDezimalzahl = (wert) =>
  new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(wert);

const tempCo2LageSprüche = {
  co2: {
    frisch: [
      "Die Luft unterschreibt gerade freiwillig ein Führungszeugnis. Fenster darf entspannt bleiben.",
      "Hier kann man noch denken, ohne dass die Synapsen einen Betriebsrat gründen.",
      "CO2 benimmt sich vorbildlich. Der Fenstergriff trägt heute nur Schmuckfunktion.",
      "Raumluft im Vorzeigemodus. Selbst die Messstelle wirkt kurz zufrieden.",
      "Alles erstaunlich klar. Die Wohnung klingt innerlich wie frisch sortierte Tabellen.",
      "Die Luft hat sich gekämmt, geduscht und pünktlich beim Sensor gemeldet.",
      "Fenster bleibt Reservebank. Die aktuelle Luft spielt noch erste Liga.",
      "So frisch, dass der Sensor fast höflich salutiert.",
    ],
    normal: [
      "Noch alles zivilisiert, aber der Fenstergriff legt schon demonstrativ den Finger auf die Tagesordnung.",
      "Die Luft ist nicht schlecht, sie erzählt nur schon etwas länger dieselbe Geschichte.",
      "CO2 hebt vorsichtig die Hand und fragt, ob gleich gelüftet wird oder ob das ein Charaktertest ist.",
      "Der Raum wirkt noch professionell, aber die Tagesordnung bekommt den Punkt „Fenster?“",
      "Alles im grünen Bereich, nur nicht mehr ganz mit Konfetti und Fanfare.",
      "Die Wohnung sagt: „Passt schon“, und genau deshalb schaut der Sensor zweimal hin.",
      "Noch kein Drama. Eher ein dezentes Räuspern aus der Raumluftabteilung.",
      "Die Luft ist brauchbar, aber sie hat den Lüftungsantrag schon als Entwurf gespeichert.",
    ],
    aufmerksam: [
      "Der Raum beantragt eine Lüftungspause mit Nachdruck und leicht hochgezogener Augenbraue.",
      "CO2 tritt ans Mikrofon und bedankt sich für die viele Redezeit.",
      "Die Luft macht jetzt auf Besprechungszimmer und verteilt unsichtbare Protokolle.",
      "Noch nicht schlimm, aber das Fenster sollte schon mal sein Namensschild polieren.",
      "Der Sensor schaut streng. Nicht böse, nur enttäuscht professionell.",
      "Die Wohnung tut so, als wäre alles normal. Die Zahlen erzählen eine andere Pressemitteilung.",
      "Jetzt wäre ein kurzer Luftwechsel keine Schwäche, sondern Führungsstärke.",
      "CO2 winkt aus der zweiten Reihe und möchte bald Tagesordnungspunkt eins werden.",
    ],
    lüften: [
      "Sitzung vertagen, Fenster auf, die Luft möchte sonst eine eigene Abteilung gründen.",
      "Der Raum riecht statistisch nach „noch fünf Minuten“, und genau da beginnt das Problem.",
      "CO2 ist nicht mehr zu Gast, CO2 hat schon einen Schreibtisch beantragt.",
      "Das Fenster sollte jetzt nicht nur dekorativ herumstehen.",
      "Die Luft schreibt eine Beschwerde mit Durchschlag an den Fenstergriff.",
      "Hier wird aus Raumklima langsam Raumklimakonferenz.",
      "Die Messstelle empfiehlt Sauerstoff mit Nachdruck und ohne PowerPoint.",
      "Der Sensor räuspert sich so laut, wie ein Sensor sich eben räuspern kann.",
    ],
    alarm: [
      "Fenster auf. Nicht diskutieren, die Luft hat gerade den Krisenmodus unterschrieben.",
      "CO2 hat die Moderation übernommen. Das war so nicht im Raumplan vorgesehen.",
      "Die Wohnung probt Innenraum-Drama mit Zahlenbeweis.",
      "Der Fenstergriff sollte jetzt Karriere machen.",
      "Atmen ist hier noch erlaubt, aber die Luft verlangt langsam Gebühren.",
      "Das Raumklima ruft nicht mehr, es diktiert.",
      "Die Messstelle empfiehlt: öffnen, lüften, kurz so tun, als sei das von Anfang an geplant gewesen.",
      "Wenn Zahlen sprechen könnten, würde diese hier mit Warnweste auftreten.",
    ],
  },
  temperatur: {
    kalt: [
      "Die Wohnung übt Keller. Hausschuhe schreiben schon Bewerbungen.",
      "Kühl genug, dass der Schreibtisch über eine Strickjacke nachdenkt.",
      "Thermisch eher Nordseite des Lebens. Noch okay, aber nicht gerade Urlaubsprospekt.",
      "Die Heizung schaut aus der Ferne und fragt, ob sie gemeint war.",
      "Der Raum gibt sich sachlich, fast schon behördlich frisch.",
      "Gemütlichkeit wurde kurz zur Stellungnahme eingeladen.",
      "Die Temperatur trägt heute Aktentasche statt Pantoffeln.",
      "Noch kein Frost, aber der Tee fühlt sich sehr wichtig.",
    ],
    neutral: [
      "Seriöse Zimmertemperatur. Weder Sauna noch Kühlhaus, die Mitte trägt Krawatte.",
      "Temperatur im Diplomatenmodus: niemand beleidigt, niemand schwitzt.",
      "Das Raumklima wirkt kontrolliert, als hätte jemand heimlich eine Checkliste geführt.",
      "Hier kann man sitzen, arbeiten und so tun, als hätte man alles im Griff.",
      "Die Wohnung meldet: thermisch unauffällig, bürokratisch verwertbar.",
      "Sehr erwachsen. Fast verdächtig erwachsen.",
      "Der Sensor nickt, legt den Stempel weg und trinkt innerlich Kaffee.",
      "Alles angenehm normal. Genau die Sorte normal, die in Graphen kaum Schlagzeilen macht.",
    ],
    warm: [
      "Gemütlich warm. Das Sofa nickt fachlich und tut so, als wäre das geplant.",
      "Die Wohnung hat den Komfortmodus gefunden und hält ihn jetzt für eine Persönlichkeit.",
      "Warm genug für Zufriedenheit, noch nicht warm genug für Beschwerden mit Aktenzeichen.",
      "Der Raum sagt „angenehm“, der Sensor sagt „ich dokumentiere das trotzdem“.",
      "Das Thermometer lächelt leicht und füllt dabei Formblatt 27b aus.",
      "Wohlfühlzone mit leichter Tendenz zum „Fenster später vielleicht“.",
      "Hier kann man sitzen bleiben, ohne dass die Stirn eine Pressemitteilung schreibt.",
      "Die Temperatur macht es sich bequem und stellt keine weiteren Fragen.",
    ],
    sommer: [
      "Sommermodus im Wohnzimmer. Das Fenster bekommt langsam Projektverantwortung.",
      "Die Wohnung probt Urlaub, leider ohne Meer und mit mehr WLAN.",
      "Der Raum wärmt vor. Wofür, weiß niemand, aber er wirkt entschlossen.",
      "Langsam wird es warm genug, dass der Fenstergriff im Organigramm aufsteigt.",
      "Thermisch wird hier nicht diskutiert, sondern geschwitzt mit Stil.",
      "Die Luft trägt kurze Ärmel, obwohl sie gar keine hat.",
      "Das Thermometer schaut über den Rand seiner Akte und sagt: „Interessant.“",
      "Noch wohnlich, aber die Temperatur hat schon Sonnenbrille im Warenkorb.",
    ],
    heiß: [
      "Die Wohnung testet Backofen-Praktikum. Bitte keine Pizza auf den Schreibtisch legen.",
      "Das Raumklima macht auf Wellnessbereich, nur ohne Handtücher und Anmeldung.",
      "Hier wird Wärme nicht gemessen, sondern verwaltet.",
      "Der Sensor fragt, ob das noch Wohnen ist oder schon Vorheizen.",
      "Das Fenster sollte nicht mehr warten, es sollte auftreten.",
      "Die Temperatur hat Führungsanspruch angemeldet und wirkt dabei unangenehm überzeugt.",
      "Wenn der Raum jetzt noch Musik hätte, wäre es ein sehr kleiner Club.",
      "Die Wohnung schiebt thermisch Überstunden.",
    ],
  },
  luftfeuchte: {
    trocken: [
      "Trocken wie ein Amtsformular. Wasserglas fühlt sich plötzlich systemrelevant.",
      "Die Luft knistert gedanklich und beantragt Handcreme.",
      "Feuchtigkeit ist anwesend, aber nur als Gerücht.",
      "Die Raumluft wirkt, als hätte sie gerade Papier sortiert.",
      "Trocken genug, dass Zimmerpflanzen eine Beschwerde vorbereiten könnten.",
      "Das Klima staubt nicht, es formuliert staubtrocken.",
      "Luftfeuchte im Sparprogramm. Sehr effizient, sehr freudlos.",
      "Die Messstelle empfiehlt ein Glas Wasser, mindestens für die Moral.",
    ],
    leichtTrocken: [
      "Etwas trocken, aber noch nicht Pergament. Die Luft bittet um mehr Eleganz.",
      "Die Feuchte ist da, nur mit sehr schmalem Budget.",
      "Noch okay, aber die Luft klingt schon ein bisschen nach Archiv.",
      "Der Raum ist trocken genug, um seriös zu wirken, aber nicht genug für Applaus.",
      "Luftfeuchte in Teilzeit. Sie macht mit, aber ohne Begeisterung.",
      "Alles brauchbar, nur das Wort „samtig“ bleibt heute im Schrank.",
      "Die Wohnung sagt: „Geht doch“, und die Schleimhäute schauen misstrauisch.",
      "Ein Hauch mehr Feuchte wäre kein Luxus, sondern Innenraumdiplomatie.",
    ],
    gut: [
      "Im Wohlfühlkorridor. Die Messstelle setzt ein Häkchen und schaut sehr wichtig.",
      "Luftfeuchte benimmt sich. Das Protokoll notiert ein seltenes „unauffällig“.",
      "Hier ist nichts klebrig, nichts trocken, einfach solide Wohnungsarbeit.",
      "Die Feuchte trifft die Mitte und tut so, als sei das mühelos.",
      "Sehr ordentlich. Der Sensor könnte jetzt theoretisch eine Urkunde drucken.",
      "Die Luft fühlt sich weder Wüste noch Waschküche. Ein kleiner Verwaltungssegen.",
      "Das Raumklima steht gerade erstaunlich gerade in der Landschaft.",
      "Feuchte im Normalbereich. Keine Schlagzeile, aber gute Verwaltung.",
    ],
    feucht: [
      "Leicht schwitzig. Die Luft reicht vorsichtig ein Handtuch durch den Dienstweg.",
      "Die Feuchte wird gesprächig und setzt sich etwas zu bequem hin.",
      "Noch harmlos, aber die Wohnung sagt schon „ich war nur kurz duschen“.",
      "Das Raumklima wird weicher. Nicht dramatisch, aber sehr präsent.",
      "Luftfeuchte drückt sich in den Vordergrund und tut überrascht.",
      "Der Sensor hebt eine Augenbraue. Die andere wartet noch auf weitere Daten.",
      "Ein bisschen Lüften könnte aus dieser Feuchte wieder gute Laune machen.",
      "Die Luft fühlt sich an, als hätte sie gerade eine Jacke zu viel an.",
    ],
    sehrFeucht: [
      "Feuchte hält Betriebsversammlung. Bitte Tagesordnungspunkt Lüften aufnehmen.",
      "Die Luft hat Wellness gebucht und niemanden gefragt.",
      "Jetzt wird es innenraumklimatisch sehr selbstbewusst.",
      "Die Feuchte steht nicht mehr im Raum, sie sitzt schon am Kopfende.",
      "Das Fenster sollte sich vorbereiten, gleich ist sein großer Auftritt.",
      "Hier beginnt die Zone, in der Handtücher theoretisch politische Ambitionen entwickeln.",
      "Die Messstelle empfiehlt Luftwechsel, bevor die Wand anfängt mitzulesen.",
      "Feuchtigkeit mit Sendungsbewusstsein. Das muss nicht sein.",
    ],
  },
  offline: {
    co2: [
      "Keine frischen ppm: Die Luft verweigert gerade die Pressekonferenz.",
      "CO2-Wert fehlt. Der Raum hat die Aussage vorerst vertagt.",
      "Die ppm-Abteilung ist kurz nicht erreichbar und lässt ausrichten: „bitte später lüften“.",
      "Keine neue CO2-Meldung. Der Sensor übt offenbar Datenschutz.",
      "CO2 schweigt. Das ist messtechnisch unhöflich, aber dramaturgisch spannend.",
      "Der aktuelle ppm-Zettel liegt vermutlich noch im Bluetooth-Flur.",
    ],
    temperatur: [
      "Temperatur noch ohne Aussage. Das Thermometer prüft angeblich erst die Aktenlage.",
      "Keine neue Temperatur. Die Wärme hat sich für ein stilles Verfahren entschieden.",
      "Thermometer meldet nichts Neues und wirkt dabei verdächtig beschäftigt.",
      "Temperaturstatus unbekannt. Die Wohnung trägt heute Tarnkappe aus Funkstille.",
      "Die Gradzahl ist kurz abwesend und bittet, keine Gerüchte zu verbreiten.",
      "Keine frische Temperatur, nur Raumgefühl mit Fragezeichen.",
    ],
    luftfeuchtigkeit: [
      "Luftfeuchte wartet auf neue Beweise und wirkt dabei erstaunlich bürokratisch.",
      "Feuchtewert fehlt. Das Raumklima hat die Unterlagen noch nicht eingereicht.",
      "Keine neue Luftfeuchte. Der zuständige Messwert ist in der Teeküche verschwunden.",
      "Die Feuchte schweigt. Wahrscheinlich juristisch beraten.",
      "Luftfeuchte ohne Update. Das Diagramm räumt schon mal nervös seine Linien.",
      "Die Messstelle wartet. Die Luft tut so, als sei das Absicht.",
    ],
  },
  trend: {
    co2: {
      steigt: [
        "Tendenz steigt: Der Lüftungsantrag wandert von Entwurf zu EILT.",
        "Tendenz steigt: CO2 schiebt seinen Stuhl näher an den Konferenztisch.",
        "Tendenz steigt: Der Fenstergriff wird aus der Bereitschaft geholt.",
        "Tendenz steigt: Die Luft macht leise Karriere im Verwaltungsapparat.",
        "Tendenz steigt: Das Raumklima bittet um weniger Redebeiträge und mehr Außenluft.",
        "Tendenz steigt: Der Sensor legt den Stempel „bitte lüften“ schon mal quer.",
        "Tendenz steigt: CO2 tut so, als hätte es einen Termin mit der Geschäftsführung.",
        "Tendenz steigt: Aus „passt schon“ wird gerade „wir sollten reden“.",
        "Tendenz steigt: Die Luft schreibt an einer sehr passiv-aggressiven Hausmitteilung.",
        "Tendenz steigt: Das Fenster bekommt in der nächsten Sitzung mehr Redezeit.",
        "Tendenz steigt: Die Raumluft sammelt Argumente für einen kurzen Dienstgang nach draußen.",
        "Tendenz steigt: Noch kein Alarm, aber der Sensor trägt schon ernste Schuhe.",
      ],
      sinkt: [
        "Tendenz sinkt: Das Fenster hat offenbar Überzeugungsarbeit geleistet.",
        "Tendenz sinkt: CO2 packt langsam seine Unterlagen zusammen.",
        "Tendenz sinkt: Die Luft räumt den Sitzungssaal und wirkt erleichtert.",
        "Tendenz sinkt: Der Lüftungsantrag wurde bearbeitet, ausnahmsweise ohne Rückfrage.",
        "Tendenz sinkt: Das Raumklima macht einen Schritt Richtung Anstand.",
        "Tendenz sinkt: Der Sensor nickt vorsichtig, will aber noch nicht zu viel loben.",
        "Tendenz sinkt: Die Wohnung bekommt gerade wieder Gehirnluft.",
        "Tendenz sinkt: CO2 verlässt die Bühne, wenn auch mit Aktenkoffer.",
        "Tendenz sinkt: Der Fenstergriff darf sich für erfolgreiche Außenpolitik feiern.",
        "Tendenz sinkt: Die Luft wirkt, als hätte jemand den Raum auf Werkseinstellung gestellt.",
        "Tendenz sinkt: Das Protokoll notiert „Besserung, bitte nicht sofort wieder ruinieren“.",
        "Tendenz sinkt: Die ppm-Abteilung verliert Einfluss im Innenraumkabinett.",
      ],
      ruhig: [
        "Tendenz ruhig: Die Luft sitzt still da und wartet auf den nächsten Tagesordnungspunkt.",
        "Tendenz ruhig: CO2 bewegt sich kaum und übt Standbild mit Zahlen.",
        "Tendenz ruhig: Der Raum hält die Linie, vermutlich aus Gewohnheit.",
        "Tendenz ruhig: Der Sensor macht keine große Szene, was selten genug ist.",
        "Tendenz ruhig: Alles bleibt im Rahmen, der Rahmen schaut trotzdem streng.",
        "Tendenz ruhig: Die Werte halten Dienst nach Vorschrift.",
        "Tendenz ruhig: Das Fenster bleibt informiert, aber noch nicht alarmiert.",
        "Tendenz ruhig: CO2 steht an der Wand und tut, als sei es Dekoration.",
        "Tendenz ruhig: Der Lagebericht blättert langsam um und findet keine neue Krise.",
        "Tendenz ruhig: Der Raum sagt „weitergehen“, der Sensor schreibt „beobachten“.",
        "Tendenz ruhig: Zahlenbewegung auf Beamtenpuls.",
        "Tendenz ruhig: Die Luft hat heute offenbar keine Lust auf Plot-Twist.",
      ],
    },
    temperatur: {
      steigt: [
        "Tendenz steigt: Die Wohnung entdeckt ihren inneren Heizlüfter.",
        "Tendenz steigt: Das Thermometer klettert mit Verwaltungsentschlossenheit.",
        "Tendenz steigt: Der Raum wärmt vor, ohne zu sagen wofür.",
        "Tendenz steigt: Aus gemütlich wird langsam „wer hat hier Sommer bestellt?“",
        "Tendenz steigt: Die Temperatur beantragt mehr Platz im Diagramm.",
        "Tendenz steigt: Der Sensor wischt sich gedanklich die Stirn.",
        "Tendenz steigt: Das Fenster wird vom Deko-Objekt zur Führungskraft.",
        "Tendenz steigt: Die Wohnung nimmt thermisch Anlauf.",
        "Tendenz steigt: Das Raumklima geht von Pullover zu Fragezeichen.",
        "Tendenz steigt: Der Schreibtisch überlegt, ob er Schatten braucht.",
        "Tendenz steigt: Die Gradzahl macht auf Karriereleiter.",
        "Tendenz steigt: Noch kein Backofen, aber die Bewerbung liegt im Entwurf.",
      ],
      sinkt: [
        "Tendenz sinkt: Die Wohnung legt die Sonnenbrille zurück in die Schublade.",
        "Tendenz sinkt: Das Thermometer tritt geordnet den Rückzug an.",
        "Tendenz sinkt: Der Raum findet wieder zu seriöser Betriebstemperatur.",
        "Tendenz sinkt: Die Wärme räumt den Besprechungsraum.",
        "Tendenz sinkt: Das Fenster hat offenbar diplomatisch verhandelt.",
        "Tendenz sinkt: Der Sensor wirkt erleichtert, aber nicht übermütig.",
        "Tendenz sinkt: Aus Sommermodus wird wieder Arbeitszimmer mit Restwürde.",
        "Tendenz sinkt: Die Gradzahl macht einen Schritt weg vom Drama.",
        "Tendenz sinkt: Der Raum nimmt thermisch den Fuß vom Gas.",
        "Tendenz sinkt: Das Klima sortiert sich Richtung vernünftig.",
        "Tendenz sinkt: Die Wohnung atmet kurz kühl durch.",
        "Tendenz sinkt: Die Heizung bleibt trotzdem erst einmal in der Personalakte.",
      ],
      ruhig: [
        "Tendenz ruhig: Die Temperatur hält still und tut sehr professionell.",
        "Tendenz ruhig: Thermisch passiert gerade Verwaltung.",
        "Tendenz ruhig: Das Thermometer steht stramm und meldet nichts Neues.",
        "Tendenz ruhig: Die Gradzahl hat einen Parkplatz gefunden.",
        "Tendenz ruhig: Der Raum bleibt bei seiner Aussage.",
        "Tendenz ruhig: Keine thermische Handlung, nur solide Zahlenhaltung.",
        "Tendenz ruhig: Das Klima zeigt beeindruckende Sitzfleisch-Kompetenz.",
        "Tendenz ruhig: Die Temperatur wirkt, als hätte sie einen Vertrag unterschrieben.",
        "Tendenz ruhig: Alles bleibt da, wo es eben noch war.",
        "Tendenz ruhig: Das Thermometer macht heute Innendienst.",
        "Tendenz ruhig: Die Wohnung lässt die Temperatur im Standgas laufen.",
        "Tendenz ruhig: Keine große Szene, nur Gradzahl mit Klemmbrett.",
      ],
    },
    luftfeuchte: {
      steigt: [
        "Tendenz steigt: Die Luft zieht sich langsam eine zweite Schicht an.",
        "Tendenz steigt: Feuchte meldet sich selbstbewusst zu Wort.",
        "Tendenz steigt: Das Raumklima wird weicher und schaut dabei unschuldig.",
        "Tendenz steigt: Die Luft reicht vorsorglich ein Handtuch durch den Dienstweg.",
        "Tendenz steigt: Aus trockenem Protokoll wird langsam feuchte Ausschusssitzung.",
        "Tendenz steigt: Die Feuchte beantragt mehr Sichtbarkeit im Organigramm.",
        "Tendenz steigt: Der Sensor schaut auf die Wand und sagt erst einmal nichts.",
        "Tendenz steigt: Die Luft legt die trockene Krawatte ab.",
        "Tendenz steigt: Das Raumklima übt dezentes Wellness-Flair.",
        "Tendenz steigt: Noch kein Waschküchenantrag, aber die Vorlage ist vorbereitet.",
        "Tendenz steigt: Die Feuchte nimmt den Dienstweg über die Stirn.",
        "Tendenz steigt: Das Fenster wird als Mediator vorgeschlagen.",
      ],
      sinkt: [
        "Tendenz sinkt: Die Feuchte packt die Akten und verlässt den Raum geordnet.",
        "Tendenz sinkt: Das Raumklima trocknet seine Argumente.",
        "Tendenz sinkt: Die Luft wird sachlicher, fast schon trockenhumorig.",
        "Tendenz sinkt: Feuchte zieht sich aus der ersten Reihe zurück.",
        "Tendenz sinkt: Das Fenster hat offenbar diskret verhandelt.",
        "Tendenz sinkt: Die Messstelle notiert „weniger klebrig, mehr Contenance“.",
        "Tendenz sinkt: Die Luft macht einen Schritt Richtung Papierform.",
        "Tendenz sinkt: Das Raumklima hört auf, Wellness zu spielen.",
        "Tendenz sinkt: Die Feuchte verliert Mandate im Innenraumparlament.",
        "Tendenz sinkt: Das Protokoll trocknet schneller als erwartet.",
        "Tendenz sinkt: Die Wohnung stellt von Dampfbad auf Aktenablage zurück.",
        "Tendenz sinkt: Der Sensor wirkt, als hätte jemand den Nebensatz gelüftet.",
      ],
      ruhig: [
        "Tendenz ruhig: Die Feuchte sitzt da und sortiert Büroklammern.",
        "Tendenz ruhig: Keine Bewegung, nur Luft mit Verwaltungshaltung.",
        "Tendenz ruhig: Der Wert hält still und möchte dafür gelobt werden.",
        "Tendenz ruhig: Die Luftfeuchte bleibt bei ihrer Aussage.",
        "Tendenz ruhig: Raumklima im Wartemodus, aber mit Formular.",
        "Tendenz ruhig: Die Feuchte hat einen stabilen Parkplatz gefunden.",
        "Tendenz ruhig: Das Diagramm bekommt keine neue Ausrede.",
        "Tendenz ruhig: Die Messstelle schreibt „unauffällig“ und wirkt stolz.",
        "Tendenz ruhig: Alles klebt weder mehr noch weniger.",
        "Tendenz ruhig: Die Luft verhält sich statistisch höflich.",
        "Tendenz ruhig: Feuchte auf Standby, Aktenzeichen unverändert.",
        "Tendenz ruhig: Der Raum bleibt in seiner Feuchte-Meinung erstaunlich konsequent.",
      ],
    },
  },
};

const tempCo2LageLetzteAuswahl = new Map();
const tempCo2LageSpruchIntervallMillis = 10 * 60 * 1000;
const tempCo2TrendFensterMillis = 15 * 60 * 1000;
const tempCo2TrendSchwellen = {
  co2_ppm: 1,
  temperatur_c: 0.1,
  luftfeuchtigkeit_prozent: 1,
};

const ermittleSpruchIndex = (sprüche, seed) => {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = ((hash << 5) - hash + seed.charCodeAt(index)) | 0;
  }
  return Math.abs(hash) % sprüche.length;
};

const wähleSpruch = (sprüche, seed, kanal) => {
  let spruchIndex = ermittleSpruchIndex(sprüche, seed);
  const letzteAuswahl = tempCo2LageLetzteAuswahl.get(kanal);
  if (sprüche.length > 1 && letzteAuswahl && letzteAuswahl.seed !== seed && letzteAuswahl.spruchIndex === spruchIndex) {
    spruchIndex = (spruchIndex + 1) % sprüche.length;
  }
  tempCo2LageLetzteAuswahl.set(kanal, { seed, spruchIndex });
  return sprüche[spruchIndex];
};

const ermittleLageSeed = (daten, schlüssel, wert, wertSchritt, lageklasse) => {
  const zeitstempel = Date.parse(daten?.empfangen_utc || daten?.zeit_utc || "");
  const zeitfenster = Number.isFinite(zeitstempel)
    ? Math.floor(zeitstempel / tempCo2LageSpruchIntervallMillis)
    : Math.floor(Date.now() / tempCo2LageSpruchIntervallMillis);
  const wertgruppe = Math.round(wert / wertSchritt) * wertSchritt;
  return `${schlüssel}:${lageklasse}:${zeitfenster}:${wertgruppe}`;
};

const tempCo2MesswertZeit = (messwert) => {
  const zeitstempel = Date.parse(messwert?.empfangen_utc || messwert?.zeit_utc || "");
  return Number.isFinite(zeitstempel) ? zeitstempel : null;
};

const findeTempCo2Trendwerte = (daten, fallbackVorwert = null) => {
  const aktuelleZeit = tempCo2MesswertZeit(daten);
  if (aktuelleZeit === null) {
    return fallbackVorwert ? [fallbackVorwert] : [];
  }

  const fensterStart = aktuelleZeit - tempCo2TrendFensterMillis;
  const trendwerte = tempCo2TrendMesswerte
    .map((messwert) => ({ messwert, zeit: tempCo2MesswertZeit(messwert) }))
    .filter((eintrag) => eintrag.zeit !== null && eintrag.zeit >= fensterStart && eintrag.zeit < aktuelleZeit)
    .sort((a, b) => a.zeit - b.zeit);

  if (fallbackVorwert) {
    const fallbackZeit = tempCo2MesswertZeit(fallbackVorwert);
    const istGültigerFallback = fallbackZeit === null || (fallbackZeit >= fensterStart && fallbackZeit < aktuelleZeit);
    const istSchonVorhanden = trendwerte.some((eintrag) => eintrag.messwert.empfangen_utc === fallbackVorwert.empfangen_utc);
    if (istGültigerFallback && !istSchonVorhanden) {
      trendwerte.push({ messwert: fallbackVorwert, zeit: fallbackZeit || aktuelleZeit - 1 });
      trendwerte.sort((a, b) => a.zeit - b.zeit);
    }
  }

  return trendwerte.map((eintrag) => eintrag.messwert);
};

const ermittleTempCo2Trend = (daten, trendwerte, schlüssel) => {
  const aktuellerWert = Number(daten?.[schlüssel]);
  const gültigeTrendwerte = trendwerte
    .map((messwert) => Number(messwert?.[schlüssel]))
    .filter((wert) => Number.isFinite(wert));

  if (!Number.isFinite(aktuellerWert) || gültigeTrendwerte.length === 0) {
    return { richtung: "unbekannt", delta: 0, vorhanden: false };
  }

  const schwelle = tempCo2TrendSchwellen[schlüssel] || 0;
  const referenzWert = gültigeTrendwerte[0];
  const delta = aktuellerWert - referenzWert;
  if (Math.abs(delta) + Number.EPSILON < schwelle) {
    return { richtung: "ruhig", delta, vorhanden: true };
  }

  return {
    richtung: delta > 0 ? "steigt" : "sinkt",
    delta,
    vorhanden: true,
  };
};

const beschreibeTrendLage = (gruppe, trend, seed) => {
  const sprüche = tempCo2LageSprüche.trend[gruppe]?.[trend.richtung];
  if (!sprüche) {
    return "";
  }

  const deltaSeed = `${seed}:trend:${trend.richtung}:${Math.round(Math.abs(trend.delta) * 10)}`;
  return ` ${wähleSpruch(sprüche, deltaSeed, `${gruppe}-trend`)}`;
};

const beschreibeCo2Lage = (wert, daten, trend) => {
  const gerundet = Math.round(wert);
  if (gerundet < 700) {
    const seed = ermittleLageSeed(daten, "co2", gerundet, 25, "frisch");
    return `${gerundet} ppm: ${wähleSpruch(tempCo2LageSprüche.co2.frisch, seed, "co2")}${beschreibeTrendLage("co2", trend, seed)}`;
  }
  if (gerundet < 1000) {
    const seed = ermittleLageSeed(daten, "co2", gerundet, 25, "normal");
    return `${gerundet} ppm: ${wähleSpruch(tempCo2LageSprüche.co2.normal, seed, "co2")}${beschreibeTrendLage("co2", trend, seed)}`;
  }
  if (gerundet < 1400) {
    const seed = ermittleLageSeed(daten, "co2", gerundet, 50, "aufmerksam");
    return `${gerundet} ppm: ${wähleSpruch(tempCo2LageSprüche.co2.aufmerksam, seed, "co2")}${beschreibeTrendLage("co2", trend, seed)}`;
  }
  if (gerundet < 1800) {
    const seed = ermittleLageSeed(daten, "co2", gerundet, 50, "lüften");
    return `${gerundet} ppm: ${wähleSpruch(tempCo2LageSprüche.co2.lüften, seed, "co2")}${beschreibeTrendLage("co2", trend, seed)}`;
  }
  const seed = ermittleLageSeed(daten, "co2", gerundet, 100, "alarm");
  return `${gerundet} ppm: ${wähleSpruch(tempCo2LageSprüche.co2.alarm, seed, "co2")}${beschreibeTrendLage("co2", trend, seed)}`;
};

const beschreibeTemperaturLage = (wert, daten, trend) => {
  const formatiert = formatiereDezimalzahl(wert);
  if (wert < 19) {
    const seed = ermittleLageSeed(daten, "temperatur", wert, 0.5, "kalt");
    return `${formatiert} °C: ${wähleSpruch(tempCo2LageSprüche.temperatur.kalt, seed, "temperatur")}${beschreibeTrendLage("temperatur", trend, seed)}`;
  }
  if (wert < 22) {
    const seed = ermittleLageSeed(daten, "temperatur", wert, 0.5, "neutral");
    return `${formatiert} °C: ${wähleSpruch(tempCo2LageSprüche.temperatur.neutral, seed, "temperatur")}${beschreibeTrendLage("temperatur", trend, seed)}`;
  }
  if (wert < 25) {
    const seed = ermittleLageSeed(daten, "temperatur", wert, 0.5, "warm");
    return `${formatiert} °C: ${wähleSpruch(tempCo2LageSprüche.temperatur.warm, seed, "temperatur")}${beschreibeTrendLage("temperatur", trend, seed)}`;
  }
  if (wert < 28) {
    const seed = ermittleLageSeed(daten, "temperatur", wert, 0.5, "sommer");
    return `${formatiert} °C: ${wähleSpruch(tempCo2LageSprüche.temperatur.sommer, seed, "temperatur")}${beschreibeTrendLage("temperatur", trend, seed)}`;
  }
  const seed = ermittleLageSeed(daten, "temperatur", wert, 0.5, "heiß");
  return `${formatiert} °C: ${wähleSpruch(tempCo2LageSprüche.temperatur.heiß, seed, "temperatur")}${beschreibeTrendLage("temperatur", trend, seed)}`;
};

const beschreibeLuftfeuchteLage = (wert, daten, trend) => {
  const gerundet = Math.round(wert);
  if (gerundet < 35) {
    const seed = ermittleLageSeed(daten, "luftfeuchte", gerundet, 2, "trocken");
    return `${gerundet} % rF: ${wähleSpruch(tempCo2LageSprüche.luftfeuchte.trocken, seed, "luftfeuchte")}${beschreibeTrendLage("luftfeuchte", trend, seed)}`;
  }
  if (gerundet < 45) {
    const seed = ermittleLageSeed(daten, "luftfeuchte", gerundet, 2, "leicht-trocken");
    return `${gerundet} % rF: ${wähleSpruch(tempCo2LageSprüche.luftfeuchte.leichtTrocken, seed, "luftfeuchte")}${beschreibeTrendLage("luftfeuchte", trend, seed)}`;
  }
  if (gerundet <= 60) {
    const seed = ermittleLageSeed(daten, "luftfeuchte", gerundet, 2, "gut");
    return `${gerundet} % rF: ${wähleSpruch(tempCo2LageSprüche.luftfeuchte.gut, seed, "luftfeuchte")}${beschreibeTrendLage("luftfeuchte", trend, seed)}`;
  }
  if (gerundet <= 70) {
    const seed = ermittleLageSeed(daten, "luftfeuchte", gerundet, 2, "feucht");
    return `${gerundet} % rF: ${wähleSpruch(tempCo2LageSprüche.luftfeuchte.feucht, seed, "luftfeuchte")}${beschreibeTrendLage("luftfeuchte", trend, seed)}`;
  }
  const seed = ermittleLageSeed(daten, "luftfeuchte", gerundet, 2, "sehr-feucht");
  return `${gerundet} % rF: ${wähleSpruch(tempCo2LageSprüche.luftfeuchte.sehrFeucht, seed, "luftfeuchte")}${beschreibeTrendLage("luftfeuchte", trend, seed)}`;
};

const aktualisiereLuftlagebericht = (daten, fallbackVorwert = null) => {
  if (!tempCo2LageCo2 || !tempCo2LageTemperatur || !tempCo2LageLuftfeuchtigkeit) {
    return;
  }

  if (!daten || !daten.verfuegbar) {
    const seed = Math.floor(Date.now() / tempCo2LageSpruchIntervallMillis).toString();
    tempCo2LageCo2.textContent = wähleSpruch(tempCo2LageSprüche.offline.co2, `offline-co2:${seed}`, "offline-co2");
    tempCo2LageTemperatur.textContent = wähleSpruch(tempCo2LageSprüche.offline.temperatur, `offline-temperatur:${seed}`, "offline-temperatur");
    tempCo2LageLuftfeuchtigkeit.textContent = wähleSpruch(tempCo2LageSprüche.offline.luftfeuchtigkeit, `offline-luftfeuchte:${seed}`, "offline-luftfeuchte");
    return;
  }

  const trendwerte = findeTempCo2Trendwerte(daten, fallbackVorwert);
  const co2Trend = ermittleTempCo2Trend(daten, trendwerte, "co2_ppm");
  const temperaturTrend = ermittleTempCo2Trend(daten, trendwerte, "temperatur_c");
  const luftfeuchteTrend = ermittleTempCo2Trend(daten, trendwerte, "luftfeuchtigkeit_prozent");

  tempCo2LageCo2.textContent = beschreibeCo2Lage(daten.co2_ppm, daten, co2Trend);
  tempCo2LageTemperatur.textContent = beschreibeTemperaturLage(daten.temperatur_c, daten, temperaturTrend);
  tempCo2LageLuftfeuchtigkeit.textContent = beschreibeLuftfeuchteLage(daten.luftfeuchtigkeit_prozent, daten, luftfeuchteTrend);
};

const versteckeTempCo2 = () => {
  tempCo2AktuelleDaten = null;
  if (tempCo2Anzeige) {
    tempCo2Anzeige.hidden = true;
  }
  if (tempCo2Seitenwerte) {
    tempCo2Seitenwerte.hidden = true;
  }
  if (tempCo2SeitenLeer) {
    tempCo2SeitenLeer.hidden = false;
  }
  aktualisiereLuftlagebericht(null);
};

const zeigeTempCo2Seitenwerte = (daten) => {
  if (
    !tempCo2Seitenwerte ||
    !tempCo2SeitenLeer ||
    !tempCo2SeitenTemperatur ||
    !tempCo2SeitenLuftfeuchtigkeit ||
    !tempCo2SeitenCo2 ||
    !tempCo2SeitenZeit ||
    !tempCo2SeitenDatum
  ) {
    return;
  }

  const messzeit = new Date(daten.empfangen_utc);
  tempCo2SeitenTemperatur.textContent = formatiereDezimalzahl(daten.temperatur_c);
  tempCo2SeitenLuftfeuchtigkeit.textContent = Math.round(daten.luftfeuchtigkeit_prozent).toString();
  tempCo2SeitenCo2.textContent = Math.round(daten.co2_ppm).toString();
  tempCo2SeitenZeit.textContent = new Intl.DateTimeFormat("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(messzeit);
  tempCo2SeitenDatum.textContent = new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(messzeit);
  tempCo2Seitenwerte.hidden = false;
  tempCo2SeitenLeer.hidden = true;
};

const aktualisiereTempCo2 = async () => {
  if (!tempCo2Anzeige || !tempCo2Temperatur || !tempCo2Luftfeuchtigkeit || !tempCo2Co2) {
    return;
  }

  try {
    const antwort = await fetch("/api/tempco2/aktuell", { cache: "no-store" });
    if (!antwort.ok) {
      versteckeTempCo2();
      return;
    }

    const daten = await antwort.json();
    if (!daten.verfuegbar) {
      versteckeTempCo2();
      return;
    }

    const fallbackVorwert = tempCo2AktuelleDaten?.empfangen_utc !== daten.empfangen_utc ? tempCo2AktuelleDaten : null;
    tempCo2AktuelleDaten = daten;
    tempCo2Temperatur.textContent = formatiereDezimalzahl(daten.temperatur_c);
    tempCo2Luftfeuchtigkeit.textContent = Math.round(daten.luftfeuchtigkeit_prozent).toString();
    tempCo2Co2.textContent = Math.round(daten.co2_ppm).toString();
    tempCo2Anzeige.hidden = false;
    zeigeTempCo2Seitenwerte(daten);
    aktualisiereLuftlagebericht(daten, fallbackVorwert);
  } catch {
    versteckeTempCo2();
  }
};

aktualisiereTempCo2();
window.setInterval(aktualisiereTempCo2, 30000);

const tempCo2Serien = [
  {
    schlüssel: "temperatur_c",
    titel: "Temperatur",
    einheit: "°C",
    farbe: "#c9434b",
    skalaUntergrenze: -10,
    skalaObergrenze: 50,
    polsterOhneÄnderung: 1,
    skalenSchritt: 0.5,
    nachkommastellen: 1,
    messbereiche: [
      { typ: "kritisch", minimum: -10, maximum: 18, beschreibung: "zu kühl: unter 18 °C" },
      { typ: "warnung", minimum: 18, maximum: 20, beschreibung: "kühl: 18 bis 20 °C" },
      { typ: "normal", minimum: 20, maximum: 26, beschreibung: "Wohnraum-Wohlfühlbereich: 20 bis 26 °C" },
      { typ: "warnung", minimum: 26, maximum: 30, beschreibung: "warm: 26 bis 30 °C" },
      { typ: "kritisch", minimum: 30, maximum: 50, beschreibung: "heiß: über 30 °C" },
    ],
  },
  {
    schlüssel: "luftfeuchtigkeit_prozent",
    titel: "Luftfeuchte",
    einheit: "% rF",
    farbe: "#2457a6",
    skalaUntergrenze: 0,
    skalaObergrenze: 100,
    polsterOhneÄnderung: 4,
    skalenSchritt: 1,
    nachkommastellen: 0,
    messbereiche: [
      { typ: "kritisch", minimum: 0, maximum: 30, beschreibung: "sehr trocken: unter 30 % rF" },
      { typ: "warnung", minimum: 30, maximum: 40, beschreibung: "trocken: 30 bis 40 % rF" },
      { typ: "normal", minimum: 40, maximum: 60, beschreibung: "schimmelarme Wohlfühlfeuchte: 40 bis 60 % rF" },
      { typ: "warnung", minimum: 60, maximum: 70, beschreibung: "feucht: 60 bis 70 % rF" },
      { typ: "kritisch", minimum: 70, maximum: 100, beschreibung: "sehr feucht: über 70 % rF" },
    ],
  },
  {
    schlüssel: "co2_ppm",
    titel: "CO2",
    einheit: "ppm",
    farbe: "#009f93",
    skalaUntergrenze: 300,
    skalaObergrenze: 3000,
    polsterOhneÄnderung: 100,
    skalenSchritt: 50,
    nachkommastellen: 0,
    messbereiche: [
      { typ: "normal", minimum: 400, maximum: 1000, beschreibung: "hygienisch unbedenklich: 400 bis 1000 ppm" },
      { typ: "warnung", minimum: 1000, maximum: 2000, beschreibung: "hygienisch auffällig: 1000 bis 2000 ppm" },
      { typ: "kritisch", minimum: 2000, maximum: 3000, beschreibung: "hygienisch inakzeptabel: über 2000 ppm" },
    ],
  },
];

const svgNamensraum = "http://www.w3.org/2000/svg";
const tempCo2DiagrammLayout = {
  breite: 760,
  höhe: 430,
  links: 160,
  rechts: 722,
  reihen: [
    { oben: 34, höhe: 76 },
    { oben: 164, höhe: 76 },
    { oben: 294, höhe: 76 },
  ],
  zeitY: 404,
};

const svgElement = (name, attribute = {}, text = "") => {
  const element = document.createElementNS(svgNamensraum, name);
  Object.entries(attribute).forEach(([schlüssel, wert]) => {
    element.setAttribute(schlüssel, wert.toString());
  });
  if (text) {
    element.textContent = text;
  }
  return element;
};

const begrenzeZahl = (wert, minimum, maximum) => Math.min(maximum, Math.max(minimum, wert));

const formatiereMesswert = (wert, serie, mitEinheit = true) => {
  const zahl = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: serie.nachkommastellen,
    maximumFractionDigits: serie.nachkommastellen,
  }).format(wert);
  return mitEinheit ? `${zahl} ${serie.einheit}` : zahl;
};

const formatiereZeitpunktKurz = (zeit) =>
  new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(zeit));

const rundeSkalenwert = (wert, serie, richtung) => {
  const faktor = 1 / serie.skalenSchritt;
  const skaliert = wert * faktor;
  const gerundet = richtung === "ab" ? Math.floor(skaliert) : Math.ceil(skaliert);
  return gerundet / faktor;
};

const berechneSkala = (werte, serie) => {
  const datenMinimum = Math.min(...werte);
  const datenMaximum = Math.max(...werte);
  const abstand = datenMaximum - datenMinimum;
  const polster = abstand > 0 ? Math.max(abstand * 0.22, serie.skalenSchritt) : serie.polsterOhneÄnderung;
  let minimum = rundeSkalenwert(datenMinimum - polster, serie, "ab");
  let maximum = rundeSkalenwert(datenMaximum + polster, serie, "auf");

  minimum = Math.max(serie.skalaUntergrenze, minimum);
  maximum = Math.min(serie.skalaObergrenze, maximum);

  if (maximum <= minimum) {
    minimum = Math.max(serie.skalaUntergrenze, datenMinimum - serie.polsterOhneÄnderung);
    maximum = Math.min(serie.skalaObergrenze, datenMaximum + serie.polsterOhneÄnderung);
  }

  return { minimum, maximum, datenMinimum, datenMaximum };
};

const wertZuY = (wert, skala, reihe) => {
  const begrenzt = begrenzeZahl(wert, skala.minimum, skala.maximum);
  return reihe.oben + reihe.höhe - ((begrenzt - skala.minimum) / (skala.maximum - skala.minimum)) * reihe.höhe;
};

const zeichneMessbereiche = (svg, serie, skala, reihe) => {
  if (!Array.isArray(serie.messbereiche)) {
    return;
  }

  serie.messbereiche.forEach((bereich) => {
    const minimum = Math.max(bereich.minimum, skala.minimum);
    const maximum = Math.min(bereich.maximum, skala.maximum);
    if (maximum <= minimum) {
      return;
    }

    const yOben = wertZuY(maximum, skala, reihe);
    const yUnten = wertZuY(minimum, skala, reihe);
    const höhe = Math.max(1.5, yUnten - yOben);
    const bereichElement = svgElement("rect", {
      class: `tempco2-messbereich tempco2-messbereich--${bereich.typ}`,
      x: tempCo2DiagrammLayout.links,
      y: yOben,
      width: tempCo2DiagrammLayout.rechts - tempCo2DiagrammLayout.links,
      height: höhe,
    });
    bereichElement.append(svgElement("title", {}, `${serie.titel}: ${bereich.beschreibung}`));
    svg.append(bereichElement);
  });
};

const zeitZuX = (zeit, start, ende) => {
  const links = tempCo2DiagrammLayout.links;
  const breite = tempCo2DiagrammLayout.rechts - tempCo2DiagrammLayout.links;
  if (ende <= start) {
    return links + breite / 2;
  }
  return links + ((zeit - start) / (ende - start)) * breite;
};

const zeichneMesspunkt = (svg, punkt, serie, aktuell = false) => {
  const punktElement = svgElement("circle", {
    class: aktuell ? "tempco2-dot tempco2-dot--aktuell" : "tempco2-dot tempco2-dot--messpunkt",
    cx: punkt.x,
    cy: punkt.y,
    r: aktuell ? 3.2 : 1.7,
    fill: serie.farbe,
  });
  punktElement.append(svgElement("title", {}, `${serie.titel}: ${formatiereMesswert(punkt.wert, serie)} · ${formatiereZeitpunktKurz(punkt.zeit)}`));
  svg.append(punktElement);
};

const reduziereSichtbareMesspunkte = (punkte) => {
  if (punkte.length <= tempCo2MaxSichtbareMesspunkte) {
    return punkte;
  }

  const letzterIndex = punkte.length - 1;
  const schritt = Math.ceil(punkte.length / tempCo2MaxSichtbareMesspunkte);
  return punkte.filter((_, index) => index === 0 || index === letzterIndex || index % schritt === 0);
};

const erstelleTabellenZelle = (zeile, name, text) => {
  const zelle = document.createElement(name);
  zelle.textContent = text;
  zeile.append(zelle);
  return zelle;
};

const aktualisiereTempCo2Wertetabelle = (karte, messpunkte) => {
  const container = karte.querySelector("[data-tempco2-chart-values]");
  if (!container) {
    return;
  }

  container.replaceChildren();
  if (messpunkte.length === 0) {
    return;
  }

  const tabelle = document.createElement("table");
  const kopf = document.createElement("thead");
  const kopfzeile = document.createElement("tr");
  ["Messwert", "Aktuell", "Minimum", "Maximum", "Ø"].forEach((titel) => {
    erstelleTabellenZelle(kopfzeile, "th", titel);
  });
  kopf.append(kopfzeile);
  tabelle.append(kopf);

  const körper = document.createElement("tbody");
  tempCo2Serien.forEach((serie) => {
    const werte = messpunkte
      .map((punkt) => Number(punkt.messwert[serie.schlüssel]))
      .filter((wert) => Number.isFinite(wert));
    if (werte.length === 0) {
      return;
    }

    const letzterWert = werte.at(-1);
    const minimum = Math.min(...werte);
    const maximum = Math.max(...werte);
    const durchschnitt = werte.reduce((summe, wert) => summe + wert, 0) / werte.length;
    const zeile = document.createElement("tr");
    const name = erstelleTabellenZelle(zeile, "th", serie.titel);
    const farbpunkt = document.createElement("span");
    farbpunkt.className = "tempco2-value-color";
    farbpunkt.style.background = serie.farbe;
    name.prepend(farbpunkt);
    erstelleTabellenZelle(zeile, "td", formatiereMesswert(letzterWert, serie));
    erstelleTabellenZelle(zeile, "td", formatiereMesswert(minimum, serie));
    erstelleTabellenZelle(zeile, "td", formatiereMesswert(maximum, serie));
    erstelleTabellenZelle(zeile, "td", formatiereMesswert(durchschnitt, serie));
    körper.append(zeile);
  });
  tabelle.append(körper);
  container.append(tabelle);
};

const zeichneTempCo2Diagramm = (karte, messwerte) => {
  const svg = karte.querySelector("svg");
  const zähler = karte.querySelector("[data-tempco2-chart-count]");
  const leer = karte.querySelector("[data-tempco2-chart-empty]");
  if (!svg || !zähler || !leer) {
    return;
  }

  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${tempCo2DiagrammLayout.breite} ${tempCo2DiagrammLayout.höhe}`);
  zähler.textContent = `${messwerte.length} Werte`;
  leer.hidden = messwerte.length > 0;

  const messpunkte = messwerte
    .map((messwert) => ({
      zeit: new Date(messwert.empfangen_utc).getTime(),
      messwert,
    }))
    .filter((punkt) => Number.isFinite(punkt.zeit))
    .sort((a, b) => a.zeit - b.zeit);
  aktualisiereTempCo2Wertetabelle(karte, messpunkte);

  if (messpunkte.length === 0) {
    return;
  }

  const ersterZeitpunkt = messpunkte[0].zeit;
  const letzterZeitpunkt = messpunkte.at(-1).zeit;
  const zeitPolster = ersterZeitpunkt === letzterZeitpunkt ? 30 * 60 * 1000 : 0;
  const start = ersterZeitpunkt - zeitPolster;
  const ende = letzterZeitpunkt + zeitPolster;

  tempCo2Serien.forEach((serie, index) => {
    const reihe = tempCo2DiagrammLayout.reihen[index];
    const serienpunkte = messpunkte
      .map((punkt) => ({
        zeit: punkt.zeit,
        wert: Number(punkt.messwert[serie.schlüssel]),
      }))
      .filter((punkt) => Number.isFinite(punkt.wert));

    svg.append(svgElement("rect", {
      class: "tempco2-row-bg",
      x: tempCo2DiagrammLayout.links,
      y: reihe.oben,
      width: tempCo2DiagrammLayout.rechts - tempCo2DiagrammLayout.links,
      height: reihe.höhe,
      rx: 6,
      ry: 6,
    }));

    svg.append(svgElement("text", {
      class: "tempco2-row-title",
      x: 18,
      y: reihe.oben + 22,
      fill: serie.farbe,
    }, serie.titel));
    svg.append(svgElement("text", {
      class: "tempco2-row-unit",
      x: 18,
      y: reihe.oben + 44,
    }, serie.einheit));

    if (serienpunkte.length === 0) {
      return;
    }

    const skala = berechneSkala(serienpunkte.map((punkt) => punkt.wert), serie);
    zeichneMessbereiche(svg, serie, skala, reihe);
    const skalenMitte = (skala.minimum + skala.maximum) / 2;
    [
      { wert: skala.maximum, y: reihe.oben },
      { wert: skalenMitte, y: reihe.oben + reihe.höhe / 2 },
      { wert: skala.minimum, y: reihe.oben + reihe.höhe },
    ].forEach((marke) => {
      svg.append(svgElement("line", {
        class: "tempco2-grid",
        x1: tempCo2DiagrammLayout.links,
        y1: marke.y,
        x2: tempCo2DiagrammLayout.rechts,
        y2: marke.y,
      }));
      svg.append(svgElement("text", {
        class: "tempco2-axis",
        x: tempCo2DiagrammLayout.links - 10,
        y: marke.y + 4,
        "text-anchor": "end",
      }, formatiereMesswert(marke.wert, serie, false)));
    });

    const punkte = serienpunkte
      .map((punkt) => ({
        x: zeitZuX(punkt.zeit, start, ende),
        y: wertZuY(punkt.wert, skala, reihe),
        zeit: punkt.zeit,
        wert: punkt.wert,
      }))
      .filter((punkt) => Number.isFinite(punkt.x) && Number.isFinite(punkt.y));

    if (punkte.length === 0) {
      return;
    }

    if (punkte.length > 1) {
      const pfad = punkte.map((punkt, index) => `${index === 0 ? "M" : "L"} ${punkt.x.toFixed(1)} ${punkt.y.toFixed(1)}`).join(" ");
      const linie = svgElement("path", {
        class: "tempco2-line",
        d: pfad,
        stroke: serie.farbe,
      });
      linie.append(svgElement("title", {}, `${serie.titel}: ${punkte.length} Messpunkte im Graph`));
      svg.append(linie);
      reduziereSichtbareMesspunkte(punkte).slice(0, -1).forEach((punkt) => zeichneMesspunkt(svg, punkt, serie));
    } else {
      const punkt = punkte[0];
      zeichneMesspunkt(svg, punkt, serie, true);
    }

    const letzterPunkt = punkte.at(-1);
    if (punkte.length > 1) {
      zeichneMesspunkt(svg, letzterPunkt, serie, true);
    }

    const labelAnker = letzterPunkt.x > tempCo2DiagrammLayout.rechts - 90 ? "end" : "start";
    const labelX = labelAnker === "end" ? letzterPunkt.x - 9 : letzterPunkt.x + 9;
    const labelY = begrenzeZahl(letzterPunkt.y - 9, reihe.oben + 13, reihe.oben + reihe.höhe - 8);
    svg.append(svgElement("text", {
      class: "tempco2-last-value",
      x: labelX,
      y: labelY,
      fill: serie.farbe,
      "text-anchor": labelAnker,
    }, formatiereMesswert(letzterPunkt.wert, serie)));
  });

  const mitte = start + (ende - start) / 2;
  svg.append(svgElement("line", {
    class: "tempco2-time-axis",
    x1: tempCo2DiagrammLayout.links,
    y1: tempCo2DiagrammLayout.zeitY,
    x2: tempCo2DiagrammLayout.rechts,
    y2: tempCo2DiagrammLayout.zeitY,
  }));
  svg.append(svgElement("text", { class: "tempco2-axis", x: tempCo2DiagrammLayout.links, y: tempCo2DiagrammLayout.zeitY + 20 }, formatiereZeitpunktKurz(start)));
  svg.append(svgElement("text", { class: "tempco2-axis", x: (tempCo2DiagrammLayout.links + tempCo2DiagrammLayout.rechts) / 2, y: tempCo2DiagrammLayout.zeitY + 20, "text-anchor": "middle" }, formatiereZeitpunktKurz(mitte)));
  svg.append(svgElement("text", { class: "tempco2-axis", x: tempCo2DiagrammLayout.rechts, y: tempCo2DiagrammLayout.zeitY + 20, "text-anchor": "end" }, formatiereZeitpunktKurz(ende)));
};

const findeAktivesTempCo2Diagramm = () =>
  Array.from(tempCo2Diagramme).find((karte) => !karte.hidden) || tempCo2Diagramme[0] || null;

async function ladeTempCo2Diagramm(karte, optionen = {}) {
  if (!(karte instanceof HTMLElement)) {
    return;
  }

  const zeitraum = karte.getAttribute("data-tempco2-chart");
  if (!zeitraum) {
    return;
  }

  const status = tempCo2DiagrammStatus.get(zeitraum) || {};
  const jetzt = Date.now();
  const darfCacheNutzen = !optionen.erzwingen && status.geladenUm && jetzt - status.geladenUm < tempCo2DiagrammCacheMillis;
  if (darfCacheNutzen && Array.isArray(status.messwerte)) {
    if (!karte.dataset.tempco2Gezeichnet) {
      zeichneTempCo2Diagramm(karte, status.messwerte);
      karte.dataset.tempco2Gezeichnet = "true";
    }
    return;
  }

  if (status.wirdGeladen) {
    return status.wirdGeladen;
  }

  const ladevorgang = (async () => {
    const zähler = karte.querySelector("[data-tempco2-chart-count]");
    if (zähler && !Array.isArray(status.messwerte)) {
      zähler.textContent = "lädt ...";
    }

    try {
      const antwort = await fetch(`/api/tempco2/historie?zeitraum=${encodeURIComponent(zeitraum)}`, { cache: "no-store" });
      const daten = antwort.ok ? await antwort.json() : {};
      const messwerte = Array.isArray(daten.messwerte) ? daten.messwerte : [];

      tempCo2DiagrammStatus.set(zeitraum, {
        messwerte,
        geladenUm: Date.now(),
        wirdGeladen: null,
      });

      if (zeitraum === "tag") {
        tempCo2TrendMesswerte = messwerte;
        if (tempCo2AktuelleDaten) {
          aktualisiereLuftlagebericht(tempCo2AktuelleDaten);
        }
      }

      zeichneTempCo2Diagramm(karte, messwerte);
      karte.dataset.tempco2Gezeichnet = "true";
    } catch {
      tempCo2DiagrammStatus.set(zeitraum, {
        messwerte: [],
        geladenUm: Date.now(),
        wirdGeladen: null,
      });
      zeichneTempCo2Diagramm(karte, []);
      karte.dataset.tempco2Gezeichnet = "true";
    }
  })();

  tempCo2DiagrammStatus.set(zeitraum, {
    ...status,
    wirdGeladen: ladevorgang,
  });
  return ladevorgang;
}

const ladeAktivesTempCo2Diagramm = () => ladeTempCo2Diagramm(findeAktivesTempCo2Diagramm(), { erzwingen: true });

if (tempCo2Diagramme.length > 0) {
  ladeAktivesTempCo2Diagramm();
  window.setInterval(ladeAktivesTempCo2Diagramm, 60000);
}

const revealTargets = document.querySelectorAll(".reveal");

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "0px 0px -4% 0px", threshold: 0.08 },
  );

  revealTargets.forEach((target) => observer.observe(target));
} else {
  revealTargets.forEach((target) => target.classList.add("is-visible"));
}
