/* T6 — ENF1 : « latence totale < 10 s » + mesures réseau sur les 10 nœuds (20 min).
   Latence capteur → passerelle de CHAQUE rapport, taux de livraison (PDR), nombre de sauts,
   et l'arbre de routage CTP final (qui relaie qui). Budget du cahier pour le saut
   radio nœud → passerelle : < 1 s. */
var P = "T6";          /* préfixe des mesures (T6b réutilise ce script) */
var PDR_MIN = 99.0;
TIMEOUT(1210000, terminer());
planifier(1200000, function () {
  var b = bilanReseau(P + "_");
  var g = pdrGlobal();
  mesure(P + "_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ")");
  for (var s in parents) ecrire("ARBRE " + s + " -> " + parents[s] + " sauts=" + sauts[s]);
  verdict(P, b.n > 300 && b.max < 10000, "latence capteur->passerelle max " + b.max.toFixed(0) +
          " ms, moyenne " + b.moy.toFixed(1) + " ms sur " + b.n + " rapports (exigence < 10 s)");
  verdict(P + "_budget_radio", b.p95 < 1000, "95 % des rapports en moins de " + b.p95.toFixed(0) +
          " ms (budget noeud->passerelle < 1 s)");
  verdict(P + "_pdr", g.pdr >= PDR_MIN, "taux de livraison " + g.pdr.toFixed(2) + " % (seuil " + PDR_MIN + " %)");
  verdict(P + "_multisaut", sauts[8] >= 2 && sauts[9] >= 2 && sauts[10] >= 2,
          "P1, P2, P3 hors de portee du puits : sauts = " + sauts[8] + ", " + sauts[9] + ", " + sauts[10]);
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
}
