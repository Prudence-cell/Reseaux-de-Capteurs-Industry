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
                     sauts: sauts[src], diff: 0});
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

/* T6b — mêmes mesures que T6, mais avec des liens radio DÉGRADÉS : dans le .csc,
   UDGM success_ratio_rx = 0,8 (à 20 m, seuls 80 % des paquets arrivent ; plus près, davantage).
   CTP doit retransmettre (accusés de réception) et éviter les mauvais liens. */
var P = "T6b";
var PDR_MIN = 98.0;
TIMEOUT(1210000, terminer());
planifier(1200000, function () {
  var b = bilanReseau(P + "_");
  var g = pdrGlobal();
  mesure(P + "_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ")");
  for (var s in parents) ecrire("ARBRE " + s + " -> " + parents[s] + " sauts=" + sauts[s]);
  verdict(P, b.n > 300 && b.max < 10000, "latence capteur->passerelle max " + b.max.toFixed(0) +
          " ms, moyenne " + b.moy.toFixed(1) + " ms sur " + b.n + " rapports (exigence < 10 s)");
  verdict(P + "_pdr", g.pdr >= PDR_MIN, "taux de livraison " + g.pdr.toFixed(2) + " % (seuil " + PDR_MIN + " %)");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
}
