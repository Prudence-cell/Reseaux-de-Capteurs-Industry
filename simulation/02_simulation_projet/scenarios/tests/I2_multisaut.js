/* Incrément 2 : P1 (nœud 8) est à 22,7 m de la passerelle, hors de portée (20 m).
   Il doit passer par T1 (nœud 2) : 2 sauts. On vérifie aussi le passage en mode nuit
   (18h00 = 60 s) et qu'une présence à 18h40 donne une ALERTE INTRUSION relayée. */
TIMEOUT(160000, terminer());
var alerte = false, nuit = false, parentP1 = null;
planifier(100000, function () { commander(8, "P"); });
planifier(150000, function () {
  bilanReseau("");
  verdict("I2_P1_recu", (recus[8] || 0) >= 3, "rapports de P1 recus=" + (recus[8] || 0));
  verdict("I2_P1_deux_sauts", sauts[8] == 2 && parents[8] == 2,
          "sauts=" + sauts[8] + " parent=" + parents[8]);
  verdict("I2_mode_nuit", nuit, "passage HORLOGE 18:00 vu sur P1");
  verdict("I2_alerte_intrusion", alerte, "ALERTE INTRUSION recue par la passerelle");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (id == 8 && msg.indexOf("mode nuit") > 0) nuit = true;
  if (id == PUITS && msg.indexOf("ALERTE INTRUSION ZONE_01") == 0) alerte = true;
}
