/* Scénario de démonstration (version avec fenêtres) : rien à faire, il se déroule seul.
   - t = 90 s  : la sonde de M2 (T2, nœud 3) lit 95 °C  → ALERTE SURCHAUFFE
   - t = 150 s : retour à la normale
   - t = 100 s : présence à l'entrée (P1, nœud 8) à 18h40 → ALERTE INTRUSION + buzzer (LED bleue)
   - t = 40 s  : présence sur le quai de réception (P2) à 17h40 : heures ouvrées, pas d'alerte */
TIMEOUT(36000000);   /* 10 h de simulation (sinon Cooja arrête le script après 20 min) */
bavard = false;
planifier(40000,  function () { commander(9, "P"); });
planifier(90000,  function () { commander(3, "H"); });
planifier(100000, function () { commander(8, "P"); });
planifier(150000, function () { commander(3, "N"); });
while (true) {
  YIELD();
  if (executerAction()) continue;
}
