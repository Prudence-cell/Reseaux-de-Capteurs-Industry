/* T7 — ENF3 : « coupure d'1 h → données gardées puis renvoyées ».
   À t = 300 s, la passerelle est ÉLOIGNÉE à 1 km (hors de portée de tous les nœuds) pendant
   1 h (3600 s), puis remise à sa place : c'est une coupure de la liaison radio, la passerelle
   continue de fonctionner. Pendant la coupure, chaque capteur garde ses rapports dans son tampon
   (130 places ≈ 65 min à 30 s). Au retour, il doit tout renvoyer, marqué « différé ».
   On vérifie : récupération des rapports publiés pendant la coupure, temps de vidage
   des tampons, et que l'horodatage JSON est celui de la MESURE, pas celui de la réception. */
var DEBUT = 300000;
var DUREE = (typeof DUREE_COUPURE !== "undefined") ? DUREE_COUPURE : 3600000;
var FIN = DEBUT + DUREE;
TIMEOUT(4510000, terminer());   /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
var tBootGw = null, tampMax = {}, dernierDiffere = null, nbDifferes = 0, ecartHorodatage = 0;
var tPub = {};
/* Déplace un nœud dans la simulation (interface Position de Cooja) */
function deplacer(noeud, x, y) {
  sim.getMoteWithID(noeud).getInterfaces().getPosition().setCoordinates(x, y, 0);
  ecrire("DEPLACEMENT " + maintenant().toFixed(1) + " noeud " + noeud + " -> (" + x + " ; " + y + ")");
}
var gwX = null, gwY = null;
planifier(DEBUT, function () {
  var pos = sim.getMoteWithID(PUITS).getInterfaces().getPosition();
  gwX = pos.getXCoordinate(); gwY = pos.getYCoordinate();
  deplacer(PUITS, gwX, gwY - 1000);                    /* coupure */
});
planifier(FIN, function () { deplacer(PUITS, gwX, gwY); });   /* rétablissement */
planifier(FIN + 600000, function () {
  var pend = 0, rec = 0, txt = "";
  for (var src in historique) {
    var p = 0, r = 0;
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t < DEBUT || e.t > FIN) continue;
      p++; if (livres[src + ":" + e.seq]) r++;
    }
    pend += p; rec += r;
    txt += src + ":" + r + "/" + p + " ";
    mesure("T7_tampon_max_" + src, tampMax[src] || 0, "rapports en attente au maximum");
  }
  mesure("T7_publies_pendant_coupure", pend, "");
  mesure("T7_recuperes", rec, "");
  mesure("T7_recuperation", pend ? 100.0 * rec / pend : 0, "%");
  mesure("T7_rapports_differes", nbDifferes, "");
  mesure("T7_temps_vidage", (dernierDiffere - FIN) / 1000, "s apres le retablissement");
  mesure("T7_ecart_horodatage_max", ecartHorodatage, "s");
  var g = pdrGlobal();
  mesure("T7_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ")");
  verdict("T7", pend >= 9 * (DUREE / 30000) - 9 && rec == pend, "rapports publies pendant 1 h de coupure puis recus : " +
          rec + "/" + pend + " (" + txt + ")");
  /* Critère choisi par nous (le cahier n'en fixe pas) : ± 5 s, soit 1/6 de la période de 30 s,
     pour qu'une mesure ne puisse jamais être confondue avec la précédente ou la suivante.
     L'écart vient du temps passé dans les files des RELAIS, que age_ms ne compte pas. */
  verdict("T7_horodatage", ecartHorodatage <= 5.0, "ecart max entre timestamp JSON et instant de mesure : " +
          ecartHorodatage.toFixed(1) + " s (critere +/- 5 s = 1/6 de la periode)");
  terminer();
});
bavard = (typeof JOURNAL_COMPLET !== "undefined");   /* journal allégé : la simulation dure 75 min */
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (!bavard && (msg.indexOf("PUB ") == 0 || msg.indexOf("RX ") == 0 || msg.indexOf("COUPURE") >= 0 ||
      msg.indexOf("RETABLISSEMENT") >= 0 || msg.indexOf("ECHEC_ENVOI") == 0 || msg.indexOf("PARENT") == 0 ||
      msg.indexOf("LIGNE") >= 0 || msg.indexOf("RENVOI") == 0 || msg.indexOf("TAMPON") == 0))
    ecrire("L " + maintenant().toFixed(1) + " " + id + " " + msg);
  if (id == PUITS && msg.indexOf("BOOT passerelle") == 0) tBootGw = maintenant();
  if (msg.indexOf("PUB ") == 0) {
    var a = parseInt(champ(msg, "attente"));
    if (!tampMax[id] || a > tampMax[id]) tampMax[id] = a;
    tPub[id + ":" + champ(msg, "seq")] = maintenant();
  }
  if (id == PUITS && msg.indexOf("RX ") == 0 && champ(msg, "diff") == "1") {
    nbDifferes++;
    dernierDiffere = maintenant();
    /* timestamp attendu = EPOCH_DEBUT + (instant de mesure - démarrage de la passerelle) */
    var ts = parseInt(/"timestamp":(\d+)/.exec(msg)[1]);
    var t0 = tPub[champ(msg, "src") + ":" + champ(msg, "seq")];
    if (t0 !== undefined) {
      var attendu = 1792512000 + (t0 - tBootGw) / 1000;
      ecartHorodatage = Math.max(ecartHorodatage, Math.abs(ts - attendu));
    }
  }
}
