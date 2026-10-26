/*
 * Service de publication des nœuds capteurs, version Contiki-NG.
 *
 * TinyOS (CTP)                          Contiki-NG (RPL + UDP)
 * ------------------------------------  ------------------------------------------------
 * CTP construit l'arbre de collecte     RPL construit un DODAG dont la passerelle est la racine
 * Send.send() vers la collecte          simple_udp_sendto() vers l'adresse IPv6 de la racine
 * sendDone(SUCCESS) = accusé du voisin  UDP n'accuse rien : la PASSERELLE renvoie un
 *                                       acquittement signé (comme le mode confirmable de CoAP)
 * CtpInfo.getParent()                   curr_instance.dag.preferred_parent (RPL-Lite)
 *
 * Fonctionnement :
 *  1. publier() range le rapport dans le tampon et écrit « PUB seq=... » (instant de référence
 *     pour la latence).
 *  2. Dès que RPL dit que la racine est joignable, on envoie le plus ancien rapport.
 *  3. On attend son acquittement 3 s au plus ; sans réponse, on le renvoie. Il ne quitte le
 *     tampon qu'une fois acquitté : rien n'est perdu pendant une reconvergence (ENF8).
 *  4. Chaque seconde, on regarde le parent RPL ; s'il change, on écrit « PARENT a->b ».
 */
#include "publication.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"
#include "net/ipv6/simple-udp.h"
#include "sys/node-id.h"
#include "dev/leds.h"
#include <stdio.h>
#include <string.h>

typedef struct {
  uint8_t  type, etat;
  uint16_t seq;
  uint32_t t_ms;        /* instant de la mesure */
  int16_t  valeur;
  uint32_t compteur;
} entree_t;

static entree_t tampon[CAPACITE_TAMPON];
static uint8_t  debut, nb;            /* file circulaire */
static uint16_t seq;
static bool     en_vol;               /* un rapport attend son acquittement */
static uint16_t dernier_parent = 0xFFFF;
static struct simple_udp_connection conn;

PROCESS(publication_process, "publication");

/* ---------------------------------------------------------------- RPL : notre parent */
static uint16_t
parent_actuel(void)
{
  if(curr_instance.used && curr_instance.dag.preferred_parent != NULL) {
    uip_ipaddr_t *a = rpl_neighbor_get_ipaddr(curr_instance.dag.preferred_parent);
    if(a != NULL) {
      return a->u8[15];            /* sur un Cooja mote, le dernier octet = numéro du nœud */
    }
  }
  return 0xFFFF;
}

/* ---------------------------------------------------------------- envoi du plus ancien */
static void
envoyer(void)
{
  rapport_t r;
  uip_ipaddr_t racine;
  entree_t *e;

  if(en_vol || nb == 0) {
    return;
  }
  if(!NETSTACK_ROUTING.node_is_reachable() || !NETSTACK_ROUTING.get_root_ipaddr(&racine)) {
    return;                        /* pas encore de route : on réessaiera à la seconde suivante */
  }
  e = &tampon[debut];
  r.type = e->type;
  r.etat = e->etat;
  r.source = node_id;
  r.seq = e->seq;
  r.age_ms = maintenant_ms() - e->t_ms;
  r.valeur = e->valeur;
  r.compteur = e->compteur;
  r.parent = parent_actuel();
  r.rang = curr_instance.used ? curr_instance.dag.rank : 0xFFFF;
  r.mac = MAC_RAPPORT(&r);         /* signature calculée en dernier (ENF6) */

  simple_udp_sendto(&conn, &r, sizeof(r), &racine);
  en_vol = true;
  leds_toggle(LEDS_GREEN);         /* LED verte = un rapport est parti */
  process_post(&publication_process, PROCESS_EVENT_CONTINUE, NULL);  /* arme l'attente */
}

/* ---------------------------------------------------------------- acquittement reçu */
static void
reception(struct simple_udp_connection *c, const uip_ipaddr_t *expediteur, uint16_t port_exp,
          const uip_ipaddr_t *destinataire, uint16_t port_dest,
          const uint8_t *donnees, uint16_t taille)
{
  acquit_t a;
  if(taille != sizeof(acquit_t)) {
    return;
  }
  memcpy(&a, donnees, sizeof(a));
#ifndef INTRUS   /* l'intrus du test ENF6 ne vérifie rien */
  if(MAC_ACQUIT(&a) != a.mac) {
    printf("ACQUIT_REJETE code d'authentification invalide\n");
    return;
  }
#endif
  if(en_vol && nb > 0 && tampon[debut].seq == a.seq) {
    debut = (debut + 1) % CAPACITE_TAMPON;   /* reçu par la passerelle : on l'oublie */
    nb--;
    en_vol = false;
    envoyer();                               /* et on enchaîne avec le suivant */
  }
}

/* ---------------------------------------------------------------- API */
uint16_t
publier(uint8_t type, uint8_t etat, int16_t valeur, uint32_t compteur)
{
  entree_t *e;
  if(nb == CAPACITE_TAMPON) {                /* tampon plein : on sacrifie le plus ancien */
    debut = (debut + 1) % CAPACITE_TAMPON;
    nb--;
    en_vol = false;
    printf("TAMPON_PLEIN : rapport le plus ancien perdu\n");
  }
  e = &tampon[(debut + nb) % CAPACITE_TAMPON];
  e->type = type;
  e->etat = etat;
  e->seq = ++seq;
  e->t_ms = maintenant_ms();
  e->valeur = valeur;
  e->compteur = compteur;
  nb++;
  printf("PUB seq=%u type=%u etat=%u val=%d cpt=%lu attente=%u\n",
         seq, type, etat, valeur, (unsigned long)compteur, nb);
  envoyer();
  return seq;
}

void
publication_reinitialiser(void)
{
  debut = nb = 0;
  seq = 0;
  en_vol = false;
}

void
publication_demarrer(void)
{
  simple_udp_register(&conn, PORT_CAPTEUR, NULL, PORT_PASSERELLE, reception);
  process_start(&publication_process, NULL);
}

/* ---------------------------------------------------------------- processus : renvois + parent
   Un « processus » Contiki est une fonction qui s'arrête sur PROCESS_WAIT_EVENT et reprend
   quand un événement arrive (minuterie, message...) : l'équivalent des événements nesC. */
PROCESS_THREAD(publication_process, ev, data)
{
  static struct etimer surveillance, attente;

  PROCESS_BEGIN();
  etimer_set(&surveillance, MS(SURVEILLANCE_MS));
  while(1) {
    PROCESS_WAIT_EVENT();

    if(ev == PROCESS_EVENT_CONTINUE) {       /* un rapport vient de partir */
      etimer_set(&attente, MS(ATTENTE_ACK_MS));
    } else if(ev == PROCESS_EVENT_TIMER && data == &attente) {
      if(en_vol) {                           /* pas d'acquittement : on renvoie */
        en_vol = false;
        envoyer();
      }
    } else if(ev == PROCESS_EVENT_TIMER && data == &surveillance) {
      uint16_t p = parent_actuel();
      if(p != dernier_parent) {
        if(dernier_parent == 0xFFFF) printf("PARENT aucun->"); else printf("PARENT %u->", dernier_parent);
        if(p == 0xFFFF) printf("aucun"); else printf("%u", p);
        printf(" rang=%u\n", curr_instance.used ? curr_instance.dag.rank : 0);
        dernier_parent = p;
      }
      envoyer();                             /* au cas où une route vient d'apparaître */
      etimer_reset(&surveillance);
    }
  }
  PROCESS_END();
}
