// Génère presentation/Expose_Groupe7.pptx — support de l'exposé oral du Groupe 7.
//
//   node presentation/generer_presentation.js
//
// pptxgenjs est installé dans presentation/_build/node_modules (npm install pptxgenjs@3.12.0).
// Tous les chiffres viennent de simulation/02_simulation_projet/rapport/rapport_simulation.html,
// des journaux simulation/02_simulation_projet/resultats/*.log, de simulation/03_contiki_ng/README.md
// (§ 6), de architecture/plan_implantation.html et de materiel/README.md.
// Les champs entre crochets ([Membres…], [date…]) sont à compléter.

const path = require("path");
const BUILD = path.join(__dirname, "_build");
const pptxgen = require(require.resolve("pptxgenjs", { paths: [BUILD] }));
const { applyTheme } = require(path.join(BUILD, "apply_theme.js"));

const ROOT = path.join(__dirname, "..");
const SORTIE = path.join(__dirname, "Expose_Groupe7.pptx");
const IMG = {
  plan: path.join(ROOT, "architecture", "plan_implantation.png"), // 2880 × 1740
  topo: path.join(ROOT, "simulation", "02_simulation_projet", "rapport", "figures", "topologie.png"), // 1827 × 696
  t2: path.join(ROOT, "simulation", "02_simulation_projet", "rapport", "figures", "t2_temperatures.png"), // 1827 × 634
  // presentation/images : illustrations générées (Flow) et photos Wikimedia Commons, voir images/CREDITS.md
  usine: path.join(__dirname, "images", "usine.jpg"), // 1300 × 1741
  surchauffe: path.join(__dirname, "images", "surchauffe.jpg"), // 16:9
  convoyeur: path.join(__dirname, "images", "convoyeur.jpg"), // 16:9
  intrusion: path.join(__dirname, "images", "intrusion.jpg"), // 16:9
  esp32: path.join(__dirname, "images", "esp32.jpg"), // 900 × 703
  ds18b20: path.join(__dirname, "images", "ds18b20.jpg"), // 4:3
  thermocouple: path.join(__dirname, "images", "thermocouple_k.jpg"), // 4:3
  rpi: path.join(__dirname, "images", "raspberry_pi4.jpg"), // 3:2
};

// ------------------------------------------------------------------ texte de la page de titre
const MEMBRES = ["KIDJE Fortunatus", "MOUZOUN Prudence", "VOGNITO Laurent", "OGOUNCHI Nelson"];
const DATE = "[Date de la soutenance à compléter]";

// ------------------------------------------------------------------ thème : une couleur d'accent
const THEME = {
  name: "Groupe 7",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "17293B", lt1: "FFFFFF", dk2: "17293B", lt2: "F2F5F7",
    accent1: "0E746D", // vert-bleu du plan d'implantation
    accent2: "C63F29", // famille thermique (schémas uniquement)
    accent3: "1F66AE", // famille comptage (schémas uniquement)
    accent4: "7B3FAF", // famille intrusion (schémas uniquement)
    accent5: "DCEEEC", // teinte claire de l'accent (fonds de cartes)
    accent6: "5B6B7B", // texte secondaire
    hlink: "0E746D", folHlink: "0E746D",
  },
};
const H = THEME.colors; // valeurs hexadécimales, pour les options qui n'acceptent pas les couleurs du thème
const BORD = "CBD3DB";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13,333 × 7,5 pouces
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Surveillance d'une ligne de production — Groupe 7";
pres.author = "Groupe 7";
pres.company = "IFRI";
const C = pres.SchemeColor;

const W = 13.333, MX = 0.6, CW = W - 2 * MX; // largeur utile 12,13
const PIED = "Groupe 7 · Surveillance d'une ligne de production";

// ------------------------------------------------------------------ dispositions (layouts)
function dispositionContenu(nom, etiquette, largeurEtiquette) {
  pres.defineSlideMaster({
    title: nom,
    background: { color: H.lt1 },
    margin: [0.5, MX, 0.6, MX],
    objects: [
      { rect: { x: MX, y: 0.32, w: largeurEtiquette, h: 0.32, fill: { color: H.accent5 } } },
      { text: { text: etiquette, options: { x: MX, y: 0.32, w: largeurEtiquette, h: 0.32, fontSize: 12, bold: true, color: H.accent1, align: "center", valign: "middle", margin: 0 } } },
      { text: { text: PIED, options: { x: MX, y: 6.98, w: 8, h: 0.3, fontSize: 12, color: H.accent6, margin: 0, valign: "middle" } } },
      { placeholder: { options: { name: "titre", type: "title", x: MX, y: 0.78, w: CW, h: 0.95, fontSize: 30, bold: true, color: H.dk1, align: "left", valign: "top", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - MX - 0.8, y: 6.98, w: 0.8, h: 0.3, fontSize: 12, color: H.accent6, align: "right", margin: 0 },
  });
}
dispositionContenu("CONTEXTE", "Contexte", 1.3);
dispositionContenu("PARTIE_A", "A · Solution industrielle", 2.55);
dispositionContenu("PARTIE_B", "B · Réalisation", 1.75);
dispositionContenu("BILAN", "Bilan", 1.0);
pres.defineSlideMaster({ title: "TITRE", background: { color: H.lt1 }, objects: [] });

// ------------------------------------------------------------------ petits outils de dessin
// Espace insécable entre un nombre et son unité, pour ne jamais couper « 0,87 | s ».
const nb = (s) => s.replace(/(\d) (\d{3})/g, "$1 $2").replace(/(\d) (s|ms|°C|%|m|min|kbit\/s|pièces)\b/g, "$1 $2");
const fix = (t) => (typeof t === "string" ? nb(t) : t.map((r) => ({ ...r, text: nb(r.text) })));

function texte(s, t, o) {
  s.addText(fix(t), Object.assign({ isTextBox: true, margin: 0, fontSize: 18, color: C.text1, valign: "top" }, o));
}
function titre(s, t) { s.addText(nb(t), { placeholder: "titre" }); }
function fond(s, x, y, w, h, couleur) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: couleur || C.background2 }, line: { color: couleur || C.background2, width: 0 } });
}
function cadre(s, x, y, w, h, o = {}) {
  s.addShape(o.arrondi ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE, {
    x, y, w, h, rectRadius: o.arrondi ? 0.08 : undefined,
    fill: { color: o.fill || C.background1 }, line: { color: o.line || BORD, width: o.epaisseur || 1 },
  });
}
// Boîte de schéma : un intitulé en gras et une ligne de détail.
function boite(s, x, y, w, h, intitule, detail, o = {}) {
  cadre(s, x, y, w, h, { fill: o.fill, line: o.line, arrondi: true, epaisseur: o.epaisseur });
  const runs = [{ text: intitule, options: { bold: true, fontSize: o.taille || 18, color: o.couleur || C.text1, breakLine: !!detail } }];
  if (detail) runs.push({ text: detail, options: { fontSize: o.tailleDetail || 14, color: o.couleurDetail || C.accent6 } });
  texte(s, runs, { x: x + 0.1, y, w: w - 0.2, h, align: "center", valign: "middle", paraSpaceAfter: 2 });
}
function fleche(s, x1, y1, x2, y2, o = {}) {
  s.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1,
    line: { color: o.couleur || H.dk1, width: o.epaisseur || 1.5, endArrowType: "triangle", dashType: o.tirets ? "dash" : "solid" },
  });
}
// Symboles du plan : rond = thermique, carré = comptage, losange = intrusion, GW = passerelle.
const FAMILLE = {
  T: { forme: "OVAL", couleur: H.accent2 },
  C: { forme: "RECTANGLE", couleur: H.accent3 },
  P: { forme: "DIAMOND", couleur: H.accent4 },
  GW: { forme: "ROUNDED_RECTANGLE", couleur: H.accent1 },
};
function symbole(s, fam, x, y, d, lettre) {
  const f = FAMILLE[fam];
  const larg = fam === "GW" ? d * 1.5 : d;
  s.addShape(pres.shapes[f.forme], { x, y, w: larg, h: d, fill: { color: f.couleur }, line: { color: f.couleur, width: 0 }, rectRadius: fam === "GW" ? 0.06 : undefined });
  texte(s, lettre || fam, { x, y, w: larg, h: d, fontSize: d > 0.45 ? 14 : 11, bold: true, color: C.background1, align: "center", valign: "middle" });
}
function image(s, chemin, x, y, w, ratio) {
  s.addImage({ path: chemin, x, y, w, h: w / ratio });
}
// Tableau sobre : en-tête sur fond d'accent, lignes séparées par un filet.
function tableau(s, entete, lignes, o) {
  const taille = o.taille || 16;
  const rows = [entete.map((t) => ({ text: nb(t), options: { bold: true, color: "FFFFFF", fill: { color: H.accent1 } } }))];
  lignes.forEach((l, i) => rows.push(l.map((cell, j) => {
    const c = typeof cell === "string" ? { text: cell, options: {} } : cell;
    return { text: nb(c.text), options: Object.assign({ color: H.dk1, fill: { color: i % 2 ? H.lt2 : "FFFFFF" }, bold: j === 0 }, c.options) };
  })));
  s.addTable(rows, {
    x: o.x, y: o.y, w: o.w, colW: o.colW, rowH: o.rowH, fontSize: taille, fontFace: THEME.bodyFontFace,
    valign: "middle", margin: o.marge || [4, 8, 4, 8], border: { type: "solid", pt: 0.75, color: BORD },
  });
}
function diapo(disposition) { return pres.addSlide({ masterName: disposition }); }

