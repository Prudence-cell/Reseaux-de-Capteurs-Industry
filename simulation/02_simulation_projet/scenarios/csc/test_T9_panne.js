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

/* T9 / ENF8 : « un nœud débranché, les autres continuent ».
   À t = 300 s, l'arbre CTP est stable et P1 (nœud 8, hors de portée du puits) passe par
   T1 (nœud 2). On RETIRE T1 de la simulation (comme si on le débranchait).
   Mesures :
     - reconvergence : temps jusqu'à ce que P1 choisisse un autre parent (ligne PARENT) ;
     - rétablissement : temps jusqu'au premier rapport de P1 reçu par le nouveau chemin ;
     - détection : temps jusqu'à « ALERTE NOEUD_MUET src=2 » à la passerelle ;
     - les 8 autres capteurs continuent : rapports reçus et PDR après la panne. */
var PANNE = 300000;
TIMEOUT(610000, terminer());     /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
var parentAvant = null, tReconv = null, nouveauParent = null, tRetabli = null, sautsApres = null;
var tMuet = null, recusApres = {};
planifier(PANNE, function () {
  parentAvant = parents[8];
  ecrire("PANNE " + maintenant().toFixed(1) + " retrait du noeud 2 (T1) ; parent de P1 = " + parentAvant);
  sim.removeMote(sim.getMoteWithID(2));
});
planifier(PANNE + 300000, function () {
  mesure("T9_reconvergence", (tReconv - PANNE) / 1000, "s (P1 : parent " + parentAvant + " -> " + nouveauParent + ")");
  mesure("T9_retablissement_P1", (tRetabli - PANNE) / 1000, "s (premier rapport de P1 recu, " + sautsApres + " sauts)");
  mesure("T9_detection_noeud_muet", (tMuet - PANNE) / 1000, "s");
  /* PDR des 8 autres capteurs sur les rapports publiés après la panne */
  var p = 0, r = 0, continuent = 0;
  for (var src in historique) {
    if (src == 2) continue;
    var pp = 0, rr = 0;
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t < PANNE || e.t > maintenant() - 10000) continue;
      pp++; if (livres[src + ":" + e.seq]) rr++;
    }
    p += pp; r += rr;
    if (rr > 0) continuent++;
    mesure("T9_pdr_apres_" + src, pp ? 100.0 * rr / pp : 0, "% (" + rr + "/" + pp + ") parent=" + parents[src]);
  }
  mesure("T9_pdr_autres", 100.0 * r / p, "% (" + r + "/" + p + ")");
  for (var s in parents) ecrire("ARBRE " + s + " -> " + parents[s] + " sauts=" + sauts[s]);
  verdict("T9", parentAvant == 2 && continuent == 8 && r == p,
          "T1 retire : " + continuent + "/8 autres capteurs continuent, PDR apres panne " + (100.0 * r / p).toFixed(1) + " %");
  verdict("T9_reroutage_P1", tRetabli !== null && nouveauParent != 2,
          "P1 passe par " + nouveauParent + " (" + sautsApres + " sauts), rapports retablis en " +
          ((tRetabli - PANNE) / 1000).toFixed(1) + " s");
  verdict("ENF8_detection", tMuet !== null, "passerelle signale NOEUD_MUET T1 apres " + ((tMuet - PANNE) / 1000).toFixed(1) + " s");
  terminer();
});
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (parentAvant === null) continue;
  if (id == 8 && msg.indexOf("PARENT ") == 0 && tReconv === null) {
    tReconv = maintenant();
    nouveauParent = msg.split("->")[1].split(" ")[0];
  }
  if (id == PUITS && msg.indexOf("RX src=8 ") == 0 && tRetabli === null && champ(msg, "parent") != "2") {
    tRetabli = maintenant(); sautsApres = champ(msg, "sauts");
  }
  if (id == PUITS && msg.indexOf("ALERTE NOEUD_MUET src=2") == 0 && tMuet === null) tMuet = maintenant();
}
