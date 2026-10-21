/*
 * MODULE de la passerelle.
 *
 * Pour chaque rapport reçu par CTP :
 *   1. vérifie le code d'authentification (ENF6) ; sinon « REJET_AUTH » ;
 *   2. met à jour le suivi du nœud (reçus, pertes, doublons) → taux de livraison (PDR) ;
 *   3. écrit une ligne « RX ... | topic {json} » : le message MQTT qu'elle publierait ;
 *   4. décide des ALERTES (B3) : surchauffe (seuil propre à chaque machine, EF2),
 *      intrusion hors heures (EF6), nœud muet (ENF8).
 * Toutes les 60 s elle écrit une ligne « STAT » par nœud.
 * Toutes les 30 s elle DIFFUSE (Drip) les acquittements : pour chaque nœud, le plus grand
 * numéro reçu sans trou. Les capteurs effacent alors ces rapports de leur tampon.
 *
 * Commande série (banc d'essai) : S = statistiques tout de suite.
 * (La coupure du test T7 se fait en ÉLOIGNANT la passerelle dans Cooja, pas en éteignant
 *  sa radio : arrêter la radio pendant une émission bloque la pile CC2420 de TinyOS.)
 */
#include "Usine.h"

module PasserelleC {
  uses {
    interface Boot;
    interface Leds;
    interface Console;
    interface SplitControl as RadioControl;
    interface StdControl as RoutingControl;
    interface RootControl;
    interface Receive;
    interface CtpPacket;
    interface CtpInfo;
    interface Timer<TMilli> as Stats;
    interface Timer<TMilli> as Supervision;
    interface Timer<TMilli> as Acquitter;
    interface StdControl as DisseminationControl;
    interface DisseminationUpdate<acquit_t> as Acquit;
#ifdef LOW_POWER_LISTENING
    interface LowPowerListening;
#endif
  }
}
implementation {
  /* Ce que la passerelle retient de chaque nœud */
  typedef struct {
    uint16_t recus, doublons, redemarrages;
    uint16_t contigu;          /* tous les seq <= contigu sont arrivés (c'est ce qu'on acquitte) */
    uint8_t  vus[FENETRE_SUIVI / 8];  /* bit (seq % FENETRE_SUIVI) = ce seq est arrivé en avance */
    uint16_t maxSeq;           /* plus grand seq reçu */
    uint32_t dernierRx;        /* instant du dernier message (ms, horloge de la passerelle) */
    uint32_t compteur;         /* dernier compteur de pièces connu (pour le JSON machine) */
    uint16_t parent;
    uint8_t  sauts, vu, muet, enAlerte;
  } suivi_t;

  suivi_t suivi[MAX_ID + 1];
  bool premierDemarrage = TRUE;
  acquit_t acquit;

  /* Diffuse les acquittements : « voici, pour chacun, jusqu'où j'ai tout reçu » */
  void diffuserAcquits() {
    uint8_t i;
    acquit.battement++;
    for (i = 0; i <= MAX_ID; i++) acquit.dernier[i] = suivi[i].contigu;
    acquit.mac = macAcquit(&acquit, CLE_RESEAU);   /* signé, comme les rapports (ENF6) */
    call Acquit.change(&acquit);
  }
  event void Acquitter.fired() {
    diffuserAcquits();
    /* Une racine stable espace ses balises CTP jusqu'à plusieurs minutes (Trickle).
       Après une coupure, les nœuds ne la retrouveraient pas avant longtemps : on force
       une balise toutes les 30 s (la passerelle est sur secteur, le coût est négligeable). */
    call CtpInfo.triggerImmediateRouteUpdate();
    call Acquitter.startOneShot(TICKS(ACQUIT_MS));
  }

  /* Fenêtre circulaire : un bit par numéro de séquence « en avance » sur contigu */
  bool estVu(suivi_t *s, uint16_t seq) {
    uint16_t b = seq % FENETRE_SUIVI;
    return (s->vus[b / 8] >> (b % 8)) & 1;
  }
  void marquer(suivi_t *s, uint16_t seq, bool v) {
    uint16_t b = seq % FENETRE_SUIVI;
    if (v) s->vus[b / 8] |= (uint8_t)(1 << (b % 8));
    else   s->vus[b / 8] &= (uint8_t)~(1 << (b % 8));
  }

  /* Nombre de rapports manquants (trous) entre contigu et maxSeq */
  uint16_t manquants(suivi_t *s) {
    uint16_t n = 0, i;
    for (i = s->contigu + 1; i < s->maxSeq; i++)
      if (!estVu(s, i)) n++;
    return n;
  }

  /* ---------------------------------------------------------------- démarrage */
  event void Boot.booted() {
    call Console.texte("BOOT passerelle GW noeud ");
    call Console.nombre(TOS_NODE_ID);
    call Console.texte(" (racine CTP)\n");
#ifdef LOW_POWER_LISTENING
    /* Alimentée sur secteur : elle écoute en permanence (réveil local = 0) */
    call LowPowerListening.setLocalWakeupInterval(0);
#endif
    call RadioControl.start();
  }

  event void RadioControl.startDone(error_t err) {
    if (err != SUCCESS) { call RadioControl.start(); return; }
    if (premierDemarrage) {
      premierDemarrage = FALSE;
      call RoutingControl.start();
      call RootControl.setRoot();              /* « je suis la racine de l'arbre » */
      call DisseminationControl.start();
      call Acquitter.startOneShot(TICKS(2000)); /* premier battement vite, puis toutes les 30 s */
      call Stats.startPeriodic(TICKS(STATS_MS));
      call Supervision.startPeriodic(TICKS(5000));
      call Console.texte("PRET passerelle racine\n");
    }
  }

  event void RadioControl.stopDone(error_t err) {}

  /* ---------------------------------------------------------------- petites aides d'écriture */
  void ecrireNodeId(uint16_t src) {            /* MACHINE_02, POSTE_02, ZONE_02 */
    uint8_t f = FAMILLE[src];
    call Console.texte(f == FAM_TEMP ? "MACHINE_0" : f == FAM_COUNT ? "POSTE_0" : "ZONE_0");
    call Console.nombre(INDICE[src]);
  }

  void ecrireTopic(uint16_t src) {
    uint8_t f = FAMILLE[src];
    call Console.texte(f == FAM_TEMP ? "factory/machines/" :
                       f == FAM_COUNT ? "factory/production/" : "factory/security/");
    ecrireNodeId(src);
  }

  const char *texteEtat(uint8_t e) {
    switch (e) {
      case ETAT_OK: return "OK";
      case ETAT_ALERTE: return "ALERTE";
      case ETAT_FIN_ALERTE: return "OK";
      case ETAT_VEILLE: return "VEILLE";
      case ETAT_ARME: return "ARME";
      case ETAT_INTRUSION: return "INTRUSION";
      default: return "?";
    }
  }

  /* Le JSON du cahier des charges, adapté à chaque famille */
  void ecrireJson(rapport_t *r, uint32_t horodatage) {
    uint16_t src = r->source;
    call Console.texte("{\"node_id\":\"");   ecrireNodeId(src);
    call Console.texte("\",\"timestamp\":"); call Console.nombre(horodatage);
    if (r->type == TYPE_TEMPERATURE) {
      /* format exact du cahier : la température de la machine + le compteur du poste associé */
      uint8_t poste;
      uint32_t cpt = 0;
      for (poste = 1; poste <= MAX_ID; poste++)
        if (FAMILLE[poste] == FAM_COUNT && INDICE[poste] == INDICE[src]) cpt = suivi[poste].compteur;
      call Console.texte(",\"temperature_c\":"); call Console.dixiemes(r->valeur);
      call Console.texte(",\"production_count\":"); call Console.nombre(cpt);
    } else if (r->type == TYPE_COMPTAGE) {
      call Console.texte(",\"production_count\":"); call Console.nombre(r->compteur);
      call Console.texte(",\"cadence_ppm\":"); call Console.entier(r->valeur);
    } else {
      call Console.texte(",\"presence\":");
      call Console.texte(r->etat == ETAT_INTRUSION ? "true" : "false");
      call Console.texte(",\"detections\":"); call Console.nombre(r->compteur);
      call Console.texte(",\"heure\":\""); call Console.heure((uint16_t)r->valeur);
      call Console.car('"');
    }
    call Console.texte(",\"status\":\""); call Console.texte(texteEtat(r->etat));
    call Console.texte("\"}");
  }

  /* ---------------------------------------------------------------- réception */
  event message_t *Receive.receive(message_t *msg, void *payload, uint8_t len) {
    rapport_t *r = (rapport_t *) payload;
    uint32_t maintenant = EN_MS(call Stats.getNow());
    uint16_t src;
    suivi_t *s;
    uint8_t sauts;

    if (len != sizeof(rapport_t)) return msg;

    /* 1. Authentification : on recalcule le code avec NOTRE clé et on compare */
    if (calculerMac(r, CLE_RESEAU) != r->mac) {
      call Console.texte("REJET_AUTH origine=");
      call Console.nombre(call CtpPacket.getOrigin(msg));
      call Console.texte(" seq=");  call Console.nombre(r->seq);
      call Console.texte(" (code d'authentification invalide)\n");
      return msg;
    }
    /* Clé correcte, mais nœud absent du plan ou qui se fait passer pour un autre */
    if (r->source > MAX_ID || r->source != call CtpPacket.getOrigin(msg)) {
      call Console.texte("REJET_ORIGINE origine=");
      call Console.nombre(call CtpPacket.getOrigin(msg));
      call Console.texte(" source annoncee="); call Console.nombre(r->source);
      call Console.car('\n');
      return msg;
    }

    src = r->source;
    s = &suivi[src];
    /* THL (« time has lived ») : CTP l'augmente de 1 à chaque réception, y compris
       à la racine (CtpForwardingEngineP). C'est donc directement le nombre de sauts. */
    sauts = call CtpPacket.getThl(msg);

    /* 2. Suivi des numéros de séquence, avec trous possibles : un rapport perdu en route
          sera renvoyé plus tard par le capteur, faute d'acquittement. */
    if (s->vu && r->seq <= 2 && s->maxSeq > 4) {  /* le nœud a redémarré (seq repart de 1) */
      s->redemarrages++;
      call Console.texte("REDEMARRAGE src="); call Console.nombre(src);
      call Console.texte(" ("); call Console.texte(REPERE[src]); call Console.texte(")\n");
      s->contigu = 0; s->maxSeq = 0;
      memset(s->vus, 0, sizeof(s->vus));
    }
    if (r->seq <= s->contigu) { s->doublons++; return msg; }        /* déjà reçu */
    /* Trop en avance pour être suivi : on l'ignore SANS l'acquitter, le capteur le renverra.
       (Règle d'or : ne jamais acquitter un rapport qu'on n'a pas reçu.) */
    if (r->seq > s->contigu + FENETRE_SUIVI) return msg;
    if (estVu(s, r->seq)) { s->doublons++; return msg; }   /* déjà reçu (en avance) */
    marquer(s, r->seq, TRUE);
    while (estVu(s, s->contigu + 1)) {                       /* on comble les trous */
      s->contigu++;
      marquer(s, s->contigu, FALSE);
    }
    if (r->seq > s->maxSeq) s->maxSeq = r->seq;
    s->vu = 1;
    s->recus++;
    s->dernierRx = maintenant;
    s->parent = r->parent;
    s->sauts = sauts;
    if (r->type == TYPE_COMPTAGE) s->compteur = r->compteur;
    call Leds.led1Toggle();

    if (s->muet) {
      s->muet = 0;
      call Console.texte("NOEUD_RETABLI src="); call Console.nombre(src);
      call Console.texte(" ("); call Console.texte(REPERE[src]); call Console.texte(")\n");
    }

    /* 3. La ligne « message MQTT » */
    call Console.texte("RX src=");     call Console.nombre(src);
    call Console.texte(" seq=");       call Console.nombre(r->seq);
    call Console.texte(" sauts=");     call Console.nombre(sauts);
    call Console.texte(" parent=");    call Console.nombre(r->parent);
    call Console.texte(" age=");       call Console.nombre(r->age_ms);
    call Console.texte(" diff=");      call Console.nombre(r->differe);
    call Console.texte(" | ");         ecrireTopic(src);
    call Console.car(' ');
    ecrireJson(r, EPOCH_DEBUT + (maintenant - r->age_ms) / 1000UL);
    call Console.car('\n');

    /* 4. Décision d'alerte (B3) */
    if (r->type == TYPE_TEMPERATURE) {
      int16_t seuil = SEUIL_DIXIEMES[INDICE[src]];
      if (r->valeur > seuil && !s->enAlerte) {
        s->enAlerte = 1;
        call Leds.led2On();                      /* LED bleue = alerte en cours */
        call Console.texte("ALERTE SURCHAUFFE "); ecrireNodeId(src);
        call Console.texte(" ("); call Console.texte(NOM_MACHINE[INDICE[src]]);
        call Console.texte(") temp="); call Console.dixiemes(r->valeur);
        call Console.texte(" seuil=");  call Console.dixiemes(seuil);
        call Console.texte(" src=");    call Console.nombre(src);
        call Console.texte(" seq=");    call Console.nombre(r->seq);
        call Console.car('\n');
      } else if (s->enAlerte && r->valeur <= seuil - HYSTERESIS_DIXIEMES) {
        s->enAlerte = 0;
        call Leds.led2Off();
        call Console.texte("FIN_ALERTE SURCHAUFFE "); ecrireNodeId(src);
        call Console.texte(" temp="); call Console.dixiemes(r->valeur);
        call Console.car('\n');
      }
    } else if (r->type == TYPE_PRESENCE && r->etat == ETAT_INTRUSION && !r->differe) {
      call Console.texte("ALERTE INTRUSION "); ecrireNodeId(src);
      call Console.texte(" heure="); call Console.heure((uint16_t)r->valeur);
      call Console.texte(" src=");   call Console.nombre(src);
      call Console.texte(" seq=");   call Console.nombre(r->seq);
      call Console.car('\n');
    }
    return msg;
  }

  /* ---------------------------------------------------------------- supervision (ENF8) */
  event void Supervision.fired() {
    uint8_t i;
    uint32_t maintenant = EN_MS(call Supervision.getNow());
    for (i = 2; i <= MAX_ID; i++) {
      suivi_t *s = &suivi[i];
      if (s->vu && !s->muet && maintenant - s->dernierRx > SILENCE_MS) {
        s->muet = 1;
        call Console.texte("ALERTE NOEUD_MUET src="); call Console.nombre(i);
        call Console.texte(" ("); call Console.texte(REPERE[i]);
        call Console.texte(") silence="); call Console.nombre((maintenant - s->dernierRx) / 1000UL);
        call Console.texte(" s\n");
      }
    }
  }

  void ecrireStats() {
    uint8_t i;
    for (i = 2; i <= MAX_ID; i++) {
      suivi_t *s = &suivi[i];
      if (!s->vu) continue;             /* nœud jamais entendu (absent du scénario) */
      call Console.texte("STAT src=");   call Console.nombre(i);
      call Console.car(' ');             call Console.texte(REPERE[i]);
      call Console.texte(" recus=");     call Console.nombre(s->recus);
      call Console.texte(" manquants="); call Console.nombre(manquants(s));
      call Console.texte(" doublons=");  call Console.nombre(s->doublons);
      call Console.texte(" acquitte=");  call Console.nombre(s->contigu);
      call Console.texte(" sauts=");     call Console.nombre(s->sauts);
      call Console.texte(" parent=");    call Console.nombre(s->parent);
      call Console.texte(s->muet ? " MUET\n" : "\n");
    }
  }

  event void Stats.fired() { ecrireStats(); }

  /* ---------------------------------------------------------------- commandes du banc d'essai */
  event void Console.commande(char c) {
    if (c == 'S') ecrireStats();
  }
}
