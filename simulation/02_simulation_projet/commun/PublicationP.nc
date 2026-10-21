/*
 * MODULE PublicationP : envoi FIABLE des rapports d'un nœud capteur.
 *
 * 1. Démarrage : radio, puis routage CTP et Drip, puis on prévient l'application (pret).
 * 2. publier() range le rapport dans un TAMPON circulaire et écrit « PUB seq=... » :
 *    c'est l'instant de référence pour mesurer la latence.
 * 3. La tâche envoyer() confie à CTP, dans l'ordre, les rapports pas encore envoyés.
 * 4. Un rapport ne quitte le tampon que lorsque la PASSERELLE l'a acquitté (acquittement
 *    de bout en bout diffusé par Drip toutes les 30 s). L'accusé de réception de CTP ne
 *    suffit pas : il prouve seulement que le VOISIN a reçu le paquet. Si la passerelle
 *    disparaît, les voisins se renvoient les paquets en boucle et finissent par les jeter.
 * 5. Plus d'acquittement depuis 75 s ? Le nœud se déclare HORS LIGNE : il arrête d'émettre
 *    et garde tout (ENF3). Au retour des acquittements, il renvoie ce qui manque (T7).
 * 6. Chaque seconde, on regarde quel est notre parent CTP. S'il change, on l'écrit
 *    (« PARENT 2->9 ») : c'est ainsi qu'on mesure la reconvergence (T9 / ENF8).
 */
#include "Usine.h"

