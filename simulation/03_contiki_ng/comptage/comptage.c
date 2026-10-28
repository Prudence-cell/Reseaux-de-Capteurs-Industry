/*
 * NŒUD DE COMPTAGE (C1, C2, C3 = nœuds Cooja 5, 6, 7) — version Contiki-NG.
 * Traduction de ComptageC.nc (TinyOS).
 *
 * Les pièces sortent de la machine toutes les 2 à 6 s (≈ 15/min). Chaque pièce incrémente
 * le compteur (EF5), qui est aussitôt écrit dans un FICHIER du système de fichiers CFS de
 * Contiki : au redémarrage, le comptage reprend où il en était. Rapport toutes les 30 s.
 *
 * Commandes série : + = une pièce (T4), A = arrêt auto, M = marche auto, Z = remise à zéro,
 *                   R = redémarrage.
 * LIMITE Cooja mote : watchdog_reboot() ne fait rien sur cette plateforme (pas de matériel
 * émulé). « R » fait donc un REDÉMARRAGE LOGICIEL : toute la mémoire vive du programme est
 * remise à zéro et le compteur est relu dans le fichier, comme après une vraie coupure.
 */
#include "contiki.h"
#include "random.h"
#include "dev/leds.h"
#include "dev/serial-line.h"
#include "sys/node-id.h"
#include "cfs/cfs.h"
#include "usine.h"
#include "publication.h"
#include <stdio.h>

#define FICHIER  "compteur"
#define MAGIQUE  0xC0DE

typedef struct { uint16_t magique; uint32_t compteur; uint16_t controle; } sauvegarde_t;

static uint32_t compteur;
static uint16_t pieces_periode;
static bool automatique;

static uint16_t controle(uint32_t c) { return (uint16_t)(c ^ (c >> 16) ^ 0xA5A5); }

static void
sauvegarder(void)                             /* le fichier survit au redémarrage */
{
  sauvegarde_t s = { MAGIQUE, compteur, controle(compteur) };
  int fd = cfs_open(FICHIER, CFS_WRITE);
  if(fd >= 0) {
    cfs_write(fd, &s, sizeof(s));
    cfs_close(fd);
  }
}

static void
restaurer(void)
{
  sauvegarde_t s;
  int fd = cfs_open(FICHIER, CFS_READ);
  compteur = 0;
  if(fd >= 0) {
    if(cfs_read(fd, &s, sizeof(s)) == sizeof(s) && s.magique == MAGIQUE && s.controle == controle(s.compteur)) {
      compteur = s.compteur;
    }
    cfs_close(fd);
  }
}

static void
demarrage(void)                               /* ce que fait la carte à la mise sous tension */
{
  pieces_periode = 0;
  automatique = true;
  restaurer();
  printf("BOOT comptage %s poste %u %s%lu\n", REPERE[node_id], INDICE[node_id],
         compteur ? "RESTAURE compteur=" : "fichier vide, compteur=", (unsigned long)compteur);
}

static void
une_piece(void)
{
  compteur++;
  pieces_periode++;
  sauvegarder();
  leds_toggle(LEDS_RED);
  printf("PIECE n=%lu\n", (unsigned long)compteur);
}

PROCESS(comptage_process, "comptage");
AUTOSTART_PROCESSES(&comptage_process);

PROCESS_THREAD(comptage_process, ev, data)
{
  static struct etimer t_piece, t_rapport;
  static bool premier;

  PROCESS_BEGIN();
  demarrage();
  publication_demarrer();
  premier = true;
  etimer_set(&t_piece, MS(2000 + random_rand() % 4000));
  etimer_set(&t_rapport, MS(5000 + random_rand() % 10000));

  while(1) {
    PROCESS_WAIT_EVENT();
    if(ev == PROCESS_EVENT_TIMER && data == &t_piece) {
      if(automatique) une_piece();
      etimer_set(&t_piece, MS(2000 + random_rand() % 4000));
    } else if(ev == PROCESS_EVENT_TIMER && data == &t_rapport) {
      int16_t cadence;
      if(premier) { premier = false; etimer_set(&t_rapport, MS(PERIODE_MS)); }
      else etimer_reset(&t_rapport);
      cadence = (int16_t)((uint32_t)pieces_periode * 60000UL / PERIODE_MS);   /* pièces/min */
      pieces_periode = 0;
      publier(TYPE_COMPTAGE, ETAT_OK, cadence, compteur);
    } else if(ev == serial_line_event_message && data != NULL) {
      char c = ((char *)data)[0];
      if(c == '+') {
        une_piece();
      } else if(c == 'A') {
        automatique = false; printf("MODE manuel\n");
      } else if(c == 'M') {
        automatique = true; printf("MODE automatique\n");
      } else if(c == 'Z') {
        compteur = 0; pieces_periode = 0; sauvegarder(); printf("RAZ compteur=0\n");
      } else if(c == 'R') {
        printf("REDEMARRAGE demande (redemarrage logiciel)\n");
        compteur = 0;                         /* la RAM est « perdue » ... */
        publication_reinitialiser();          /* ... tampon vidé, numéros repartent de 1 */
        demarrage();                          /* ... puis on redémarre : relecture du fichier */
        premier = true;
        etimer_set(&t_piece, MS(2000 + random_rand() % 4000));
        etimer_set(&t_rapport, MS(5000 + random_rand() % 10000));
      }
    }
  }
  PROCESS_END();
}