// ============================================================================ 1. Titre
{
  const s = diapo("TITRE");
  // Illustration pleine hauteur à droite (ligne de production avec ses boîtiers capteurs).
  const wI = 7.5 * 1300 / 1741; // 5,6
  s.addImage({ path: IMG.usine, x: W - wI, y: 0, w: wI, h: 7.5, altText: "Ligne de production équipée de boîtiers capteurs sans fil" });
  const wG = W - wI - MX - 0.5;
  texte(s, "IFRI · Réseaux de capteurs sans fil & IoT", { x: MX, y: 0.9, w: wG, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  texte(s, "Surveillance d'une ligne de production industrielle", { x: MX, y: 1.4, w: wG, h: 1.7, fontSize: 40, bold: true, valign: "top" });
  texte(s, "Température des machines, comptage des pièces, détection d'intrusion et alertes centralisées",
    { x: MX, y: 3.15, w: wG, h: 0.9, fontSize: 20, color: C.accent6 });
  texte(s, "Groupe 7", { x: MX, y: 4.35, w: wG, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  MEMBRES.forEach((m, i) => texte(s, m, { x: MX + (i % 2) * 3.3, y: 4.8 + Math.floor(i / 2) * 0.42, w: 3.2, h: 0.4, fontSize: 18 }));
  texte(s, [
    { text: "Enseignante : Dr Ida Tognisse", options: { breakLine: true } },
    { text: DATE },
  ], { x: MX, y: 5.85, w: wG, h: 0.85, fontSize: 16, color: C.accent6, paraSpaceAfter: 4 });
  s.addNotes("Bonjour. Nous sommes le Groupe 7 et nous présentons notre projet de réseau de capteurs : la surveillance d'une ligne de production industrielle. " +
    "Le système surveille la température des trois machines, compte les pièces à la sortie de chaque poste, détecte les intrusions hors des heures de travail et centralise les alertes. " +
    "Il repose sur neuf nœuds capteurs, trois de chaque famille, et une passerelle. " +
    "L'exposé a deux parties : d'abord la solution qu'il faudrait installer dans une vraie usine, puis ce que nous avons réellement réalisé, en simulation et sur un prototype.");
}

// ============================================================================ 2. Contexte
{
  const s = diapo("CONTEXTE");
  titre(s, "Trois risques à surveiller en continu sur la ligne de production");
  texte(s, "Usine de 50 × 30 m · réception → M1 découpe → M2 presse → M3 four → expédition",
    { x: MX, y: 1.8, w: CW, h: 0.4, fontSize: 18, color: C.accent6 });

  const risques = [
    ["T", IMG.surchauffe, "Surchauffe", "Une machine qui chauffe trop s'abîme ou s'arrête : il faut alerter avant la panne."],
    ["C", IMG.convoyeur, "Pièces perdues", "Si C1 compte plus que C2, des pièces se perdent ou partent au rebut entre M1 et M2."],
    ["P", IMG.intrusion, "Intrusion de nuit", "Hors des heures de travail, une présence près d'une porte doit déclencher une alerte et un buzzer."],
  ];
  const wR = 3.85, gR = (CW - 3 * wR) / 2, yR = 2.4, hR = 4.35, hImg = wR * 9 / 16;
  risques.forEach(([fam, img, tit, corps], i) => {
    const x = MX + i * (wR + gR);
    fond(s, x, yR, wR, hR);
    s.addImage({ path: img, x, y: yR, w: wR, h: hImg, altText: tit });
    symbole(s, fam, x + 0.3, yR + hImg + 0.3, 0.3, " ");
    texte(s, tit, { x: x + 0.75, y: yR + hImg + 0.22, w: wR - 0.95, h: 0.45, fontSize: 20, bold: true, valign: "middle" });
    texte(s, corps, { x: x + 0.3, y: yR + hImg + 0.8, w: wR - 0.55, h: 1.3, fontSize: 18 });
  });
  s.addNotes("Notre usine fait 50 mètres sur 30 et compte huit zones. La ligne de production enchaîne trois machines : la découpe M1, la presse M2 et le four M3. " +
    "Trois risques justifient une surveillance continue. D'abord la surchauffe : une machine qui chauffe trop s'abîme, il faut prévenir avant la casse. " +
    "Ensuite les pièces perdues : en comptant les pièces à la sortie de chaque poste, on voit tout de suite si des pièces disparaissent entre deux machines. " +
    "Enfin l'intrusion : la nuit, une présence près des portes doit déclencher une alerte et un buzzer.");
}

// ============================================================================ 3. Besoins et exigences
{
  const s = diapo("CONTEXTE");
  titre(s, "4 besoins à couvrir et 3 exigences non fonctionnelles retenues");
  tableau(s, ["Besoin", "Exigences fonctionnelles vérifiées"], [
    ["B1 · Température de chaque machine, seuil propre", "EF1 : une mesure toutes les 30 s ± 2 s, précision ± 1 °C\nEF2 : alerte dès que le seuil est dépassé"],
    ["B2 · Comptage des pièces par poste", "EF5 : 100 pièces → compteur = 100, conservé après un redémarrage"],
    ["B3 · Données centralisées", "Toutes les mesures arrivent au serveur (taux de livraison)"],
    ["B4 · Intrusion hors 08h–18h", "EF6 : présence la nuit → alerte en moins de 5 s"],
  ], { x: MX, y: 1.95, w: 7.45, colW: [3.1, 4.35], rowH: [0.5, 1.15, 0.95, 0.95, 0.95], taille: 16 });

  const xE = 8.45, wE = W - MX - xE;
  texte(s, "Exigences non fonctionnelles retenues", { x: xE, y: 1.95, w: wE, h: 0.4, fontSize: 16, bold: true, color: C.accent6 });
  [["ENF1", "Latence < 10 s", "de la mesure à l'alerte (cible 5 s pour une surchauffe)"],
    ["ENF6", "Messages authentifiés", "un faux nœud est rejeté par la passerelle"],
    ["ENF8", "Un nœud tombe, le reste continue", "on peut retirer un nœud défaillant"]]
    .forEach(([code, tit, detail], i) => {
      const y = 2.45 + i * 1.4;
      fond(s, xE, y, wE, 1.25, C.accent5);
      texte(s, code, { x: xE + 0.25, y: y + 0.2, w: 0.9, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
      texte(s, [{ text: tit, options: { bold: true, breakLine: true } }, { text: detail, options: { fontSize: 15, color: C.accent6 } }],
        { x: xE + 1.15, y: y + 0.17, w: wE - 1.35, h: 0.95, fontSize: 18 });
    });
  s.addNotes("Le cahier des charges exprime quatre besoins. B1 : suivre la température de chaque machine avec son propre seuil ; les exigences EF1 et EF2 demandent une mesure toutes les 30 secondes et une alerte dès le dépassement. " +
    "B2 : compter les pièces de chaque poste ; EF5 demande que 100 pièces donnent un compteur de 100, même après un redémarrage. B3 : centraliser les données. B4 : détecter les intrusions la nuit ; EF6 demande une alerte en moins de 5 secondes. " +
    "Parmi les exigences non fonctionnelles, nous en avons retenu trois, que l'on peut vérifier par un test : ENF1, la latence de moins de 10 secondes ; ENF6, l'authentification des messages ; ENF8, la tolérance à la panne d'un nœud.");
}

// ============================================================================ 4. Architecture cible
{
  const s = diapo("PARTIE_A");
  titre(s, "Chaque mesure doit aller du capteur à l'alerte en moins de 10 s");
  const etapes = [
    ["Capteurs", "DS18B20 · type K\nbarrière IR · PIR"],
    ["Nœud ESP32", "mesure / 30 s\n→ JSON"],
    ["Point d'accès", "Wi-Fi 2,4 GHz\nau plafond du hall"],
    ["Raspberry Pi 4", "Mosquitto\nNode-RED\nInfluxDB · Grafana"],
    ["Alertes et écrans", "e-mail · SMS\nécrans E1 et E2"],
  ];
  const liens = ["GPIO", "Wi-Fi", "Ethernet", "HTTP\nSMTP"];
  const wB = 1.9, g = (CW - 5 * wB) / 4, yB = 2.0, hB = 1.45;
  etapes.forEach(([a, b], i) => {
    const x = MX + i * (wB + g);
    const pi = i === 3;
    boite(s, x, yB, wB, hB, a, b, { fill: pi ? C.accent5 : C.background1, line: pi ? H.accent1 : BORD, taille: 17, tailleDetail: 14 });
    if (i < 4) {
      fleche(s, x + wB + 0.05, yB + hB / 2, x + wB + g - 0.05, yB + hB / 2);
      texte(s, liens[i], { x: x + wB - 0.25, y: yB + hB / 2 + 0.08, w: g + 0.5, h: 0.45, fontSize: 12, color: C.accent6, align: "center" });
    }
  });

  // Budget de latence d'ENF1, à l'échelle.
  const yL = 4.15;
  texte(s, "Budget de latence d'ENF1 (total < 10 s, à l'échelle)", { x: MX, y: yL, w: CW, h: 0.4, fontSize: 18, bold: true });
  const seg = [[1, "< 1 s", "capteur → MQTT"], [1, "< 1 s", "nœud → AP → passerelle"], [3, "< 3 s", "passerelle → serveur"], [3, "< 3 s", "serveur → alerte"], [2, "< 2 s", "alerte → utilisateur"]];
  let x = MX;
  seg.forEach(([d, v, lib], i) => {
    const w = (CW * d) / 10;
    s.addShape(pres.shapes.RECTANGLE, { x, y: yL + 0.55, w, h: 0.55, fill: { color: i % 2 ? H.accent1 : "0A5A55" }, line: { color: "FFFFFF", width: 1.5 } });
    texte(s, v, { x, y: yL + 0.55, w, h: 0.55, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle" });
    texte(s, lib, { x: x + 0.03, y: yL + 1.18, w: w - 0.06, h: 0.55, fontSize: 13, color: C.accent6, align: "center" });
    x += w;
  });
  texte(s, "Ici passerelle et serveur sont le même Raspberry Pi : le segment de 3 s devient presque nul.",
    { x: MX, y: 6.15, w: CW, h: 0.4, fontSize: 18 });
  s.addNotes("Voici la solution que nous proposons pour une vraie usine. Le capteur est lu par un nœud ESP32, qui envoie toutes les 30 secondes un message JSON par Wi-Fi au point d'accès placé au plafond du hall. " +
    "Le point d'accès est câblé en Ethernet au Raspberry Pi 4 du local technique. Il héberge Mosquitto, le broker MQTT, Node-RED, qui décide des alertes, InfluxDB pour l'historique et Grafana pour le tableau de bord. " +
    "Les alertes partent par e-mail et par SMS et s'affichent sur les écrans E1 et E2. " +
    "La barre du bas répartit les 10 secondes d'ENF1 : 1 seconde jusqu'au broker, 1 jusqu'à la passerelle, 3, 3 et 2 pour la suite. Comme passerelle et serveur sont la même machine, il reste une bonne marge sous la cible de 5 secondes.");
}

// ============================================================================ 5. Plan d'implantation
{
  const s = diapo("PARTIE_A");
  titre(s, "9 nœuds et une passerelle placés dans les 8 zones de l'usine");
  const wI = 8.15;
  image(s, IMG.plan, MX, 1.9, wI, 2880 / 1740); // hauteur 4,92
  const xT = MX + wI + 0.4, wT = W - MX - xT;
  const points = [
    ["GW", "Point d'accès au centre du plafond : P3, le plus loin, est à 22,7 m"],
    ["T", "T1–T3 sur les machines, C1–C3 en sortie de chaque poste"],
    ["P", "P1–P3 face aux 3 portes, avec un buzzer local"],
    ["GW", "Passerelle en Z3, accessible seulement depuis la salle de contrôle"],
  ];
  points.forEach(([fam, t], i) => {
    const y = 1.95 + i * 1.22;
    if (i === 1) { symbole(s, "T", xT, y + 0.05, 0.3, " "); symbole(s, "C", xT, y + 0.45, 0.3, " "); }
    else symbole(s, fam, xT, y + 0.05, 0.3, " ");
    texte(s, t, { x: xT + 0.55, y, w: wT - 0.55, h: 1.1, fontSize: 18 });
  });
  s.addNotes("Le plan d'implantation place chaque équipement avec ses coordonnées en mètres. Les trois sondes de température sont sur les machines, et les trois barrières de comptage sont à leur sortie, sur le convoyeur. " +
    "Les trois détecteurs de présence font face aux trois ouvertures : l'entrée du personnel et les deux quais. Leur buzzer est commandé par le nœud lui-même, il sonne même si le réseau est coupé. " +
    "Le point d'accès est au centre du plafond : le nœud le plus éloigné, P3, est à 22,7 mètres, sous la portée Wi-Fi de 30 mètres que nous avons retenue. " +
    "La passerelle est dans le local technique Z3, accessible seulement depuis la salle de contrôle. Ces mêmes positions ont été reprises telles quelles dans la simulation.");
}

// ============================================================================ 6. Capteurs et seuils
{
  const s = diapo("PARTIE_A");
  titre(s, "Chaque machine a son capteur et son propre seuil d'alerte");
  const machines = [
    ["T1", "M1 · Découpe", "85 °C", "Sonde DS18B20", IMG.ds18b20],
    ["T2", "M2 · Presse", "90 °C", "Sonde DS18B20", IMG.ds18b20],
    ["T3", "M3 · Four", "220 °C", "Thermocouple K + MAX6675 (DS18B20 limité à 125 °C)", IMG.thermocouple],
  ];
  const wM = 3.85, gM = (CW - 3 * wM) / 2, yM = 1.95, hM = 2.45, wPh = 1.3;
  machines.forEach(([rep, nom, seuil, capteur, photo], i) => {
    const x = MX + i * (wM + gM);
    fond(s, x, yM, wM, hM);
    symbole(s, "T", x + 0.3, yM + 0.3, 0.45, rep);
    texte(s, nom, { x: x + 0.95, y: yM + 0.3, w: wM - 1.2, h: 0.45, fontSize: 20, bold: true, valign: "middle" });
    texte(s, [{ text: "seuil ", options: { fontSize: 16, color: C.accent6 } }, { text: seuil, options: { fontSize: 36, bold: true } }],
      { x: x + 0.3, y: yM + 0.85, w: wM - wPh - 0.5, h: 0.7, valign: "middle" });
    texte(s, capteur, { x: x + 0.3, y: yM + 1.6, w: wM - wPh - 0.5, h: 0.8, fontSize: 16, color: C.accent6 });
    s.addImage({ path: photo, x: x + wM - wPh - 0.2, y: yM + 1.0, w: wPh, h: wPh * 3 / 4, altText: capteur });
  });
  const autres = [
    ["C", "Comptage · C1 à C3", "Barrière IR FC-51 en sortie de chaque machine : une pièce qui coupe le faisceau est une pièce terminée."],
    ["P", "Intrusion · P1 à P3", "Détecteur PIR HC-SR501 (7 m, 120°) et buzzer, armés hors des heures 08h–18h."],
  ];
  const wA = (CW - 0.3) / 2, yA = 4.65, hA = 1.95;
  autres.forEach(([fam, tit, corps], i) => {
    const x = MX + i * (wA + 0.3);
    cadre(s, x, yA, wA, hA);
    symbole(s, fam, x + 0.3, yA + 0.3, 0.45);
    texte(s, tit, { x: x + 0.95, y: yA + 0.3, w: wA - 1.2, h: 0.45, fontSize: 20, bold: true, valign: "middle" });
    texte(s, corps, { x: x + 0.3, y: yA + 0.9, w: wA - 0.6, h: 0.95, fontSize: 18 });
  });
  s.addNotes("Le besoin B1 impose un seuil par machine : 85 degrés pour la découpe, 90 pour la presse et 220 pour le four. " +
    "Pour M1 et M2, une sonde numérique DS18B20 suffit. Le four dépasse sa limite de 125 degrés : il prend donc un thermocouple de type K, lu par un convertisseur MAX6675. " +
    "Pour le comptage, une barrière infrarouge FC-51 est placée à la sortie de chaque machine : chaque pièce qui coupe le faisceau est comptée. " +
    "Pour l'intrusion, un détecteur PIR HC-SR501, qui voit à 7 mètres sur 120 degrés, avec un buzzer. Il n'est armé qu'en dehors des heures de travail, de 18 heures à 8 heures.");
}

// ============================================================================ 7. Réseau et protocoles
{
  const s = diapo("PARTIE_A");
  titre(s, "MQTT pour publier, 802.15.4 multi-saut pour ménager les piles");
  const wG = 5.75;
  texte(s, "Un topic MQTT par nœud", { x: MX, y: 1.95, w: wG, h: 0.4, fontSize: 20, bold: true });
  [["T", "factory/machines/MACHINE_01 … 03"], ["C", "factory/production/POSTE_01 … 03"], ["P", "factory/security/ZONE_01 … 03"]]
    .forEach(([fam, t], i) => {
      const y = 2.5 + i * 0.55;
      symbole(s, fam, MX, y + 0.06, 0.3, " ");
      texte(s, t, { x: MX + 0.5, y, w: wG - 0.5, h: 0.42, fontSize: 18, valign: "middle" });
    });
  fond(s, MX, 4.3, wG, 1.85);
  texte(s, '{"node_id":"MACHINE_03",\n "timestamp":1792512014,\n "temperature_c":73.0,\n "production_count":2,\n "status":"OK"}',
    { x: MX + 0.25, y: 4.42, w: wG - 0.5, h: 1.65, fontSize: 15, valign: "middle" });
  texte(s, "Format JSON du cahier des charges (ligne réelle écrite par la passerelle simulée)", { x: MX, y: 6.22, w: wG, h: 0.5, fontSize: 12, color: C.accent6 });

  const xD = MX + wG + 0.5, wD = W - MX - xD;
  tableau(s, ["", "Wi-Fi 2,4 GHz", "IEEE 802.15.4"], [
    ["Topologie", "étoile autour du point d'accès", "multi-saut : les nœuds relaient"],
    ["Débit", "élevé", "250 kbit/s, assez pour 22 octets"],
    ["Consommation", "élevée", "faible, pensée pour la pile"],
    ["Portée intérieure", "30 m retenus", "≈ 20 m → relais nécessaires"],
  ], { x: xD, y: 1.95, w: wD, colW: [1.75, 2.0, wD - 3.75], rowH: [0.5, 0.85, 0.85, 0.85, 0.85], taille: 16 });
  texte(s, "Les sondes T1–T3 sont sur batterie LiPo : c'est le réseau multi-saut que nous avons simulé.",
    { x: xD, y: 5.95, w: wD, h: 0.75, fontSize: 18 });
  s.addNotes("Chaque nœud publie sur son propre topic MQTT, rangé par famille : machines, production et sécurité. Le message suit le format JSON du cahier des charges ; l'exemple affiché est une vraie ligne produite par notre passerelle simulée. " +
    "Dans l'usine, le Wi-Fi est pratique : le point d'accès existe et le débit est élevé. Mais la radio Wi-Fi consomme beaucoup, ce qui pose problème pour les sondes alimentées par batterie. " +
    "Un réseau IEEE 802.15.4 est conçu pour la basse consommation. Son débit de 250 kilobits par seconde suffit largement pour nos messages, mais sa portée d'environ 20 mètres oblige les nœuds à relayer les messages de leurs voisins : c'est le multi-saut. " +
    "C'est ce réseau multi-saut que nous avons étudié en simulation.");
}

// ============================================================================ 8. Plateforme de supervision
{
  const s = diapo("PARTIE_A");
  titre(s, "Un Raspberry Pi 4 reçoit, analyse, stocke et affiche les mesures");
  const yC = 1.95, hC = 2.25;
  cadre(s, MX, yC, CW, hC, { fill: C.accent5, line: H.accent1, arrondi: true });
  texte(s, "Raspberry Pi 4 · local technique Z3", { x: MX + 0.25, y: yC + 0.12, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.accent1 });
  const logiciels = [["Mosquitto", "broker MQTT, reçoit factory/#"], ["Node-RED", "règles : T > seuil ? → alerte"], ["InfluxDB", "historique de 30 jours"], ["Grafana", "tableau de bord"]];
  const yL = yC + 0.55, hL = 1.45, wPh = hL * 3 / 2; // photo de la carte, au format 3:2
  s.addImage({ path: IMG.rpi, x: MX + 0.25, y: yL, w: wPh, h: hL, altText: "Carte Raspberry Pi 4 Model B" });
  const x0 = MX + 0.25 + wPh + 0.35, wL = 2.05, gL = (MX + CW - 0.25 - x0 - 4 * wL) / 3;
  const cx = [];
  logiciels.forEach(([a, b], i) => {
    const x = x0 + i * (wL + gL);
    cx.push(x + wL / 2);
    boite(s, x, yL, wL, hL, a, b, { taille: 18, tailleDetail: 15 });
    if (i < 3) fleche(s, x + wL + 0.05, yL + hL / 2, x + wL + gL - 0.05, yL + hL / 2);
  });
  const yS = 4.75, hS = 1.5, wS = (CW - 0.6) / 3;
  const sorties = [
    ["Onduleur ≥ 30 min", "passerelle, switch, routeur et point d'accès restent alimentés"],
    ["Alertes e-mail et SMS", "SMTP Gmail · API SMS Orange / MTN, via le routeur 4G / fibre"],
    ["Écrans E1 et E2", "Grafana dans un navigateur : hall et salle de contrôle"],
  ];
  sorties.forEach(([a, b], i) => {
    const x = MX + i * (wS + 0.3);
    boite(s, x, yS, wS, hS, a, b, { taille: 18, tailleDetail: 15 });
  });
  fleche(s, cx[1], yL + hL + 0.05, cx[1], yS - 0.05);
  fleche(s, cx[3], yL + hL + 0.05, cx[3], yS - 0.05);
  s.addNotes("Toute la supervision tient sur un Raspberry Pi 4 placé dans le local technique. Mosquitto reçoit tous les messages des topics factory. " +
    "Node-RED applique les règles, par exemple « la température dépasse le seuil de la machine », et déclenche l'alerte. InfluxDB garde l'historique pendant 30 jours, et Grafana l'affiche. " +
    "Les alertes partent par e-mail et par SMS grâce au routeur 4G ou fibre, et le tableau de bord s'affiche dans un simple navigateur sur l'écran du hall et sur le poste de la salle de contrôle. " +
    "Un onduleur d'au moins 30 minutes d'autonomie garde la passerelle, le switch, le routeur et le point d'accès en marche pendant une coupure de courant.");
}

// ============================================================================ 9. Sécurité et fiabilité
{
  const s = diapo("PARTIE_A");
  titre(s, "En production, on chiffre, on cloisonne et on prévoit les pannes");
  const cartes = [
    ["Chiffrer", "MQTT sur TLS (port 8883)", "un certificat par ESP32 ; sans TLS, les mots de passe circulent en clair"],
    ["Cloisonner", "Un compte et une ACL par nœud", "chaque nœud ne peut publier que sur ses propres topics (ENF6)"],
    ["Détecter", "Testament MQTT (Last Will)", "si un nœud tombe, le broker publie lui-même son absence (ENF8)"],
    ["Ne rien perdre", "Stockage local", "tampon de messages si le broker est injoignable, compteur de pièces en flash"],
  ];
  const wC = (CW - 0.3) / 2, hC = 2.2;
  cartes.forEach(([verbe, tit, corps], i) => {
    const x = MX + (i % 2) * (wC + 0.3), y = 1.95 + Math.floor(i / 2) * (hC + 0.3);
    fond(s, x, y, wC, hC);
    texte(s, verbe.toUpperCase(), { x: x + 0.35, y: y + 0.3, w: wC - 0.7, h: 0.35, fontSize: 14, bold: true, color: C.accent1, charSpacing: 1 });
    texte(s, tit, { x: x + 0.35, y: y + 0.7, w: wC - 0.7, h: 0.45, fontSize: 22, bold: true });
    texte(s, corps, { x: x + 0.35, y: y + 1.25, w: wC - 0.7, h: 0.8, fontSize: 18 });
  });
  s.addNotes("En production, la sécurité et la fiabilité ne sont pas optionnelles. D'abord chiffrer : MQTT doit passer en TLS sur le port 8883, avec un certificat par ESP32, sinon les mots de passe circulent en clair. " +
    "Ensuite cloisonner : chaque nœud a son propre compte et une liste de droits, l'ACL, qui ne l'autorise à publier que sur ses topics. C'est notre réponse à ENF6. " +
    "Pour ENF8, le testament MQTT permet au broker d'annoncer lui-même qu'un nœud a disparu. " +
    "Enfin, rien ne doit se perdre : chaque nœud garde ses messages dans un tampon si le broker est injoignable, et le compteur de pièces est sauvegardé en mémoire flash.");
}

// ============================================================================ 10. Démarche
{
  const s = diapo("PARTIE_B");
  titre(s, "Nous avons validé le système en simulation avant le matériel");
  const etapes = [
    ["Plan d'implantation", "positions x ; y en mètres, réutilisées partout", "fait"],
    ["Simulation TinyOS", "Cooja · 10 nœuds · 8 tests automatiques", "fait"],
    ["Portage Contiki-NG", "mêmes tests, autre OS, routage RPL", "fait"],
    ["Prototype ESP32", "3 cartes et un broker sur un VPS", "montage en cours"],
  ];
  const wE = 2.75, gE = (CW - 4 * wE) / 3, yE = 2.0, hE = 2.6;
  etapes.forEach(([tit, corps, etat], i) => {
    const x = MX + i * (wE + gE);
    cadre(s, x, yE, wE, hE, { arrondi: true });
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: yE + 0.3, w: 0.55, h: 0.55, fill: { color: H.accent1 }, line: { color: H.accent1, width: 0 } });
    texte(s, String(i + 1), { x: x + 0.3, y: yE + 0.3, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
    texte(s, tit, { x: x + 0.3, y: yE + 1.0, w: wE - 0.6, h: 0.45, fontSize: 19, bold: true });
    texte(s, corps, { x: x + 0.3, y: yE + 1.5, w: wE - 0.5, h: 0.75, fontSize: 16, color: C.accent6 });
    const fini = etat === "fait";
    texte(s, etat, { x: x + 0.3, y: yE + 2.18, w: wE - 0.6, h: 0.3, fontSize: 14, bold: true, color: fini ? C.accent1 : C.accent6 });
    if (i < 3) fleche(s, x + wE + 0.06, yE + hE / 2, x + wE + gE - 0.06, yE + hE / 2);
  });
  fond(s, MX, 5.0, CW, 1.45, C.accent5);
  texte(s, [{ text: "Pourquoi simuler d'abord ? ", options: { bold: true } },
    { text: "Cooja émule les cartes de capteurs instruction par instruction : on rejoue chaque scénario de test sans matériel, autant de fois que nécessaire, avec les vraies distances de l'usine." }],
  { x: MX + 0.35, y: 5.0, w: CW - 0.7, h: 1.45, fontSize: 18, valign: "middle" });
  s.addNotes("Passons à ce que nous avons réalisé. Nous avons avancé en quatre étapes. Le plan d'implantation fixe les positions en mètres, qui sont réutilisées dans tous les fichiers. " +
    "Ensuite, une simulation complète sous TinyOS dans le simulateur Cooja : dix nœuds et huit scénarios de test automatiques. Puis nous avons traduit la simulation sous Contiki-NG pour comparer deux systèmes d'exploitation. " +
    "Enfin, le prototype matériel avec trois ESP32 : le code est écrit et compile, le montage est en cours. " +
    "Nous avons commencé par la simulation parce que Cooja émule les cartes au niveau des instructions : on peut rejouer chaque test à l'identique, sans matériel.");
}

// ============================================================================ 11. Simulation : arbre de routage
{
  const s = diapo("PARTIE_B");
  titre(s, "Les 10 cartes du plan forment seules un arbre de routage multi-saut");
  const wI = 11.0;
  image(s, IMG.topo, (W - wI) / 2, 1.85, wI, 1827 / 696); // hauteur 4,19
  texte(s, "Portée radio de 20 m : P1, P2 et P3 ne voient pas la passerelle et passent par un relais (2 sauts). Après le retrait de T1, P1 passe par P2.",
    { x: MX, y: 6.12, w: CW, h: 0.7, fontSize: 18 });
  s.addNotes("Dans Cooja, nous avons placé dix cartes aux coordonnées exactes du plan : la passerelle, numéro 1, trois nœuds thermiques, trois de comptage et trois d'intrusion. Chaque rôle a son propre programme nesC. " +
    "La radio est en IEEE 802.15.4 avec une portée de 20 mètres. Les trois détecteurs de présence sont trop loin de la passerelle : leurs messages passent par un voisin. " +
    "Le protocole CTP de TinyOS construit seul cet arbre : chaque nœud choisit le voisin qui minimise le coût jusqu'à la racine. " +
    "À droite, après le retrait du nœud T1 qui servait de relais, P1 trouve un autre chemin en passant par P2.");
}

// ============================================================================ 12. Tests et résultats chiffrés
{
  const s = diapo("PARTIE_B");
  titre(s, "8 tests automatiques vérifient 15 exigences : toutes sont conformes");
  const ok = { text: "conforme", options: { bold: true, color: H.accent1 } };
  tableau(s, ["Exigence", "Test", "Valeur mesurée (simulation TinyOS)", "Verdict"], [
    ["EF1 · une mesure toutes les 30 s ± 2 s", "T1", "30,00 s sur 174 intervalles", ok],
    ["EF2 + ENF1 · M2 à 95 °C → alerte", "T2", "alerte 0,87 s après la mise à 95 °C", ok],
    ["EF2 · seuil propre à chaque machine", "T2", "four : 185 °C sans alerte, 225 °C → alerte en 0,32 s", ok],
    ["EF5 · 100 pièces → compteur = 100", "T4", "100 / 100 ; 42 pièces restaurées après redémarrage", ok],
    ["EF6 · présence de nuit → alerte", "T5", "0,05 s au pire, buzzer actif ; 0 alerte de jour", ok],
    ["ENF1 · latence capteur → passerelle", "T6", "moyenne 30,4 ms, max 47 ms (360 rapports)", ok],
    ["B3 · taux de livraison", "T6 / T6b", "100 % avec liens parfaits et dégradés", ok],
    ["ENF8 · le relais T1 est retiré", "T9", "8/8 capteurs continuent ; P1 rétabli en 44,0 s", ok],
    ["ENF6 · un intrus sans la clé", "ENF6", "10 rapports rejetés, 0 rapport légitime rejeté", ok],
  ], { x: MX, y: 1.9, w: CW, colW: [4.2, 1.2, 5.3, 1.43], rowH: 0.45, taille: 15 });
  texte(s, "Source : rapport_simulation.html et journaux resultats/*.log (lignes MESURE et VERDICT). Le tableau regroupe les 15 vérifications du rapport.",
    { x: MX, y: 6.55, w: CW, h: 0.3, fontSize: 12, color: C.accent6 });
  s.addNotes("Chaque exigence a son test automatique : un script, exécuté par Cooja, injecte l'événement, mesure le délai avec l'horloge de la simulation et écrit un verdict. " +
    "La période est exactement de 30 secondes. La surchauffe de la presse à 95 degrés déclenche l'alerte en 0,87 seconde, et le four reste à 185 degrés sans fausse alerte. " +
    "Les 100 pièces donnent un compteur de 100, et le compteur survit à un redémarrage. L'intrusion de nuit est signalée en 0,05 seconde au pire. " +
    "La latence moyenne est de 30 millisecondes, aucun message n'est perdu, même avec des liens dégradés. Quand on retire le relais T1, les huit autres capteurs continuent, et l'intrus est entièrement rejeté. " +
    "Les quinze vérifications sont conformes.");
}

// ============================================================================ 13. Résultats marquants
{
  const s = diapo("PARTIE_B");
  titre(s, "Les alertes arrivent en moins d'une seconde, loin de la limite de 10 s");
  const stats = [
    ["0,87 s", "surchauffe de M2 → alerte, pour une limite de 10 s"],
    ["30 ms", "latence moyenne capteur → passerelle (max 47 ms)"],
    ["44 s", "pour rétablir les rapports de P1 après la panne de T1"],
    ["10 / 10", "rapports de l'intrus rejetés par la passerelle"],
  ];
  const wS = 2.85, gS = (CW - 4 * wS) / 3, yS = 1.9, hS = 1.75;
  stats.forEach(([v, lib], i) => {
    const x = MX + i * (wS + gS);
    fond(s, x, yS, wS, hS);
    texte(s, v, { x: x + 0.25, y: yS + 0.15, w: wS - 0.5, h: 0.75, fontSize: 40, bold: true, color: C.accent1, valign: "middle" });
    texte(s, lib, { x: x + 0.25, y: yS + 0.92, w: wS - 0.45, h: 0.75, fontSize: 15 });
  });
  const wI = 8.5;
  image(s, IMG.t2, (W - wI) / 2, 3.88, wI, 1827 / 634); // hauteur 2,95
  s.addNotes("Quatre chiffres résument la simulation. L'alerte de surchauffe arrive 0,87 seconde après la mise à 95 degrés ; seulement 39 millisecondes séparent la détection sur le nœud de l'alerte, le reste est l'attente de la lecture suivante, faite toutes les 2 secondes. " +
    "La latence moyenne entre capteur et passerelle est de 30 millisecondes, très loin du budget d'une seconde. " +
    "Après la panne du relais T1, P1 change de parent en 15 secondes et ses rapports reviennent au bout de 44 secondes, sans en perdre aucun. " +
    "Le graphique montre la presse qui passe à 95 degrés, le triangle marque l'alerte ; à droite, le four tourne à 185 degrés sans alerte, puis alerte à 225.");
}

// ============================================================================ 14. TinyOS ↔ Contiki-NG
{
  const s = diapo("PARTIE_B");
  titre(s, "Sous Contiki-NG, les tests passent et RPL se rétablit plus vite");
  const g = (t) => ({ text: t, options: { bold: true } });
  tableau(s, ["Test", "Exigence", "TinyOS · CTP", "Contiki-NG · RPL + UDP"], [
    ["T1", "période 30 s ± 2 s", "30,00 s", "30,00 s"],
    ["T2", "95 °C → alerte < 10 s", "0,87 s", "0,86 s"],
    ["T4", "100 pièces → 100", "100 / 100", "100 / 100"],
    ["T5", "intrusion de nuit < 5 s", "0,05 s", "0,03 à 0,05 s"],
    ["T6", "latence capteur → passerelle", "moy. 30 ms, max 47 ms", "moy. 50 ms, 95 % < 72 ms *"],
    ["T6 / T6b", "taux de livraison", "100 % / 100 %", "100 % / 100 %"],
    ["T9", "relais T1 retiré", g("rapports de P1 en 44 s"), g("rapports de P1 en 15 s")],
    ["ENF6", "intrus rejeté", "10 rapports rejetés", "96 envois rejetés"],
  ], { x: MX, y: 1.9, w: CW, colW: [1.3, 3.6, 3.3, 3.93], rowH: 0.45, taille: 16 });
  texte(s, "* Maximum de 4,9 s pour le tout premier rapport, le temps que RPL rattache le nœud ; ensuite, aucun rapport ne dépasse 200 ms. " +
    "RPL entre plus lentement dans le réseau, mais son acquittement de bout en bout le fait reconverger plus vite.",
  { x: MX, y: 6.05, w: CW, h: 0.8, fontSize: 15, color: C.accent6 });
  s.addNotes("Nous avons traduit la simulation sous Contiki-NG : même usine, mêmes nœuds, mêmes tests. Seul le système d'exploitation change, avec du C classique au lieu de nesC, et le routage RPL sur IPv6 au lieu de CTP. " +
    "Tous les tests passent. La différence la plus nette est la panne : avec RPL, les rapports de P1 reviennent en 15 secondes au lieu de 44, grâce à l'acquittement de bout en bout renvoyé au bout de 3 secondes. " +
    "En revanche, RPL est plus lent au démarrage : un nœud n'est joignable qu'après un échange avec la racine, ce qui explique le maximum de 4,9 secondes sur le tout premier rapport. " +
    "La latence moyenne est de 50 millisecondes au lieu de 30. Attention : sous Contiki, nous avons utilisé des Cooja motes, qui n'émulent pas la carte, donc la comparaison n'est pas parfaitement stricte.");
}

// ============================================================================ 15. Prototype : schéma et câblage
{
  const s = diapo("PARTIE_B");
  titre(s, "Le prototype relie 3 ESP32 à un broker Mosquitto hébergé sur un VPS");
  const cartes = [
    ["T", "ESP32 n°1 · DHT11", "factory/machines/MACHINE_01"],
    ["C", "ESP32 n°2 · capteur IR", "factory/production/POSTE_01"],
    ["P", "ESP32 n°3 · PIR + buzzer", "factory/security/ZONE_01"],
  ];
  const xN = MX, wN = 3.45, hN = 0.95, yN0 = 1.95, gN = 0.3;
  cartes.forEach(([fam, tit, topic], i) => {
    const y = yN0 + i * (hN + gN);
    cadre(s, xN, y, wN, hN, { arrondi: true });
    symbole(s, fam, xN + 0.2, y + 0.29, 0.38, " ");
    texte(s, [{ text: tit, options: { bold: true, breakLine: true } }, { text: topic, options: { fontSize: 13, color: C.accent6 } }],
      { x: xN + 0.75, y, w: wN - 0.85, h: hN, fontSize: 17, valign: "middle" });
  });
  const yMil = yN0 + (3 * hN + 2 * gN) / 2;
  const xW = 4.55, wW = 1.35;
  boite(s, xW, yN0, wW, 3 * hN + 2 * gN, "Wi-Fi", "2,4 GHz\npuis Internet", { taille: 17, tailleDetail: 14 });
  cartes.forEach((_, i) => fleche(s, xN + wN + 0.05, yN0 + i * (hN + gN) + hN / 2, xW - 0.05, yN0 + i * (hN + gN) + hN / 2));
  const xV = 6.4, wV = 1.95;
  boite(s, xV, yMil - 0.85, wV, 1.7, "VPS", "Mosquitto (MQTT)\ncomptes + ACL", { fill: C.accent5, line: H.accent1, taille: 18, tailleDetail: 14 });
  fleche(s, xW + wW + 0.05, yMil - 0.25, xV - 0.05, yMil - 0.25);
  fleche(s, xV - 0.05, yMil + 0.25, xW + wW + 0.05, yMil + 0.25, { couleur: H.accent6, tirets: true });
  texte(s, "pointillé : commandes\nfactory/cmd/<NODE_ID>", { x: xV - 0.3, y: yMil + 0.95, w: wV + 0.6, h: 0.5, fontSize: 13, color: C.accent6, align: "center" });

  const xT = 8.85, wT = W - MX - xT;
  texte(s, "Câblage", { x: xT, y: 1.95, w: wT, h: 0.4, fontSize: 20, bold: true });
  tableau(s, ["Capteur", "Alim.", "Sortie"], [
    ["DHT11", "3V3", "GPIO 4"],
    ["IR FC-51", "3V3", "GPIO 27"],
    ["PIR HC-SR501", "VIN 5 V", "GPIO 26"],
  ], { x: xT, y: 2.45, w: wT, colW: [1.65, 1.1, wT - 2.75], rowH: 0.5, taille: 16 });
  texte(s, "Tous les GND à la masse. PIR : ~60 s de chauffe au démarrage.", { x: xT, y: 4.55, w: wT, h: 0.5, fontSize: 14, color: C.accent6 });
  const wE = 2.0, hE = wE * 703 / 900;
  s.addImage({ path: IMG.esp32, x: xT + (wT - wE) / 2, y: 6.85 - hE, w: wE, h: hE, altText: "Carte de développement ESP32 (ESP-WROOM-32)" });

  fond(s, MX, 5.75, xT - MX - 0.4, 0.85, C.accent5);
  texte(s, [{ text: "Montage en cours. ", options: { bold: true } }, { text: "Photos du montage et des messages reçus après les essais." }],
    { x: MX + 0.35, y: 5.75, w: xT - MX - 1.1, h: 0.85, fontSize: 18, valign: "middle" });
  s.addNotes("Le prototype matériel reprend un capteur de chaque type : un ESP32 avec un DHT11 pour la température, un avec un capteur infrarouge pour le comptage, et un avec un détecteur PIR et un buzzer pour l'intrusion. " +
    "Les trois cartes se connectent en Wi-Fi 2,4 GHz et publient, via Internet, sur un broker Mosquitto installé sur un VPS. Le VPS joue le rôle de la passerelle. Il peut aussi renvoyer des commandes aux nœuds, par exemple armer le détecteur ou remettre le compteur à zéro. " +
    "Le tableau donne le câblage : attention, le capteur infrarouge est alimenté en 3,3 volts, et le PIR en 5 volts. " +
    "Les trois programmes compilent ; le montage est en cours, et nous ajouterons les photos après les essais.");
}

// ============================================================================ 16. Prototype : couverture des exigences
{
  const s = diapo("PARTIE_B");
  titre(s, "Le prototype couvre les mêmes exigences avec les outils de MQTT");
  tableau(s, ["Exigence", "Mécanisme dans le prototype", "Test prévu → résultat attendu"], [
    ["ENF1", "alertes publiées dès la détection, sans attendre le rapport de 30 s", 'pincer le DHT11 → "status":"ALERTE" immédiat'],
    ["ENF6", "un compte Mosquitto et une ACL par nœud", "mauvais mot de passe → échec (code 5), rien publié"],
    ["ENF8", "testament MQTT (Last Will), keep-alive de 10 s", 'débrancher une carte → "online":false en ~15 s'],
    ["EF5", "compteur de pièces sauvegardé en flash", "10 passages devant l'IR → +10, conservé après reset"],
    ["EF6", "PIR armé hors 08h–18h (ou commande ARME)", 'bouger devant le PIR → "status":"INTRUSION"'],
  ], { x: MX, y: 1.9, w: CW, colW: [1.35, 5.2, 5.58], rowH: [0.5, 0.8, 0.8, 0.8, 0.8, 0.8], taille: 16 });
  texte(s, "Procédure prête (materiel/README.md) · résultats à venir après le montage", { x: MX, y: 6.5, w: CW, h: 0.4, fontSize: 16, bold: true, color: C.accent6 });
  s.addNotes("Avec MQTT, chaque exigence trouve un mécanisme simple. Pour ENF1, les alertes sont publiées dès la détection, sans attendre le rapport périodique. " +
    "Pour ENF6, chaque nœud a son compte et ses droits sur le broker : avec un mauvais mot de passe, la connexion est refusée et rien n'est publié. " +
    "Pour ENF8, le testament MQTT : si on débranche une carte, le broker publie lui-même qu'elle est hors ligne, après environ 15 secondes. " +
    "Le compteur de pièces est sauvegardé en flash, comme en simulation. La colonne de droite décrit les tests que nous allons faire ; nous n'avons pas encore de résultats mesurés sur le matériel.");
}

// ============================================================================ 17. Écarts et limites
{
  const s = diapo("PARTIE_B");
  titre(s, "Nos écarts avec la solution cible sont connus et assumés");
  tableau(s, ["Point", "Solution cible", "Ce que nous avons fait", "Conséquence"], [
    ["Capteur de M1", "DS18B20, seuil 85 °C", "DHT11 (0 à 50 °C) : seuil de démo à 30 °C", "on teste la logique, pas la vraie plage"],
    ["Réseau", "multi-saut basse consommation", "prototype : étoile Wi-Fi vers le VPS", "pas de relais entre nœuds"],
    ["Sécurité", "MQTT sur TLS (port 8883)", "démo sans TLS ; simulation : code FNV-1a sur 16 bits", "pas de chiffrement ni d'anti-rejeu"],
    ["Radio simulée", "murs, évanouissements", "modèle UDGM : disque parfait de 20 m", "T6b dégrade les liens pour compenser en partie"],
    ["Trajet serveur", "passerelle → broker → alerte", "non simulé : seule la partie radio est mesurée", "8 s du budget ENF1 non mesurées"],
  ], { x: MX, y: 1.9, w: CW, colW: [1.95, 3.0, 4.15, 3.03], rowH: [0.5, 0.85, 0.85, 0.85, 0.85, 0.85], taille: 16 });
  s.addNotes("Nous assumons plusieurs écarts. Le DHT11 du prototype ne mesure que jusqu'à 50 degrés : le seuil de 85 degrés est inatteignable, donc la démonstration utilise un seuil de 30 degrés, qu'on atteint en pinçant le capteur. " +
    "Le prototype est une étoile Wi-Fi, sans multi-saut. La démo tourne sans TLS, et l'authentification de la simulation est un code de 16 bits pédagogique, sans protection contre le rejeu. " +
    "Le modèle radio de Cooja est un disque parfait, sans murs ; le test T6b dégrade volontairement les liens pour s'en approcher. " +
    "Enfin, nos latences ne mesurent que le réseau de capteurs : le trajet de la passerelle jusqu'à la notification n'est pas simulé.");
}

// ============================================================================ 18. Ce que nous retenons
{
  const s = diapo("BILAN");
  titre(s, "Nos difficultés nous ont appris à tout vérifier par la mesure");
  const lecons = [
    ["TimerMilli ne compte pas en millisecondes", "Sous TinyOS, TimerMilli compte en 1/1024 s : 30 000 donnait 29,3 s. Une conversion corrige l'écart."],
    ["Écrire en flash peut planter la carte", "Une interruption pendant l'écriture fait planter le MSP430 : on les masque pendant l'écriture (atomic)."],
    ["Un routage se teste en panne", "CTP ne voit la panne qu'en envoyant : un tampon et un réessai évitent toute perte (T9)."],
    ["Deux OS, deux comportements", "RPL s'attache plus lentement mais se rétablit plus vite : seuls des tests identiques permettent de comparer."],
  ];
  const wC = (CW - 0.3) / 2, hC = 2.2;
  lecons.forEach(([tit, corps], i) => {
    const x = MX + (i % 2) * (wC + 0.3), y = 1.95 + Math.floor(i / 2) * (hC + 0.3);
    fond(s, x, y, wC, hC);
    texte(s, tit, { x: x + 0.35, y: y + 0.3, w: wC - 0.7, h: 0.5, fontSize: 21, bold: true });
    texte(s, corps, { x: x + 0.35, y: y + 0.9, w: wC - 0.7, h: 1.15, fontSize: 18 });
  });
  s.addNotes("Ce projet nous a appris surtout à vérifier par la mesure. Premier piège : sous TinyOS, la minuterie dite « milliseconde » compte en réalité en 1/1024 de seconde ; nos rapports partaient toutes les 29,3 secondes au lieu de 30. " +
    "Deuxième piège : écrire en mémoire flash bloque le processeur, et une interruption à ce moment fait planter la carte ; il a fallu masquer les interruptions. " +
    "Troisième : un protocole de routage ne découvre une panne qu'en essayant d'envoyer, d'où le tampon et le réessai. " +
    "Enfin, comparer TinyOS et Contiki-NG n'a de sens qu'avec exactement les mêmes tests, c'est pourquoi nous les avons réutilisés tels quels.");
}

// ============================================================================ 19. Conclusion et perspectives
{
  const s = diapo("BILAN");
  titre(s, "Validé en simulation, le système doit maintenant passer au matériel");
  const wC = (CW - 0.4) / 2, y0 = 1.95;
  texte(s, "Ce qui est acquis", { x: MX, y: y0, w: wC, h: 0.45, fontSize: 20, bold: true, color: C.accent1 });
  [["15 / 15", "exigences vérifiées en simulation TinyOS"], ["2 OS", "mêmes tests au vert sous Contiki-NG"], ["3 ESP32", "programmes qui compilent, broker et ACL configurés"]]
    .forEach(([v, lib], i) => {
      const y = y0 + 0.65 + i * 1.3;
      fond(s, MX, y, wC, 1.1);
      texte(s, v, { x: MX + 0.3, y, w: 2.0, h: 1.1, fontSize: 30, bold: true, color: C.accent1, valign: "middle" });
      texte(s, lib, { x: MX + 2.35, y, w: wC - 2.6, h: 1.1, fontSize: 18, valign: "middle" });
    });
  const xP = MX + wC + 0.4;
  texte(s, "Perspectives", { x: xP, y: y0, w: wC, h: 0.45, fontSize: 20, bold: true, color: C.accent1 });
  texte(s, [
    { text: "Tester les 3 ESP32 et documenter les résultats", options: { bullet: true, breakLine: true } },
    { text: "Activer TLS (port 8883) sur le broker", options: { bullet: true, breakLine: true } },
    { text: "Ajouter Node-RED, InfluxDB et Grafana côté serveur", options: { bullet: true, breakLine: true } },
    { text: "Modèle radio avec les murs du plan (MRM ou DGRM)", options: { bullet: true, breakLine: true } },
    { text: "Heure par NTP et protection contre le rejeu", options: { bullet: true } },
  ], { x: xP, y: y0 + 0.65, w: wC, h: 3.75, fontSize: 18, paraSpaceAfter: 12 });
  s.addNotes("Pour conclure : en simulation, le système satisfait les quinze vérifications du cahier des charges, et la traduction sous Contiki-NG passe les mêmes tests. " +
    "Le prototype est prêt côté logiciel : les trois programmes compilent et le broker est configuré avec un compte et une ACL par nœud. " +
    "La prochaine étape est de tester le matériel et de mesurer les résultats réels. Ensuite, il faudrait activer TLS, ajouter la chaîne Node-RED, InfluxDB et Grafana, " +
    "utiliser un modèle radio plus réaliste avec les murs de l'usine, et synchroniser l'heure par NTP avec une protection contre le rejeu.");
}

// ============================================================================ 20. Questions
{
  const s = diapo("TITRE");
  const wI = 7.5 * 1300 / 1741;
  s.addImage({ path: IMG.usine, x: 0, y: 0, w: wI, h: 7.5, altText: "Ligne de production équipée de boîtiers capteurs sans fil" });
  const xT = wI + 0.7, wT = W - MX - xT;
  texte(s, "Merci de votre attention", { x: xT, y: 1.6, w: wT, h: 1.0, fontSize: 40, bold: true });
  texte(s, "Vos questions", { x: xT, y: 2.65, w: wT, h: 0.6, fontSize: 24, color: C.accent1 });
  texte(s, "Groupe 7\n" + MEMBRES.slice(0, 2).join(" · ") + "\n" + MEMBRES.slice(2).join(" · "),
    { x: xT, y: 3.6, w: wT, h: 1.1, fontSize: 16, color: C.accent6 });
  texte(s, "Crédits images : illustrations générées par IA (Google Flow) ; photos Wikimedia Commons : " +
    "ESP32, Ubahnverleih (CC0) · DS18B20, Leonardo Postay (CC BY-SA 4.0) · thermocouple K, Harke (domaine public) · " +
    "Raspberry Pi 4, Laserlicht (CC BY-SA 4.0).",
  { x: xT, y: 5.6, w: wT, h: 1.2, fontSize: 12, color: C.accent6 });
  s.addNotes("Merci de votre attention. Nous sommes prêts à répondre à vos questions. " +
    "Chiffres utiles à garder en tête : 0,87 seconde pour l'alerte de surchauffe, 30 millisecondes de latence moyenne, 100 % de livraison, 44 secondes de rétablissement sous TinyOS et 15 sous Contiki-NG, 10 rapports de l'intrus rejetés. " +
    "Si l'on nous interroge sur le prototype : le code est prêt et compile, les essais physiques sont en cours.");
}

(async () => {
  await pres.writeFile({ fileName: SORTIE });
  await applyTheme(SORTIE, THEME);
  console.log("Écrit : " + SORTIE);
})();