module PublicationP {
  provides interface Publication;
  uses {
    interface Boot;
    interface SplitControl as RadioControl;
    interface StdControl as RoutingControl;
    interface StdControl as DisseminationControl;
    interface Send;
    interface CtpInfo;
    interface DisseminationValue<acquit_t> as Acquit;
    interface Timer<TMilli> as Surveillance;
    interface Timer<TMilli> as Reessai;
    interface Console;
    interface Leds;
  }
}
implementation {
  /* Une case du tampon : ce qu'il faut pour reconstruire le rapport au moment de l'envoi */
  typedef struct {
    uint8_t  type, etat;
    uint16_t seq;
    uint32_t t_ms;        /* instant de la mesure (horloge locale, vraies ms) */
    uint32_t t_envoi;     /* dernier envoi (pour savoir quand renvoyer) */
    int16_t  valeur;
    uint32_t compteur;
  } entree_t;

  /* Le tampon contient, dans l'ordre : [ envoyés non acquittés | pas encore envoyés ] */
  entree_t tampon[CAPACITE_TAMPON];
  uint8_t  debut = 0, nb = 0;          /* file circulaire : premier élément et nombre */
  uint8_t  envoyes = 0;                /* parmi les nb, combien sont déjà partis */
  uint16_t seq = 0;
  message_t paquet;
  bool occupe = FALSE;                 /* un envoi CTP est en cours */
  bool enLigne = FALSE;                /* la passerelle répond (acquittements reçus) */
  uint32_t dernierAcquit = 0;
  am_addr_t dernierParent = 0xFFFF;

  task void envoyer();

  uint32_t maintenant() { return EN_MS(call Surveillance.getNow()); }
  entree_t *entree(uint8_t i) { return &tampon[(debut + i) % CAPACITE_TAMPON]; }

  /* ---------------------------------------------------------------- démarrage */
  event void Boot.booted() {
    call RadioControl.start();
  }

  event void RadioControl.startDone(error_t err) {
    if (err != SUCCESS) { call RadioControl.start(); return; }
    call RoutingControl.start();                 /* CTP commence à écouter / annoncer */
    call DisseminationControl.start();           /* Drip : prêt à recevoir les acquittements */
    call Surveillance.startPeriodic(TICKS(SURVEILLANCE_MS));
    signal Publication.pret();
  }
  event void RadioControl.stopDone(error_t err) {}

  /* ---------------------------------------------------------------- publication */
  command uint16_t Publication.publier(uint8_t type, uint8_t etat, int16_t valeur, uint32_t compteur) {
    entree_t *e;
    if (nb == CAPACITE_TAMPON) {                 /* tampon plein : on sacrifie le plus ancien */
      if (occupe && envoyes == 0) return seq;    /* (sauf s'il est en cours d'envoi) */
      debut = (debut + 1) % CAPACITE_TAMPON;
      nb--;
      if (envoyes > 0) envoyes--;
      call Console.texte("TAMPON_PLEIN : rapport le plus ancien perdu\n");
    }
    e = entree(nb);
    e->type = type; e->etat = etat; e->seq = ++seq;
    e->t_ms = maintenant(); e->t_envoi = 0;
    e->valeur = valeur; e->compteur = compteur;
    nb++;

    call Console.texte("PUB seq=");     call Console.nombre(seq);
    call Console.texte(" type=");       call Console.nombre(type);
    call Console.texte(" etat=");       call Console.nombre(etat);
    call Console.texte(" val=");        call Console.entier(valeur);
    call Console.texte(" cpt=");        call Console.nombre(compteur);
    call Console.texte(" attente=");    call Console.nombre(nb);
    call Console.texte(enLigne ? "\n" : " HORS_LIGNE\n");

    post envoyer();
    return seq;
  }

  command uint8_t Publication.enAttente() { return nb; }

  /* ---------------------------------------------------------------- envoi */
  task void envoyer() {
    rapport_t *r;
    entree_t *e;
    am_addr_t parent = 0xFFFF;
    uint16_t etx = 0xFFFF;
    uint32_t age;

    if (occupe || !enLigne || envoyes >= nb) return;
    r = (rapport_t *) call Send.getPayload(&paquet, sizeof(rapport_t));
    if (r == NULL) return;
    e = entree(envoyes);
    call CtpInfo.getParent(&parent);
    call CtpInfo.getEtx(&etx);
    age = maintenant() - e->t_ms;

    r->type = e->type;       r->etat = e->etat;
    r->source = TOS_NODE_ID; r->seq = e->seq;
    r->age_ms = age;         r->valeur = e->valeur;
    r->compteur = e->compteur;
    r->parent = parent;      r->etx = etx;
    r->differe = (age > 5000UL) ? 1 : 0;       /* a attendu plus de 5 s dans le tampon */
    r->mac = calculerMac(r, CLE_RESEAU);       /* signature calculée en dernier */

    if (call Send.send(&paquet, sizeof(rapport_t)) == SUCCESS) {
      occupe = TRUE;
      e->t_envoi = maintenant();
    } else {
      call Reessai.startOneShot(TICKS(REESSAI_MS));
    }
  }

  event void Send.sendDone(message_t *m, error_t err) {
    if (m != &paquet) return;
    occupe = FALSE;
    if (err == SUCCESS) {
      if (enLigne && envoyes < nb) envoyes++;  /* parti, mais gardé jusqu'à l'acquittement */
      call Leds.led1Toggle();                  /* LED verte = un rapport est parti */
      /* Le suivant : tout de suite s'il est frais (une alerte ne doit pas attendre),
         au rythme de vidage s'il attendait depuis une coupure. */
      if (envoyes < nb && maintenant() - entree(envoyes)->t_ms > 5000UL)
        call Reessai.startOneShot(TICKS(RYTHME_VIDAGE_MS));
      else
        post envoyer();
    } else {
      call Console.texte("ECHEC_ENVOI seq=");
      call Console.nombre(entree(envoyes)->seq);
      call Console.car('\n');
      call Reessai.startOneShot(TICKS(REESSAI_MS));
    }
  }

  event void Reessai.fired() { post envoyer(); }

  /* ---------------------------------------------------------------- acquittements */
  event void Acquit.changed() {
    const acquit_t *a = call Acquit.get();
    uint16_t ok = (TOS_NODE_ID <= MAX_ID) ? a->dernier[TOS_NODE_ID] : 0;
    uint8_t liberes = 0;

    /* Acquittement non signé par la passerelle (paquet altéré ou falsifié) : on l'ignore,
       sinon on effacerait des rapports que la passerelle n'a jamais reçus. */
#ifndef INTRUS   /* le nœud intrus du test ENF6 ne respecte pas le protocole : il émet quand même */
    if (macAcquit(a, CLE_RESEAU) != a->mac) {
      call Console.texte("ACQUIT_REJETE code d'authentification invalide\n");
      return;
    }
#endif
    dernierAcquit = maintenant();
    call Console.texte("ACQUIT battement="); call Console.nombre(a->battement);
    call Console.texte(" ok=");              call Console.nombre(ok);
    call Console.car('\n');
    if (!enLigne) {
      enLigne = TRUE;
      call Console.texte("EN_LIGNE acquittements recus, ");
      call Console.nombre(nb);
      call Console.texte(" rapport(s) a envoyer\n");
    }
    /* On oublie tous les rapports que la passerelle a bien reçus */
    while (nb > 0 && entree(0)->seq <= ok && !(occupe && envoyes == 0)) {
      debut = (debut + 1) % CAPACITE_TAMPON;
      nb--;
      if (envoyes > 0) envoyes--;
      liberes++;
    }
    /* Le plus ancien rapport envoyé n'est toujours pas acquitté : il s'est perdu en route
       (nœud relais tombé, boucle de routage...). On renvoie à partir de lui. */
    if (!occupe && envoyes > 0 && maintenant() - entree(0)->t_envoi > RENVOI_MS) {
      call Console.texte("RENVOI a partir de seq="); call Console.nombre(entree(0)->seq);
      call Console.texte(" ("); call Console.nombre(envoyes);
      call Console.texte(" non acquitte(s))\n");
      envoyes = 0;
    }
    post envoyer();
  }

  /* ---------------------------------------------------------------- surveillance */
  event void Surveillance.fired() {
    am_addr_t parent;
    uint16_t etx = 0;

    /* Passerelle silencieuse trop longtemps : stockage local */
    if (enLigne && maintenant() - dernierAcquit > HORS_LIGNE_MS) {
      enLigne = FALSE;
      envoyes = 0;                     /* tout ce qui n'est pas acquitté sera renvoyé */
      call Console.texte("HORS_LIGNE plus d'acquittement depuis ");
      call Console.nombre(HORS_LIGNE_MS / 1000);
      call Console.texte(" s : stockage local\n");
    }

    if (call CtpInfo.getParent(&parent) != SUCCESS) parent = 0xFFFF;
    if (parent != dernierParent) {
      call CtpInfo.getEtx(&etx);
      call Console.texte("PARENT ");
      if (dernierParent == 0xFFFF) call Console.texte("aucun"); else call Console.nombre(dernierParent);
      call Console.texte("->");
      if (parent == 0xFFFF) call Console.texte("aucun"); else call Console.nombre(parent);
      call Console.texte(" etx=");
      call Console.nombre(etx);
      call Console.texte("\n");
      dernierParent = parent;
    }
  }

  event void Console.commande(char c) {}     /* les commandes sont pour l'application */
}
