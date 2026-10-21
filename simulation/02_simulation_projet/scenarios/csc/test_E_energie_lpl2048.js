/* ==========================================================================
 * commun.js — boîte à outils partagée par tous les tests (ScriptRunner de Cooja).
 * Ce fichier est collé AVANT le script de chaque test par generer_scenarios.py.
 *
 * Variables fournies par Cooja à chaque ligne écrite par un nœud :
 *   time = instant de la simulation (µs), id = numéro du nœud, msg = la ligne.
 * L'horloge de Cooja est la même pour tous les nœuds : c'est notre « horloge
 * de référence » pour mesurer les latences (PUB sur le capteur → RX à la passerelle).
 * ========================================================================== */

var PUITS = 1;
var pubs = {};          /* "src:seq" -> instant de publication (ms) */
var latences = [];      /* une entrée par rapport livré : {src, seq, ms, sauts, diff} */
var recus = {};         /* src -> nombre de RX */
var publies = {};       /* src -> nombre de PUB */
var historique = {};    /* src -> liste des {seq, t} publiés */
var livres = {};        /* "src:seq" -> true quand reçu par la passerelle */
var sauts = {};         /* src -> nombre de sauts du dernier RX */
var parents = {};       /* src -> parent CTP du dernier RX */
var verdicts = [];
var actions = {};
var nbActions = 0;
var bavard = true;      /* false : n'enregistre pas toutes les lignes dans le journal */

function maintenant() { return time / 1000.0; }      /* ms de simulation */
function ecrire(s) { log.log(s + "\n"); }

/* Extrait la valeur de « cle=valeur » dans une ligne */
function champ(ligne, cle) {
  var m = new RegExp("(^|\\s)" + cle + "=([^\\s|]+)").exec(ligne);
  return m ? m[2] : null;
}

/* À appeler pour CHAQUE ligne reçue : tient à jour les statistiques réseau */
function noter() {
  if (bavard) ecrire("L " + maintenant().toFixed(1) + " " + id + " " + msg);
  if (msg.indexOf("PUB ") == 0) {
    pubs[id + ":" + champ(msg, "seq")] = maintenant();
    publies[id] = (publies[id] || 0) + 1;
    if (!historique[id]) historique[id] = [];
    historique[id].push({seq: parseInt(champ(msg, "seq")), t: maintenant()});
  } else if (id == PUITS && msg.indexOf("RX ") == 0) {
    var src = parseInt(champ(msg, "src")), seq = champ(msg, "seq");
    var t0 = pubs[src + ":" + seq];
    recus[src] = (recus[src] || 0) + 1;
    livres[src + ":" + seq] = true;
    sauts[src] = parseInt(champ(msg, "sauts"));
    parents[src] = parseInt(champ(msg, "parent"));
    if (t0 !== undefined) {
      latences.push({src: src, seq: parseInt(seq), ms: maintenant() - t0,
                     sauts: sauts[src], diff: parseInt(champ(msg, "diff"))});
      delete pubs[src + ":" + seq];
    }
  }
}

/* Planifie une action dans « delai » ms (sert à injecter des événements) */
function planifier(delai, fonction) {
  var nom = "ACTION_" + (nbActions++);
  actions[nom] = fonction;
  GENERATE_MSG(delai, nom);
}
/* Si la ligne courante est une action planifiée, l'exécute et renvoie true */
function executerAction() {
  if (msg && actions[msg]) {
    var f = actions[msg];
    delete actions[msg];
    f();
    return true;
  }
  return false;
}

/* Envoie du texte sur le port série d'un nœud (comme si on le tapait au clavier) */
function commander(noeud, texte) {
  var m = sim.getMoteWithID(noeud);
  ecrire("CMD " + maintenant().toFixed(1) + " noeud " + noeud + " <- " + texte);
  m.getInterfaces().getSerialPort().writeString(texte + "\n");
}

/* ------------------------------------------------------------------ statistiques */
function stats(valeurs) {
  var v = valeurs.slice().sort(function (a, b) { return a - b; });
  if (v.length == 0) return {n: 0, moy: 0, min: 0, max: 0, p95: 0};
  var s = 0;
  for (var i = 0; i < v.length; i++) s += v[i];
  return {n: v.length, moy: s / v.length, min: v[0], max: v[v.length - 1],
          p95: v[Math.min(v.length - 1, Math.floor(0.95 * v.length))]};
}
function latencesDe(filtre) {
  var r = [];
  for (var i = 0; i < latences.length; i++) if (filtre(latences[i])) r.push(latences[i].ms);
  return r;
}

