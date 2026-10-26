/*
 * PASSERELLE (nœud 1 = GW du plan) — version Contiki-NG.
 * Racine du réseau RPL et serveur UDP. Traduction de PasserelleC.nc (TinyOS).
 *
 * Pour chaque rapport reçu :
 *   1. vérifie le code d'authentification (ENF6) ; sinon « REJET_AUTH » ;
 *   2. renvoie un acquittement signé au capteur (il peut alors effacer le rapport) ;
 *   3. met à jour le suivi du nœud (reçus, perdus, doublons) → taux de livraison ;
 *   4. écrit « RX ... | topic {json} » : le message MQTT qu'elle publierait ;
 *   5. décide des ALERTES : surchauffe (EF2), intrusion hors heures (EF6), nœud muet (ENF8).
 * Toutes les 60 s : une ligne « STAT » par nœud. Commande série : S = statistiques.
 */
#include "contiki.h"
#include "net/routing/routing.h"
#include "net/ipv6/simple-udp.h"
#include "net/ipv6/uip.h"
#include "dev/serial-line.h"
#include "dev/leds.h"
#include "sys/node-id.h"
#include "usine.h"
#include <stdio.h>
#include <string.h>

typedef struct {
  uint16_t recus, perdus, doublons, dernier_seq, redemarrages;
  uint32_t dernier_rx;       /* instant du dernier rapport (ms) */
  uint32_t compteur;         /* dernier compteur de pièces (pour le JSON machine) */
  uint16_t parent;
  uint8_t  sauts, vu, muet, en_alerte;
} suivi_t;

static suivi_t suivi[MAX_ID + 1];
static struct simple_udp_connection conn;

PROCESS(passerelle_process, "passerelle");
AUTOSTART_PROCESSES(&passerelle_process);

/* ---------------------------------------------------------------- petites aides d'écriture */
static const char *
prefixe_id(uint16_t src)
{
  uint8_t f = FAMILLE[src];
  return f == FAM_TEMP ? "MACHINE_0" : f == FAM_COUNT ? "POSTE_0" : "ZONE_0";
}
static const char *
prefixe_topic(uint16_t src)
{
  uint8_t f = FAMILLE[src];
  return f == FAM_TEMP ? "factory/machines/" : f == FAM_COUNT ? "factory/production/" : "factory/security/";
}
static const char *
texte_etat(uint8_t e)
{
  switch(e) {
  case ETAT_OK: case ETAT_FIN_ALERTE: return "OK";
  case ETAT_ALERTE: return "ALERTE";
  case ETAT_VEILLE: return "VEILLE";
  case ETAT_ARME: return "ARME";
  case ETAT_INTRUSION: return "INTRUSION";
  default: return "?";
  }
}

/* Le JSON du cahier des charges, adapté à chaque famille */
static void
ecrire_json(const rapport_t *r, uint32_t horodatage)
{
  uint16_t src = r->source;
  printf("{\"node_id\":\"%s%u\",\"timestamp\":%lu", prefixe_id(src), INDICE[src],
         (unsigned long)horodatage);
  if(r->type == TYPE_TEMPERATURE) {
    /* format exact du cahier : température de la machine + compteur du poste associé */
    uint32_t cpt = 0;
    uint8_t p;
    for(p = 1; p <= MAX_ID; p++) {
      if(FAMILLE[p] == FAM_COUNT && INDICE[p] == INDICE[src]) cpt = suivi[p].compteur;
    }
    printf(",\"temperature_c\":%d.%d,\"production_count\":%lu", DIXIEMES(r->valeur), (unsigned long)cpt);
  } else if(r->type == TYPE_COMPTAGE) {
    printf(",\"production_count\":%lu,\"cadence_ppm\":%d", (unsigned long)r->compteur, r->valeur);
  } else {
    printf(",\"presence\":%s,\"detections\":%lu,\"heure\":\"%02d:%02d\"",
           r->etat == ETAT_INTRUSION ? "true" : "false", (unsigned long)r->compteur, HHMM(r->valeur));
  }
  printf(",\"status\":\"%s\"}", texte_etat(r->etat));
}

