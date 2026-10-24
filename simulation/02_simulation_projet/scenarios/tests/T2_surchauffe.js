/* T2 — EF2/ENF1 : « simulation de 95 °C → alerte en < 10 s ».
   À t = 120 s, la sonde de la presse M2 (T2, nœud 3, seuil 90 °C) lit 95 °C.
   Latence mesurée : de l'injection à la ligne ALERTE de la passerelle.
   Contrôles complémentaires (seuil PROPRE à chaque machine) :
     - le four M3 tourne à ~185 °C sans alerte (son seuil est 220 °C) ;
     - à t = 200 s on force M3 à 225 °C : alerte attendue aussi.
   À t = 160 s, retour à la normale de M2 : FIN_ALERTE attendue. */
TIMEOUT(260000, terminer());
var tInj = {}, tDetect = {}, tAlerte = {}, alerteM3Avant = false, finM2 = false, statusAlerte = false;
planifier(120000, function () { tInj[3] = maintenant(); commander(3, "H"); });
planifier(160000, function () { commander(3, "N"); });
planifier(200000, function () { tInj[4] = maintenant(); commander(4, "H"); });
planifier(250000, function () {
  var l2 = tAlerte[3] - tInj[3], l3 = tAlerte[4] - tInj[4];
  mesure("T2_latence_injection_alerte_M2", l2, "ms");
  mesure("T2_latence_detection_alerte_M2", tAlerte[3] - tDetect[3], "ms");
  mesure("T2_latence_injection_alerte_M3", l3, "ms");
  verdict("T2", tAlerte[3] !== undefined && l2 < 10000,
          "M2 a 95 C : alerte " + (l2 / 1000).toFixed(2) + " s apres l'injection (exigence < 10 s, cible 5 s)");
  verdict("T2_json_status", statusAlerte, "JSON MACHINE_02 avec status ALERTE publie");
  verdict("T2_seuil_par_machine", !alerteM3Avant && tAlerte[4] !== undefined && l3 < 10000,
          "M3 a ~185 C sans alerte (seuil 220 C), puis alerte a 225 C en " + (l3 / 1000).toFixed(2) + " s");
  verdict("T2_fin_alerte", finM2, "FIN_ALERTE SURCHAUFFE MACHINE_02 apres retour a la normale");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (msg.indexOf("DEPASSEMENT") == 0 && tDetect[id] === undefined) tDetect[id] = maintenant();
  if (id == PUITS && msg.indexOf("ALERTE SURCHAUFFE MACHINE_02") == 0 && tAlerte[3] === undefined) tAlerte[3] = maintenant();
  if (id == PUITS && msg.indexOf("ALERTE SURCHAUFFE MACHINE_03") == 0) {
    if (tInj[4] === undefined) alerteM3Avant = true; else if (tAlerte[4] === undefined) tAlerte[4] = maintenant();
  }
  if (id == PUITS && msg.indexOf("MACHINE_02") > 0 && msg.indexOf("\"status\":\"ALERTE\"") > 0) statusAlerte = true;
  if (id == PUITS && msg.indexOf("FIN_ALERTE SURCHAUFFE MACHINE_02") == 0) finM2 = true;
}
