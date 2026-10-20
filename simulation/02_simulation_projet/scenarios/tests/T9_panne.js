/* T9 / ENF8 : « un nœud débranché, les autres continuent ».
   À t = 300 s, l'arbre CTP est stable et P1 (nœud 8, hors de portée du puits) passe par
   T1 (nœud 2). On RETIRE T1 de la simulation (comme si on le débranchait).
   Mesures :
     - reconvergence : temps jusqu'à ce que P1 choisisse un autre parent (ligne PARENT) ;
     - rétablissement : temps jusqu'au premier rapport de P1 reçu par le nouveau chemin ;
     - détection : temps jusqu'à « ALERTE NOEUD_MUET src=2 » à la passerelle ;
     - les 8 autres capteurs continuent : rapports reçus et PDR après la panne. */
var PANNE = 300000;
TIMEOUT(610000, terminer());     /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
var parentAvant = null, tReconv = null, nouveauParent = null, tRetabli = null, sautsApres = null;
var tMuet = null, recusApres = {};
planifier(PANNE, function () {
  parentAvant = parents[8];
  ecrire("PANNE " + maintenant().toFixed(1) + " retrait du noeud 2 (T1) ; parent de P1 = " + parentAvant);
  sim.removeMote(sim.getMoteWithID(2));
});
planifier(PANNE + 300000, function () {
  mesure("T9_reconvergence", (tReconv - PANNE) / 1000, "s (P1 : parent " + parentAvant + " -> " + nouveauParent + ")");
  mesure("T9_retablissement_P1", (tRetabli - PANNE) / 1000, "s (premier rapport de P1 recu, " + sautsApres + " sauts)");
  mesure("T9_detection_noeud_muet", (tMuet - PANNE) / 1000, "s");
  /* PDR des 8 autres capteurs sur les rapports publiés après la panne */
  var p = 0, r = 0, continuent = 0;
  for (var src in historique) {
    if (src == 2) continue;
    var pp = 0, rr = 0;
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t < PANNE || e.t > maintenant() - 10000) continue;
      pp++; if (livres[src + ":" + e.seq]) rr++;
    }
    p += pp; r += rr;
    if (rr > 0) continuent++;
    mesure("T9_pdr_apres_" + src, pp ? 100.0 * rr / pp : 0, "% (" + rr + "/" + pp + ") parent=" + parents[src]);
  }
  mesure("T9_pdr_autres", 100.0 * r / p, "% (" + r + "/" + p + ")");
  for (var s in parents) ecrire("ARBRE " + s + " -> " + parents[s] + " sauts=" + sauts[s]);
  verdict("T9", parentAvant == 2 && continuent == 8 && r == p,
          "T1 retire : " + continuent + "/8 autres capteurs continuent, PDR apres panne " + (100.0 * r / p).toFixed(1) + " %");
  verdict("T9_reroutage_P1", tRetabli !== null && nouveauParent != 2,
          "P1 passe par " + nouveauParent + " (" + sautsApres + " sauts), rapports retablis en " +
          ((tRetabli - PANNE) / 1000).toFixed(1) + " s");
  verdict("ENF8_detection", tMuet !== null, "passerelle signale NOEUD_MUET T1 apres " + ((tMuet - PANNE) / 1000).toFixed(1) + " s");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (parentAvant === null) continue;
  if (id == 8 && msg.indexOf("PARENT ") == 0 && tReconv === null) {
    tReconv = maintenant();
    nouveauParent = msg.split("->")[1].split(" ")[0];
  }
  if (id == PUITS && msg.indexOf("RX src=8 ") == 0 && tRetabli === null && champ(msg, "parent") != "2") {
    tRetabli = maintenant(); sautsApres = champ(msg, "sauts");
  }
  if (id == PUITS && msg.indexOf("ALERTE NOEUD_MUET src=2") == 0 && tMuet === null) tMuet = maintenant();
}
