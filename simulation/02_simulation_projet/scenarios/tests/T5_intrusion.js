/* T5 — EF6/B4 : « présence hors heures → alerte en < 5 s ».
   Horloge d'usine : départ 17h00, 1 s = 1 min. 18h00 = 60 s, 08h00 le lendemain = 900 s.
     t =  30 s (17h30, ouvert)  : présence sur P2 → AUCUNE alerte attendue ;
     t = 120 s (19h00, fermé)   : présence sur P1, puis P2 (135 s), puis P3 (150 s)
                                  → une ALERTE INTRUSION par zone, latence < 5 s ;
     t = 930 s (08h30, ouvert)  : présence sur P3 → AUCUNE alerte attendue. */
TIMEOUT(970000, terminer());
var ZONE = {8: "ZONE_01", 9: "ZONE_02", 10: "ZONE_03"};
var tInj = {}, tAlerte = {}, alerteJour = 0, buzzer = {};
var phase = "jour1";
planifier(30000,  function () { commander(9, "P"); });
planifier(66000,  function () { phase = "nuit"; });
planifier(120000, function () { tInj[8] = maintenant(); commander(8, "P"); });
planifier(135000, function () { tInj[9] = maintenant(); commander(9, "P"); });
planifier(150000, function () { tInj[10] = maintenant(); commander(10, "P"); });
planifier(905000, function () { phase = "jour2"; });
planifier(930000, function () { commander(10, "P"); });
planifier(960000, function () {
  var ok = true, txt = "";
  for (var n = 8; n <= 10; n++) {
    var l = tAlerte[n] - tInj[n];
    mesure("T5_latence_" + ZONE[n], l, "ms");
    ok = ok && tAlerte[n] !== undefined && l < 5000 && buzzer[n] === true;
    txt += ZONE[n] + "=" + (l / 1000).toFixed(2) + " s ";
  }
  verdict("T5", ok, "alertes de nuit : " + txt + "(exigence < 5 s, buzzer local actif)");
  verdict("T5_pas_alerte_de_jour", alerteJour == 0,
          alerteJour + " alerte(s) pendant les heures ouvrees (presences a 17h30 et 08h30)");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (msg.indexOf("INTRUSION heure=") == 0 && msg.indexOf("buzzer") > 0) buzzer[id] = true;
  if (id == PUITS && msg.indexOf("ALERTE INTRUSION") == 0) {
    if (phase != "nuit") alerteJour++;
    var src = parseInt(champ(msg, "src"));
    if (tInj[src] !== undefined && tAlerte[src] === undefined) tAlerte[src] = maintenant();
  }
}
