/*
 * NŒUD THERMIQUE (T1, T2, T3 = nœuds Cooja 2, 3, 4) — version Contiki-NG.
 * Traduction de ThermiqueC.nc (TinyOS) : même modèle de machine, mêmes seuils.
 *
 * Modèle (en dixièmes de °C) : la machine part de 25 °C et rejoint sa température de régime
 * (1er ordre, 1/20 de l'écart toutes les 2 s), avec une dérive lente bornée à ±3 °C et un
 * bruit de ±0,3 °C (EF1 demande ±1 °C).
 *   - LECTURE toutes les 2 s : au-delà du seuil de SA machine → rapport ALERTE immédiat ;
 *   - RAPPORT toutes les 30 s (EF1).
 * Commandes série : H = sonde forcée à seuil + 5 °C (test T2), N = retour à la normale.
 *
 * nesC → Contiki : chaque « event » de TinyOS devient une branche de la boucle
 * « PROCESS_WAIT_EVENT » ci-dessous ; les minuteries TimerMilli deviennent des etimer.
 */
#include "contiki.h"
#include "random.h"
#include "dev/leds.h"
#include "dev/serial-line.h"
#include "sys/node-id.h"
#include "usine.h"
#include "publication.h"
#include <stdio.h>

static const int16_t REGIME[4] = { 0, 680, 740, 1850 };   /* M1 68 °C, M2 74 °C, M3 185 °C */

static uint8_t machine;
static int16_t seuil, consigne, temp = 250, derive = 0;
static bool surchauffe = false, en_alerte = false;

static int16_t
aleatoire(int16_t amplitude)                  /* entier dans [-amplitude ; +amplitude] */
{
  return (int16_t)(random_rand() % (2 * amplitude + 1)) - amplitude;
}

static void
lecture(void)
{
  if(surchauffe) {
    temp = seuil + 50 + aleatoire(3);         /* la sonde lit seuil + 5 °C */
  } else {
    derive += aleatoire(2);
    if(derive > 30) derive = 30;
    if(derive < -30) derive = -30;
    temp += (consigne + derive - temp) / 20;
    temp += aleatoire(3);                     /* bruit ±0,3 °C */
  }
  if(temp > seuil && !en_alerte) {
    en_alerte = true;
    leds_on(LEDS_BLUE);                       /* LED bleue = machine en alerte */
    printf("DEPASSEMENT temp=%d.%d seuil=%d.%d\n", DIXIEMES(temp), DIXIEMES(seuil));
    publier(TYPE_TEMPERATURE, ETAT_ALERTE, temp, 0);
  } else if(en_alerte && temp <= seuil - HYSTERESIS_DIXIEMES) {
    en_alerte = false;
    leds_off(LEDS_BLUE);
    printf("RETOUR_NORMAL temp=%d.%d\n", DIXIEMES(temp));
    publier(TYPE_TEMPERATURE, ETAT_FIN_ALERTE, temp, 0);
  }
}

PROCESS(thermique_process, "thermique");
AUTOSTART_PROCESSES(&thermique_process);

PROCESS_THREAD(thermique_process, ev, data)
{
  static struct etimer t_lecture, t_rapport;
  static bool premier = true;

  PROCESS_BEGIN();
  {
    /* un nœud absent du plan (l'intrus du test ENF6, n° 11) se fait passer pour T2 */
    uint16_t id_plan = (node_id <= MAX_ID) ? node_id : 3;
    machine = INDICE[id_plan];
    if(machine < 1 || machine > 3) machine = 1;
    seuil = SEUIL_DIXIEMES[machine];
    consigne = REGIME[machine];
    printf("BOOT thermique %s machine M%u (%s) seuil=%d.%d C\n",
           node_id <= MAX_ID ? REPERE[id_plan] : "INTRUS", machine, NOM_MACHINE[machine], DIXIEMES(seuil));
  }
  publication_demarrer();
  etimer_set(&t_lecture, MS(LECTURE_MS));
  /* premier rapport après 5 à 15 s : les nœuds ne parlent pas tous en même temps */
  etimer_set(&t_rapport, MS(5000 + random_rand() % 10000));

  while(1) {
    PROCESS_WAIT_EVENT();
    if(ev == PROCESS_EVENT_TIMER && data == &t_lecture) {
      lecture();
      etimer_reset(&t_lecture);
    } else if(ev == PROCESS_EVENT_TIMER && data == &t_rapport) {
      if(premier) { premier = false; etimer_set(&t_rapport, MS(PERIODE_MS)); }
      else etimer_reset(&t_rapport);          /* reset : période exacte, sans dérive */
      leds_toggle(LEDS_RED);
      publier(TYPE_TEMPERATURE, en_alerte ? ETAT_ALERTE : ETAT_OK, temp, 0);
    } else if(ev == serial_line_event_message && data != NULL) {
      char c = ((char *)data)[0];
      if(c == 'H') {
        surchauffe = true;
        printf("SCENARIO surchauffe : sonde a %d.%d C\n", DIXIEMES(seuil + 50));
      } else if(c == 'N') {
        surchauffe = false;
        temp = consigne;
        printf("SCENARIO fin de surchauffe\n");
      }
    }
  }
  PROCESS_END();
}