/* ------------------------------------------------------------------ résultats */
function mesure(cle, valeur, unite) {
  ecrire("MESURE " + cle + "=" + (typeof valeur == "number" ? valeur.toFixed(2) : valeur) +
         " " + (unite || ""));
}
function verdict(nom, ok, detail) {
  verdicts.push(ok);
  ecrire("VERDICT " + nom + " " + (ok ? "OK" : "ECHEC") + " " + detail);
}
function terminer() {
  var tousOk = verdicts.length > 0;
  for (var i = 0; i < verdicts.length; i++) tousOk = tousOk && verdicts[i];
  ecrire("FIN " + (tousOk ? "SUCCES" : "ECHEC") + " a t=" + (maintenant() / 1000).toFixed(1) + " s");
  if (tousOk) log.testOK(); else log.testFailed();
}

/* Bilan réseau standard : latence par nombre de sauts + taux de livraison par nœud */
function bilanReseau(prefixe) {
  var tout = stats(latencesDe(function (l) { return l.diff == 0; }));
  mesure(prefixe + "latence_moy", tout.moy, "ms");
  mesure(prefixe + "latence_p95", tout.p95, "ms");
  mesure(prefixe + "latence_max", tout.max, "ms");
  mesure(prefixe + "latence_n", tout.n, "");
  for (var h = 1; h <= 4; h++) {
    var s = stats(latencesDe(function (l) { return l.sauts == h && l.diff == 0; }));
    if (s.n > 0) mesure(prefixe + "latence_" + h + "saut_moy", s.moy, "ms (n=" + s.n + ")");
  }
  /* PDR : parmi les rapports publiés il y a plus de 10 s (les plus récents
     peuvent encore être en route), combien sont arrivés à la passerelle ? */
  var limite = maintenant() - 10000;
  for (var src in historique) {
    var p = 0, r = 0;
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t > limite) continue;
      p++;
      if (livres[src + ":" + e.seq]) r++;
    }
    if (p == 0) continue;
    mesure(prefixe + "pdr_" + src, 100.0 * r / p, "% (" + r + "/" + p + ") sauts=" +
           sauts[src] + " parent=" + parents[src]);
  }
  return tout;
}

/* Taux de livraison global (tous nœuds) sur les rapports publiés il y a plus de « marge » ms
   (10 s par défaut : les plus récents peuvent encore être en route) */
function pdrGlobal(marge) {
  var limite = maintenant() - (marge || 10000), p = 0, r = 0;
  for (var src in historique)
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t > limite) continue;
      p++;
      if (livres[src + ":" + e.seq]) r++;
    }
  return {publies: p, recus: r, pdr: p ? 100.0 * r / p : 0};
}

/* Variante LPL avec réveil toutes les 2048 ms (firmwares compilés avec LPL=1 LPL_MS=2048). */
var NOM_VARIANTE = "E_lpl2048";
/* Énergie (ENF5) : temps d'activité de la radio de chaque nœud, mesuré par le plugin
   PowerTracker de Cooja pendant 15 min de fonctionnement normal.
   La radio CC2420 consomme ~19 mA dès qu'elle écoute ou émet, et presque rien éteinte :
   son temps « allumée » détermine l'autonomie. On en déduit une autonomie estimée pour
   une batterie de 2000 mAh (hypothèse : microcontrôleur 0,1 mA en moyenne).
   Le même script sert à la variante LPL (E_energie_lpl.js). */
var NOM = (typeof NOM_VARIANTE !== "undefined") ? NOM_VARIANTE : "E";
var DUREE = 900000;
TIMEOUT(910000, terminer());     /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
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
  /* Livraison « à terme » : rapports publiés au moins 5 min avant la fin. En LPL, un rapport
     perdu n'est renvoyé qu'au cycle d'acquittement suivant (2 min) : il faut lui laisser le temps. */
  var g = pdrGlobal(300000);
  mesure(NOM + "_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ", publies > 5 min avant la fin)");
  verdict(NOM, nb >= 10 && g.pdr >= 99.0, "duty cycle radio mesure sur " + nb + " noeuds, moyenne capteurs " +
          (onMoy / (nb - 1)).toFixed(2) + " %, PDR " + g.pdr.toFixed(2) + " %, latence moy " + b.moy.toFixed(0) + " ms");
  terminer();
});
bavard = true;        /* journal complet : sert à analyser ce qui consomme */
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
}

