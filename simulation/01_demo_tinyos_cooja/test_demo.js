/* Test automatique (Cooja sans fenêtre) : on écoute ce que les nœuds écrivent
   et on vérifie que (1) le puits reçoit les mesures, (2) l'alerte se déclenche,
   (3) le nœud 4, hors de portée, n'est jamais entendu. */
TIMEOUT(120000, log.log("TIMEOUT\n"); log.testFailed());

var recus = 0, alerte = false, duNoeud4 = 0;
while (true) {
  YIELD();
  log.log((time / 1000).toFixed(0) + " ms  noeud " + id + "  " + msg + "\n");
  if (msg.startsWith("RX")) {
    recus++;
    if (msg.indexOf("noeud=4 ") >= 0) duNoeud4++;
  }
  if (msg.indexOf("ALERTE") >= 0) alerte = true;
  if (alerte && recus >= 12) break;
}
log.log("RESULTAT: " + recus + " mesures recues par le puits, alerte=" + alerte +
        ", mesures du noeud 4 (hors portee)=" + duNoeud4 + "\n");
if (duNoeud4 == 0) log.testOK(); else log.testFailed();
