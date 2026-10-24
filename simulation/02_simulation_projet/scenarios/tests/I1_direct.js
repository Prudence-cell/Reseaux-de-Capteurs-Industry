/* Incrément 1 : passerelle (1) + capteur thermique T2 (3), à 12,6 m l'un de l'autre.
   On attend 2 min et on vérifie : rapports reçus, 1 seul saut, JSON au format du cahier. */
TIMEOUT(130000, terminer());
var json = null;
planifier(120000, function () {
  var b = bilanReseau("");
  verdict("I1_reception", (recus[3] || 0) >= 3, "rapports de T2 recus=" + (recus[3] || 0));
  verdict("I1_un_saut", sauts[3] == 1, "sauts=" + sauts[3]);
  verdict("I1_json", json != null && json.indexOf('"node_id":"MACHINE_02"') > 0 &&
          json.indexOf('"temperature_c":') > 0, "exemple : " + json);
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (id == PUITS && msg.indexOf("RX ") == 0) json = msg.substring(msg.indexOf("|") + 2);
}
