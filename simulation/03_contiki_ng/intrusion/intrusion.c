/*
 * NŒUD INTRUSION (P1, P2, P3 = nœuds Cooja 8, 9, 10) — version Contiki-NG.
 * Traduction de IntrusionC.nc (TinyOS).
 *
 * Horloge d'usine accélérée (usine.h) : 1 s = 1 min, départ 17h00 ; heures ouvrées 08h–18h (B4).
 *   - de JOUR : passages du personnel (aléatoires), comptés SANS alerte ;
 *   - de NUIT : toute présence → rapport INTRUSION immédiat + buzzer (LED bleue) 5 s ;
 *     au plus une alerte toutes les 10 s ;
 *   - toutes les 30 s : rapport de vie (VEILLE le jour, ARME la nuit).
 * Commande série : P = une présence devant le capteur (test T5).
 */
#include "contiki.h"
#include "random.h"
#include "dev/leds.h"
#include "dev/serial-line.h"
#include "sys/node-id.h"
#include "usine.h"
#include "publication.h"
#include <stdio.h>

#define ANTI_REBOND_MS  10000UL
#define DUREE_BUZZER_MS 5000UL

static uint32_t detections, derniere_alerte;
static bool deja_alerte = false, nuit;
static struct etimer t_buzzer;

PROCESS(intrusion_process, "intrusion");
AUTOSTART_PROCESSES(&intrusion_process);

static void
presence(void)                                /* quelqu'un passe devant le détecteur */
{
  uint32_t t = maintenant_ms();
  uint16_t h = heure_usine(t);
  detections++;
  if(heures_ouvrees(h)) {
    leds_toggle(LEDS_RED);
    printf("DETECTION heure=%02d:%02d heures ouvrees : pas d'alerte\n", HHMM(h));
    return;
  }
  if(deja_alerte && t - derniere_alerte < ANTI_REBOND_MS) {
    printf("DETECTION heure=%02d:%02d (alerte deja envoyee il y a moins de 10 s)\n", HHMM(h));
    return;
  }
  deja_alerte = true;
  derniere_alerte = t;
  leds_on(LEDS_BLUE);                         /* buzzer ! */
  PROCESS_CONTEXT_BEGIN(&intrusion_process);  /* l'etimer appartient au processus */
  etimer_set(&t_buzzer, MS(DUREE_BUZZER_MS));
  PROCESS_CONTEXT_END(&intrusion_process);
  printf("INTRUSION heure=%02d:%02d hors heures ouvrees -> alerte + buzzer\n", HHMM(h));
  publier(TYPE_PRESENCE, ETAT_INTRUSION, (int16_t)h, detections);
}

PROCESS_THREAD(intrusion_process, ev, data)
{
  static struct etimer t_lecture, t_rapport;
  static bool premier = true;

  PROCESS_BEGIN();
  {
    uint16_t h = heure_usine(0);
    nuit = !heures_ouvrees(h);
    printf("BOOT intrusion %s zone %u heure usine %02d:%02d (%s)\n", REPERE[node_id], INDICE[node_id],
           HHMM(h), nuit ? "nuit : armee" : "jour : desarmee");
  }
  publication_demarrer();
  etimer_set(&t_lecture, MS(LECTURE_MS));
  etimer_set(&t_rapport, MS(5000 + random_rand() % 10000));

  while(1) {
    PROCESS_WAIT_EVENT();
    if(ev == PROCESS_EVENT_TIMER && data == &t_lecture) {
      /* toutes les 2 s : on suit l'horloge et on simule les passages du personnel en journée */
      uint16_t h = heure_usine(maintenant_ms());
      bool est_nuit = !heures_ouvrees(h);
      if(est_nuit != nuit) {
        nuit = est_nuit;
        printf("HORLOGE %02d:%02d %s\n", HHMM(h),
               nuit ? "mode nuit : surveillance armee" : "mode jour : surveillance desarmee");
      }
      if(!nuit && random_rand() % 12 == 0) presence();   /* ≈ un passage toutes les 24 s */
      etimer_reset(&t_lecture);
    } else if(ev == PROCESS_EVENT_TIMER && data == &t_rapport) {
      uint16_t h = heure_usine(maintenant_ms());
      if(premier) { premier = false; etimer_set(&t_rapport, MS(PERIODE_MS)); }
      else etimer_reset(&t_rapport);
      publier(TYPE_PRESENCE, nuit ? ETAT_ARME : ETAT_VEILLE, (int16_t)h, detections);
    } else if(ev == PROCESS_EVENT_TIMER && data == &t_buzzer) {
      leds_off(LEDS_BLUE);
    } else if(ev == serial_line_event_message && data != NULL && ((char *)data)[0] == 'P') {
      printf("SCENARIO presence devant le capteur\n");
      presence();
    }
  }
  PROCESS_END();
}
