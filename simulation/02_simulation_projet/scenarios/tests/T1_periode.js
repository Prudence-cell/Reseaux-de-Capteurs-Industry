/* T1 — EF1 : « une mesure toutes les 30 s ± 2 s ».
   10 nœuds, 10 min. Pour chaque capteur, on mesure l'écart entre deux rapports
   PÉRIODIQUES successifs (les alertes immédiates ne comptent pas).
   On vérifie aussi que la température reçue par la passerelle est exactement
   celle mesurée par le capteur (aucune altération en route). */
TIMEOUT(620000, terminer());
var dernier = {}, ecarts = [], ecartsParNoeud = {};
var valPub = {}, comparees = 0, differentes = 0;
planifier(610000, function () {
  var s = stats(ecarts);
  mesure("T1_ecart_moy", s.moy / 1000, "s");
  mesure("T1_ecart_min", s.min / 1000, "s");
  mesure("T1_ecart_max", s.max / 1000, "s");
  mesure("T1_n", s.n, "intervalles");
  var nbNoeuds = 0;
  for (var n in ecartsParNoeud) {
    var e = stats(ecartsParNoeud[n]);
    nbNoeuds++;
    mesure("T1_noeud_" + n, e.moy / 1000, "s (min " + (e.min / 1000).toFixed(2) + ", max " + (e.max / 1000).toFixed(2) + ")");
  }
  verdict("T1", s.n >= 9 * 15 && nbNoeuds == 9 && s.min >= 28000 && s.max <= 32000,
          nbNoeuds + " capteurs, " + s.n + " intervalles entre " + (s.min / 1000).toFixed(2) + " et " +
          (s.max / 1000).toFixed(2) + " s (tolerance 28-32 s)");
  verdict("T1_fidelite", comparees > 30 && differentes == 0,
          comparees + " temperatures comparees capteur/passerelle, " + differentes + " differentes");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (msg.indexOf("PUB ") == 0) {
    var etat = parseInt(champ(msg, "etat"));
    if (etat == 0 || etat == 3 || etat == 4) {           /* rapports périodiques uniquement */
      var t = maintenant();
      if (dernier[id] !== undefined) {
        ecarts.push(t - dernier[id]);
        if (!ecartsParNoeud[id]) ecartsParNoeud[id] = [];
        ecartsParNoeud[id].push(t - dernier[id]);
      }
      dernier[id] = t;
    }
    if (champ(msg, "type") == "1") valPub[id + ":" + champ(msg, "seq")] = parseInt(champ(msg, "val"));
  }
  if (id == PUITS && msg.indexOf("RX ") == 0 && msg.indexOf("temperature_c") > 0) {
    var cle = champ(msg, "src") + ":" + champ(msg, "seq");
    var recu = Math.round(10 * parseFloat(/"temperature_c":(-?[\d.]+)/.exec(msg)[1]));
    if (valPub[cle] !== undefined) { comparees++; if (recu != valPub[cle]) differentes++; }
  }
}