/* ---------------------------------------------------------------- réception d'un rapport */
static void
reception(struct simple_udp_connection *c, const uip_ipaddr_t *expediteur, uint16_t port_exp,
          const uip_ipaddr_t *destinataire, uint16_t port_dest,
          const uint8_t *donnees, uint16_t taille)
{
  rapport_t r;
  acquit_t a;
  suivi_t *s;
  uint16_t src, origine = expediteur->u8[15];
  /* Le champ « hop limit » d'IPv6 part de 64 et perd 1 à chaque relais (RPL) */
  uint8_t sauts = UIP_TTL - UIP_IP_BUF->ttl + 1;
  uint32_t t = maintenant_ms();

  if(taille != sizeof(rapport_t)) {
    return;
  }
  memcpy(&r, donnees, sizeof(r));

  /* 1. Authentification : on recalcule le code avec NOTRE clé et on compare */
  if(MAC_RAPPORT(&r) != r.mac) {
    printf("REJET_AUTH origine=%u seq=%u (code d'authentification invalide)\n", origine, r.seq);
    return;
  }
  if(r.source > MAX_ID || r.source != origine) {
    printf("REJET_ORIGINE origine=%u source annoncee=%u\n", origine, r.source);
    return;
  }

  /* 2. Acquittement signé, même pour un doublon (le capteur l'a peut-être renvoyé) */
  a.seq = r.seq;
  a.mac = MAC_ACQUIT(&a);
  simple_udp_sendto(&conn, &a, sizeof(a), expediteur);

  /* 3. Suivi des numéros de séquence */
  src = r.source;
  s = &suivi[src];
  if(s->vu && r.seq <= s->dernier_seq) {
    if(r.seq <= 2) {                         /* le nœud a redémarré (seq repart de 1) */
      s->redemarrages++;
      printf("REDEMARRAGE src=%u (%s)\n", src, REPERE[src]);
      s->dernier_seq = r.seq - 1;
    } else {
      s->doublons++;
      return;                                /* déjà reçu : on l'ignore */
    }
  }
  if(s->vu && r.seq > s->dernier_seq + 1) s->perdus += r.seq - s->dernier_seq - 1;
  if(!s->vu && r.seq > 1) s->perdus += r.seq - 1;
  s->vu = 1;
  s->dernier_seq = r.seq;
  s->recus++;
  s->dernier_rx = t;
  s->parent = r.parent;
  s->sauts = sauts;
  if(r.type == TYPE_COMPTAGE) s->compteur = r.compteur;
  leds_toggle(LEDS_GREEN);

  if(s->muet) {
    s->muet = 0;
    printf("NOEUD_RETABLI src=%u (%s)\n", src, REPERE[src]);
  }

  /* 4. La ligne « message MQTT » */
  printf("RX src=%u seq=%u sauts=%u parent=%u age=%lu | %s%s%u ", src, r.seq, sauts, r.parent,
         (unsigned long)r.age_ms, prefixe_topic(src), prefixe_id(src), INDICE[src]);
  ecrire_json(&r, EPOCH_DEBUT + (t - r.age_ms) / 1000UL);
  printf("\n");

  /* 5. Décision d'alerte */
  if(r.type == TYPE_TEMPERATURE) {
    int16_t seuil = SEUIL_DIXIEMES[INDICE[src]];
    if(r.valeur > seuil && !s->en_alerte) {
      s->en_alerte = 1;
      leds_on(LEDS_BLUE);                    /* LED bleue = alerte en cours */
      printf("ALERTE SURCHAUFFE %s%u (%s) temp=%d.%d seuil=%d.%d src=%u seq=%u\n",
             prefixe_id(src), INDICE[src], NOM_MACHINE[INDICE[src]],
             DIXIEMES(r.valeur), DIXIEMES(seuil), src, r.seq);
    } else if(s->en_alerte && r.valeur <= seuil - HYSTERESIS_DIXIEMES) {
      s->en_alerte = 0;
      leds_off(LEDS_BLUE);
      printf("FIN_ALERTE SURCHAUFFE %s%u temp=%d.%d\n", prefixe_id(src), INDICE[src], DIXIEMES(r.valeur));
    }
  } else if(r.type == TYPE_PRESENCE && r.etat == ETAT_INTRUSION) {
    printf("ALERTE INTRUSION %s%u heure=%02d:%02d src=%u seq=%u\n",
           prefixe_id(src), INDICE[src], HHMM(r.valeur), src, r.seq);
  }
}

/* ---------------------------------------------------------------- statistiques et supervision */
static void
ecrire_stats(void)
{
  uint8_t i;
  for(i = 2; i <= MAX_ID; i++) {
    suivi_t *s = &suivi[i];
    if(!s->vu) continue;
    printf("STAT src=%u %s recus=%u perdus=%u doublons=%u sauts=%u parent=%u%s\n", i, REPERE[i],
           s->recus, s->perdus, s->doublons, s->sauts, s->parent, s->muet ? " MUET" : "");
  }
}

static void
superviser(void)                              /* ENF8 : un nœud qui ne donne plus de nouvelles */
{
  uint8_t i;
  uint32_t t = maintenant_ms();
  for(i = 2; i <= MAX_ID; i++) {
    suivi_t *s = &suivi[i];
    if(s->vu && !s->muet && t - s->dernier_rx > SILENCE_MS) {
      s->muet = 1;
      printf("ALERTE NOEUD_MUET src=%u (%s) silence=%lu s\n", i, REPERE[i],
             (unsigned long)((t - s->dernier_rx) / 1000UL));
    }
  }
}

/* ---------------------------------------------------------------- processus principal */
PROCESS_THREAD(passerelle_process, ev, data)
{
  static struct etimer stats, supervision;

  PROCESS_BEGIN();
  printf("BOOT passerelle GW noeud %u (racine RPL)\n", node_id);
  NETSTACK_ROUTING.root_start();             /* « je suis la racine du réseau » */
  simple_udp_register(&conn, PORT_PASSERELLE, NULL, PORT_CAPTEUR, reception);
  etimer_set(&stats, MS(STATS_MS));
  etimer_set(&supervision, MS(5000));
  printf("PRET passerelle racine\n");

  while(1) {
    PROCESS_WAIT_EVENT();
    if(ev == PROCESS_EVENT_TIMER && data == &stats) {
      ecrire_stats();
      etimer_reset(&stats);
    } else if(ev == PROCESS_EVENT_TIMER && data == &supervision) {
      superviser();
      etimer_reset(&supervision);
    } else if(ev == serial_line_event_message && data != NULL && ((char *)data)[0] == 'S') {
      ecrire_stats();
    }
  }
  PROCESS_END();
}
