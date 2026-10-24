/* T4 — EF5 : « 100 pièces → compteur = 100 ».
   Poste 1 (C1, nœud 5) : on coupe les arrivées automatiques (A), on remet à zéro (Z),
   puis on fait passer exactement 100 pièces (+), une toutes les 200 ms.
   On vérifie le compteur local ET le production_count reçu par la passerelle.
   Bonus « le compteur survit à un redémarrage » : à t = 150 s, on redémarre C2 (nœud 6,
   en marche automatique) par le chien de garde ; il doit repartir de sa valeur. */
TIMEOUT(260000, terminer());
var tFin100 = null, cptLocal = null, cptPasserelle = null, cptC2 = 0;
var c2AvantReboot = null, c2Restaure = null, c2Redemarrage = false, c2ApresPasserelle = null;
planifier(20000, function () { commander(5, "A"); commander(5, "Z"); });
for (var k = 0; k < 100; k++) planifier(25000 + 200 * k, function () { commander(5, "+"); });
planifier(25000 + 200 * 100, function () { tFin100 = maintenant(); });
planifier(150000, function () { c2AvantReboot = cptC2; commander(6, "R"); });
planifier(250000, function () {
  mesure("T4_compteur_local_C1", cptLocal, "pieces");
  mesure("T4_compteur_passerelle_C1", cptPasserelle, "pieces");
  mesure("T4_C2_avant_redemarrage", c2AvantReboot, "pieces");
  mesure("T4_C2_restaure", c2Restaure, "pieces");
  verdict("T4", cptLocal == 100 && cptPasserelle == 100,
          "100 pieces injectees : compteur local=" + cptLocal + ", production_count recu=" + cptPasserelle);
  verdict("T4_redemarrage", c2Restaure !== null && c2Restaure == c2AvantReboot && c2Redemarrage &&
          c2ApresPasserelle !== null && c2ApresPasserelle >= c2AvantReboot,
          "C2 redemarre a " + c2AvantReboot + " pieces, RESTAURE compteur=" + c2Restaure +
          ", passerelle voit REDEMARRAGE puis production_count=" + c2ApresPasserelle);
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (id == 5 && msg.indexOf("PIECE n=") == 0) cptLocal = parseInt(champ(msg, "n"));
  if (id == 6 && msg.indexOf("PIECE n=") == 0) cptC2 = parseInt(champ(msg, "n"));
  if (id == 6 && msg.indexOf("RESTAURE compteur=") > 0 && c2AvantReboot !== null)
    c2Restaure = parseInt(/RESTAURE compteur=(\d+)/.exec(msg)[1]);
  if (id == PUITS && msg.indexOf("REDEMARRAGE src=6") == 0) c2Redemarrage = true;
  if (id == PUITS && msg.indexOf("RX src=5 ") == 0 && tFin100 !== null && cptPasserelle === null)
    cptPasserelle = parseInt(/"production_count":(\d+)/.exec(msg)[1]);
  if (id == PUITS && msg.indexOf("RX src=6 ") == 0 && c2Redemarrage && c2ApresPasserelle === null)
    c2ApresPasserelle = parseInt(/"production_count":(\d+)/.exec(msg)[1]);
}
