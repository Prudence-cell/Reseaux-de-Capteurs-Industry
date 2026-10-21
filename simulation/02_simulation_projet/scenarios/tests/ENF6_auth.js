/* ENF6 : « messages authentifiés ».
   Un 11e nœud, INTRUS, est posé près de T2 (26 ; 14 m). Il exécute le même programme
   thermique mais ne connaît pas la clé du réseau (compilé avec CLE=0x0BADC0DE). Un nœud
   honnête sans la clé rejetterait déjà les acquittements de la passerelle et n'émettrait pas ;
   l'intrus est compilé avec INTRUS=1 pour ignorer cette vérification et émettre quand même.
   Attendu : la passerelle rejette TOUS ses rapports (REJET_AUTH) et accepte tous
   ceux des 9 capteurs légitimes. */
TIMEOUT(310000, terminer());
var rejetsIntrus = 0, rejetsLegitimes = 0, rxIntrus = 0, pubIntrus = 0;
planifier(300000, function () {
  var g = pdrGlobal();
  mesure("ENF6_rapports_intrus", pubIntrus, "publies par l'intrus");
  mesure("ENF6_rejets_intrus", rejetsIntrus, "");
  mesure("ENF6_rejets_legitimes", rejetsLegitimes, "");
  verdict("ENF6", rejetsIntrus >= 5 && rxIntrus == 0 && rejetsLegitimes == 0,
          rejetsIntrus + " rapports de l'intrus rejetes, " + rxIntrus + " acceptes ; " +
          rejetsLegitimes + " rapport legitime rejete");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (id == 11 && msg.indexOf("PUB ") == 0) pubIntrus++;
  if (id == PUITS && msg.indexOf("REJET_AUTH") == 0) {
    if (champ(msg, "origine") == "11") rejetsIntrus++; else rejetsLegitimes++;
  }
  if (id == PUITS && msg.indexOf("RX src=11 ") == 0) rxIntrus++;
}
