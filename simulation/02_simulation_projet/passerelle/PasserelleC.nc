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
 *
 * Commande série (banc d'essai) : S = statistiques tout de suite.
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
    interface Timer<TMilli> as Stats;
    interface Timer<TMilli> as Supervision;
  }
}
implementation {
  /* Ce que la passerelle retient de chaque nœud */
  typedef struct {
    uint16_t recus, perdus, doublons, dernierSeq, redemarrages;
    uint32_t dernierRx;        /* instant du dernier message (ms, horloge de la passerelle) */
    uint32_t compteur;         /* dernier compteur de pièces connu (pour le JSON machine) */
    uint16_t parent;
    uint8_t  sauts, vu, muet, enAlerte;
  } suivi_t;

  suivi_t suivi[MAX_ID + 1];

  /* ---------------------------------------------------------------- démarrage */
  event void Boot.booted() {
    call Console.texte("BOOT passerelle GW noeud ");
    call Console.nombre(TOS_NODE_ID);
    call Console.texte(" (racine CTP)\n");
    call RadioControl.start();
  }

  event void RadioControl.startDone(error_t err) {
    if (err != SUCCESS) { call RadioControl.start(); return; }
    call RoutingControl.start();
    call RootControl.setRoot();                /* « je suis la racine de l'arbre » */
    call Stats.startPeriodic(TICKS(STATS_MS));
    call Supervision.startPeriodic(TICKS(5000));
    call Console.texte("PRET passerelle racine\n");
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

    /* 2. Suivi des numéros de séquence : un trou = rapports perdus, un numéro déjà vu = doublon */
    if (s->vu && r->seq <= s->dernierSeq) {
      if (r->seq <= 2) {                         /* le nœud a redémarré (seq repart de 1) */
        s->redemarrages++;
        call Console.texte("REDEMARRAGE src="); call Console.nombre(src);
        call Console.texte(" ("); call Console.texte(REPERE[src]); call Console.texte(")\n");
        s->dernierSeq = r->seq - 1;
      } else {
        s->doublons++;
        return msg;                              /* déjà reçu : on l'ignore */
      }
    }
    if (s->vu && r->seq > s->dernierSeq + 1) s->perdus += r->seq - s->dernierSeq - 1;
    if (!s->vu && r->seq > 1) s->perdus += r->seq - 1;
    s->vu = 1;
    s->dernierSeq = r->seq;
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
    } else if (r->type == TYPE_PRESENCE && r->etat == ETAT_INTRUSION) {
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
      call Console.texte(" perdus=");    call Console.nombre(s->perdus);
      call Console.texte(" doublons=");  call Console.nombre(s->doublons);
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
