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

/* T7c : version courte de T7 (5 min de coupure), journal complet, pour le diagnostic. */
var DUREE_COUPURE = 300000;
var JOURNAL_COMPLET = true;
/* T7 — ENF3 : « coupure d'1 h → données gardées puis renvoyées ».
   À t = 300 s, la passerelle est ÉLOIGNÉE à 1 km (hors de portée de tous les nœuds) pendant
   1 h (3600 s), puis remise à sa place : c'est une coupure de la liaison radio, la passerelle
   continue de fonctionner. Pendant la coupure, chaque capteur garde ses rapports dans son tampon
   (130 places ≈ 65 min à 30 s). Au retour, il doit tout renvoyer, marqué « différé ».
   On vérifie : récupération des rapports publiés pendant la coupure, temps de vidage
   des tampons, et que l'horodatage JSON est celui de la MESURE, pas celui de la réception. */
var DEBUT = 300000;
var DUREE = (typeof DUREE_COUPURE !== "undefined") ? DUREE_COUPURE : 3600000;
var FIN = DEBUT + DUREE;
TIMEOUT(4510000, terminer());   /* nombre écrit en clair : Cooja lit TIMEOUT avec une expression régulière */
var tBootGw = null, tampMax = {}, dernierDiffere = null, nbDifferes = 0, ecartHorodatage = 0;
var tPub = {};
/* Déplace un nœud dans la simulation (interface Position de Cooja) */
function deplacer(noeud, x, y) {
  sim.getMoteWithID(noeud).getInterfaces().getPosition().setCoordinates(x, y, 0);
  ecrire("DEPLACEMENT " + maintenant().toFixed(1) + " noeud " + noeud + " -> (" + x + " ; " + y + ")");
}
var gwX = null, gwY = null;
planifier(DEBUT, function () {
  var pos = sim.getMoteWithID(PUITS).getInterfaces().getPosition();
  gwX = pos.getXCoordinate(); gwY = pos.getYCoordinate();
  deplacer(PUITS, gwX, gwY - 1000);                    /* coupure */
});
planifier(FIN, function () { deplacer(PUITS, gwX, gwY); });   /* rétablissement */
planifier(FIN + 600000, function () {
  var pend = 0, rec = 0, txt = "";
  for (var src in historique) {
    var p = 0, r = 0;
    for (var i = 0; i < historique[src].length; i++) {
      var e = historique[src][i];
      if (e.t < DEBUT || e.t > FIN) continue;
      p++; if (livres[src + ":" + e.seq]) r++;
    }
    pend += p; rec += r;
    txt += src + ":" + r + "/" + p + " ";
    mesure("T7_tampon_max_" + src, tampMax[src] || 0, "rapports en attente au maximum");
  }
  mesure("T7_publies_pendant_coupure", pend, "");
  mesure("T7_recuperes", rec, "");
  mesure("T7_recuperation", pend ? 100.0 * rec / pend : 0, "%");
  mesure("T7_rapports_differes", nbDifferes, "");
  mesure("T7_temps_vidage", (dernierDiffere - FIN) / 1000, "s apres le retablissement");
  mesure("T7_ecart_horodatage_max", ecartHorodatage, "s");
  var g = pdrGlobal();
  mesure("T7_pdr_global", g.pdr, "% (" + g.recus + "/" + g.publies + ")");
  verdict("T7", pend >= 9 * (DUREE / 30000) - 9 && rec == pend, "rapports publies pendant 1 h de coupure puis recus : " +
          rec + "/" + pend + " (" + txt + ")");
  /* Critère choisi par nous (le cahier n'en fixe pas) : ± 5 s, soit 1/6 de la période de 30 s,
     pour qu'une mesure ne puisse jamais être confondue avec la précédente ou la suivante.
     L'écart vient du temps passé dans les files des RELAIS, que age_ms ne compte pas. */
  verdict("T7_horodatage", ecartHorodatage <= 5.0, "ecart max entre timestamp JSON et instant de mesure : " +
          ecartHorodatage.toFixed(1) + " s (critere +/- 5 s = 1/6 de la periode)");
  terminer();
});
bavard = (typeof JOURNAL_COMPLET !== "undefined");   /* journal allégé : la simulation dure 75 min */
while (true) {
  YIELD();
  if (executerAction()) continue;
  noter();
  if (!bavard && (msg.indexOf("PUB ") == 0 || msg.indexOf("RX ") == 0 || msg.indexOf("COUPURE") >= 0 ||
      msg.indexOf("RETABLISSEMENT") >= 0 || msg.indexOf("ECHEC_ENVOI") == 0 || msg.indexOf("PARENT") == 0 ||
      msg.indexOf("LIGNE") >= 0 || msg.indexOf("RENVOI") == 0 || msg.indexOf("TAMPON") == 0))
    ecrire("L " + maintenant().toFixed(1) + " " + id + " " + msg);
  if (id == PUITS && msg.indexOf("BOOT passerelle") == 0) tBootGw = maintenant();
  if (msg.indexOf("PUB ") == 0) {
    var a = parseInt(champ(msg, "attente"));
    if (!tampMax[id] || a > tampMax[id]) tampMax[id] = a;
    tPub[id + ":" + champ(msg, "seq")] = maintenant();
  }
  if (id == PUITS && msg.indexOf("RX ") == 0 && champ(msg, "diff") == "1") {
    nbDifferes++;
    dernierDiffere = maintenant();
    /* timestamp attendu = EPOCH_DEBUT + (instant de mesure - démarrage de la passerelle) */
    var ts = parseInt(/"timestamp":(\d+)/.exec(msg)[1]);
    var t0 = tPub[champ(msg, "src") + ":" + champ(msg, "seq")];
    if (t0 !== undefined) {
      var attendu = 1792512000 + (t0 - tBootGw) / 1000;
      ecartHorodatage = Math.max(ecartHorodatage, Math.abs(ts - attendu));
    }
  }
}

