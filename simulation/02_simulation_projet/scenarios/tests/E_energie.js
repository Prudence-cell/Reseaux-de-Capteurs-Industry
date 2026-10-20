/* Énergie (ENF5) : temps d'activité de la radio de chaque nœud, mesuré par le plugin
   PowerTracker de Cooja pendant 10 min de fonctionnement normal.
   La radio CC2420 consomme ~19 mA dès qu'elle écoute ou émet, et presque rien éteinte :
   son temps « allumée » détermine l'autonomie. On en déduit une autonomie estimée pour
   une batterie de 2000 mAh (hypothèse : microcontrôleur 0,1 mA en moyenne).
   Le même script sert à la variante LPL (E_energie_lpl.js). */
var NOM = (typeof NOM_VARIANTE !== "undefined") ? NOM_VARIANTE : "E";
var DUREE = 600000;
TIMEOUT(610000, terminer());     /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
planifier(DUREE, function () {
  var b = bilanReseau(NOM + "_");
  var pt = null, pl = gui.getStartedPlugins();
  for (var i = 0; i < pl.length; i++)
    if (pl[i].getClass().getSimpleName() == "PowerTracker") pt = pl[i];
  if (pt == null) { verdict(NOM, false, "plugin PowerTracker introuvable"); terminer(); }
  var txt = String(pt.radioStatistics(true, true, false));
  var lignes = txt.split("\n");
  var on = {}, onMoy = 0, nb = 0;
  for (var j = 0; j < lignes.length; j++) {
    ecrire("RADIO " + lignes[j]);
    var m = /^(\S+)\s+ON\s+\d+ us\s+([\d.,]+) %/.exec(lignes[j]);
    if (m && m[1] != "AVG") { on[m[1]] = parseFloat(m[2].replace(",", ".")); }
  }
  for (var k in on) {
    var n = parseInt(k.replace(/\D/g, ""));                /* « Sky_3 » -> 3 */
    var courant = on[k] / 100.0 * 19.0 + 0.1;              /* mA moyens */
    var heures = 2000.0 / courant;
    mesure(NOM + "_radio_on_" + n, on[k], "% -> " + courant.toFixed(2) + " mA, autonomie " +
           (heures / 24).toFixed(0) + " jours");
    nb++;
    if (n != PUITS) onMoy += on[k];                        /* moyenne des capteurs seuls */
  }
  mesure(NOM + "_radio_on_capteurs_moy", onMoy / (nb - 1), "%");
  var g = pdrGlobal();
  mesure(NOM + "_pdr_global", g.pdr, "%");
  verdict(NOM, nb >= 10 && g.pdr >= 99.0, "duty cycle radio mesure sur " + nb + " noeuds, moyenne capteurs " +
          (onMoy / (nb - 1)).toFixed(2) + " %, PDR " + g.pdr.toFixed(2) + " %, latence moy " + b.moy.toFixed(0) + " ms");
  terminer();
});
bavard = false;
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
}
