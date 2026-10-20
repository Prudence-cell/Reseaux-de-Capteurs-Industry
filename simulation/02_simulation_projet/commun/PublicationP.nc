/*
 * MODULE PublicationP : envoi fiable des rapports d'un nœud capteur.
 *
 * 1. Démarrage : radio, puis routage CTP, puis on prévient l'application (pret).
 * 2. publier() range le rapport dans un TAMPON circulaire (file d'attente) et
 *    écrit « PUB seq=... » : c'est l'instant de référence pour mesurer la latence.
 * 3. La tâche envoyer() prend le plus ancien rapport du tampon et le confie à CTP.
 *    Le rapport n'est retiré du tampon que si CTP confirme l'envoi (sendDone SUCCESS).
 *    En cas d'échec (passerelle coupée, plus de route...), on réessaie plus tard :
 *    les rapports s'accumulent et repartent tous au retour du réseau (ENF3 / T7).
 * 4. Chaque seconde, on regarde quel est notre parent CTP. S'il change, on l'écrit
 *    (« PARENT 2->9 ») : c'est ainsi qu'on mesure la reconvergence (T9 / ENF8).
 */
#include "Usine.h"

module PublicationP {
  provides interface Publication;
  uses {
    interface Boot;
    interface SplitControl as RadioControl;
    interface StdControl as RoutingControl;
    interface Send;
    interface CtpInfo;
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
    uint32_t t_ms;        /* instant de la mesure (horloge locale) */
    int16_t  valeur;
    uint32_t compteur;
  } entree_t;

  entree_t tampon[CAPACITE_TAMPON];
  uint8_t  debut = 0, nb = 0;          /* file circulaire : premier élément et nombre */
  uint16_t seq = 0;
  uint16_t perdusTampon = 0;           /* rapports écrasés si le tampon déborde */
  message_t paquet;
  bool occupe = FALSE;                 /* un envoi CTP est en cours */
  am_addr_t dernierParent = 0xFFFF;

  task void envoyer();

  /* ---------------------------------------------------------------- démarrage */
  event void Boot.booted() {
    call RadioControl.start();
  }

  event void RadioControl.startDone(error_t err) {
    if (err != SUCCESS) { call RadioControl.start(); return; }
    call RoutingControl.start();                 /* CTP commence à écouter / annoncer */
    call Surveillance.startPeriodic(TICKS(SURVEILLANCE_MS));
    signal Publication.pret();
  }
  event void RadioControl.stopDone(error_t err) {}

  /* ---------------------------------------------------------------- publication */
  command uint16_t Publication.publier(uint8_t type, uint8_t etat, int16_t valeur, uint32_t compteur) {
    entree_t *e;
    if (nb == CAPACITE_TAMPON) {                 /* tampon plein : on sacrifie le plus ancien */
      debut = (debut + 1) % CAPACITE_TAMPON;
      nb--;
      perdusTampon++;
    }
    e = &tampon[(debut + nb) % CAPACITE_TAMPON];
    e->type = type; e->etat = etat; e->seq = ++seq;
    e->t_ms = EN_MS(call Surveillance.getNow());
    e->valeur = valeur; e->compteur = compteur;
    nb++;

    call Console.texte("PUB seq=");     call Console.nombre(seq);
    call Console.texte(" type=");       call Console.nombre(type);
    call Console.texte(" etat=");       call Console.nombre(etat);
    call Console.texte(" val=");        call Console.entier(valeur);
    call Console.texte(" cpt=");        call Console.nombre(compteur);
    call Console.texte(" attente=");    call Console.nombre(nb);
    call Console.texte("\n");

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

    if (occupe || nb == 0) return;
    r = (rapport_t *) call Send.getPayload(&paquet, sizeof(rapport_t));
    if (r == NULL) return;
    e = &tampon[debut];
    call CtpInfo.getParent(&parent);
    call CtpInfo.getEtx(&etx);
    age = EN_MS(call Surveillance.getNow()) - e->t_ms;

    r->type = e->type;      r->etat = e->etat;
    r->source = TOS_NODE_ID; r->seq = e->seq;
    r->age_ms = age;        r->valeur = e->valeur;
    r->compteur = e->compteur;
    r->parent = parent;     r->etx = etx;
    r->differe = (age > 5000UL) ? 1 : 0;      /* a attendu plus de 5 s dans le tampon */
    r->mac = calculerMac(r, CLE_RESEAU);      /* signature calculée en dernier */

    if (call Send.send(&paquet, sizeof(rapport_t)) == SUCCESS) {
      occupe = TRUE;
    } else {
      call Reessai.startOneShot(TICKS(REESSAI_MS));
    }
  }

  event void Send.sendDone(message_t *m, error_t err) {
    if (m != &paquet) return;
    occupe = FALSE;
    if (err == SUCCESS) {
      debut = (debut + 1) % CAPACITE_TAMPON;  /* rapport livré au saut suivant : on l'oublie */
      nb--;
      call Leds.led1Toggle();                 /* LED verte = un rapport est parti */
      post envoyer();                         /* et on enchaîne avec le suivant */
    } else {
      call Console.texte("ECHEC_ENVOI seq=");
      call Console.nombre(tampon[debut].seq);
      call Console.texte(" attente=");
      call Console.nombre(nb);
      call Console.texte("\n");
      call Reessai.startOneShot(TICKS(REESSAI_MS));
    }
  }

  event void Reessai.fired() { post envoyer(); }

  /* ---------------------------------------------------------------- surveillance du parent */
  event void Surveillance.fired() {
    am_addr_t parent;
    uint16_t etx = 0;
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
      if (parent != 0xFFFF) post envoyer();
    }
  }

  event void Console.commande(char c) {}     /* les commandes sont pour l'application */
}
