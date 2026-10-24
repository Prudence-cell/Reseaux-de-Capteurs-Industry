/* T6b — mêmes mesures que T6, mais avec des liens radio DÉGRADÉS : dans le .csc,
   UDGM success_ratio_rx = 0,8 (à 20 m, seuls 80 % des paquets arrivent ; plus près, davantage).
   CTP doit retransmettre (accusés de réception) et éviter les mauvais liens. */
var P = "T6b";
var PDR_MIN = 98.0;
TIMEOUT(1210000, terminer());
planifier(1200000, function () {
  var b = bilanReseau(P + "_");
  var g = pdrGlobal();
  mesure(P + "_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ")");
  for (var s in parents) ecrire("ARBRE " + s + " -> " + parents[s] + " sauts=" + sauts[s]);
  verdict(P, b.n > 300 && b.max < 10000, "latence capteur->passerelle max " + b.max.toFixed(0) +
          " ms, moyenne " + b.moy.toFixed(1) + " ms sur " + b.n + " rapports (exigence < 10 s)");
  verdict(P + "_pdr", g.pdr >= PDR_MIN, "taux de livraison " + g.pdr.toFixed(2) + " % (seuil " + PDR_MIN + " %)");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
}
