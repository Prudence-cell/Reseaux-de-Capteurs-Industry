#ifndef USINE_H
#define USINE_H
/*
 * En-tête COMMUN aux 4 programmes Contiki-NG (passerelle, thermique, comptage, intrusion).
 * C'est la traduction de commun/Usine.h de la version TinyOS : mêmes paramètres,
 * même format de message, même code d'authentification (ENF6).
 *
 * Différence avec TinyOS : l'horloge de Contiki compte en vraies millisecondes sur les
 * Cooja motes (CLOCK_SECOND = 1000), pas besoin des conversions TICKS() / EN_MS().
 */
#include "contiki.h"
#include <stdint.h>
#include <stdbool.h>
#include "plan.h"     /* généré depuis architecture/generer_plan.py : repères, seuils, zones */

/* ------------------------------------------------------------------ paramètres (ms) */
#define PERIODE_MS      30000UL  /* EF1 : un rapport toutes les 30 s */
#define LECTURE_MS      2000UL   /* lecture locale du capteur toutes les 2 s */
#define SURVEILLANCE_MS 1000UL   /* contrôle du parent RPL chaque seconde */
#define ATTENTE_ACK_MS  3000UL   /* sans acquittement de la passerelle au bout de 3 s : on renvoie */
#define CAPACITE_TAMPON 16       /* rapports en attente d'envoi */

/* Horloge d'usine ACCÉLÉRÉE : 1 s de simulation = 1 min d'usine, départ à 17h00 */
#define ACCEL           60UL
#define HEURE_DEBUT_MIN (17 * 60)
#define OUVERTURE_MIN   (8 * 60)
#define FERMETURE_MIN   (18 * 60)
#define EPOCH_DEBUT     1792512000UL /* 2026-10-20 17:00:00 (UTC+1) : base des « timestamp » JSON */

#define SILENCE_MS      (3 * PERIODE_MS + 5000UL)   /* passerelle : nœud déclaré muet */
#define STATS_MS        60000UL
#define HYSTERESIS_DIXIEMES 20                       /* fin d'alerte 2,0 °C sous le seuil */

/* ------------------------------------------------------------------ réseau UDP / RPL
   La passerelle (nœud 1) est la RACINE de RPL et le serveur UDP.
   Les capteurs envoient leurs rapports à l'adresse IPv6 de la racine. */
#define PORT_PASSERELLE 5678
#define PORT_CAPTEUR    8765
#define ID_PUITS        1

enum { TYPE_TEMPERATURE = 1, TYPE_COMPTAGE = 2, TYPE_PRESENCE = 3 };
enum {
  ETAT_OK = 0, ETAT_ALERTE = 1, ETAT_FIN_ALERTE = 2,
  ETAT_VEILLE = 3, ETAT_ARME = 4, ETAT_INTRUSION = 5,
};

/* ------------------------------------------------------------------ message radio
   Même contenu que la version TinyOS. « packed » : pas d'octet de bourrage, tous les
   nœuds lisent exactement les mêmes octets (en TinyOS, c'était le rôle des nx_types). */
typedef struct __attribute__((packed)) {
  uint8_t  type;       /* TYPE_... */
  uint8_t  etat;       /* ETAT_... */
  uint16_t source;     /* numéro du nœud (couvert par l'authentification) */
  uint16_t seq;        /* numéro de séquence : taux de livraison et acquittement */
  uint32_t age_ms;     /* temps passé dans le tampon avant l'envoi */
  int16_t  valeur;     /* T : dixièmes de °C · C : cadence (pièces/min) · P : heure usine (min) */
  uint32_t compteur;   /* C : pièces cumulées · P : nombre de détections */
  uint16_t parent;     /* parent RPL au moment de l'envoi (pour dessiner l'arbre) */
  uint16_t rang;       /* rang RPL du nœud (≈ distance à la racine) */
  uint16_t mac;        /* code d'authentification (ENF6) — toujours le DERNIER champ */
} rapport_t;

/* Acquittement renvoyé par la passerelle au capteur (lui aussi signé) */
typedef struct __attribute__((packed)) {
  uint16_t seq;
  uint16_t mac;
} acquit_t;

/* ------------------------------------------------------------------ authentification (ENF6)
   Démonstrateur pédagogique (hachage FNV-1a « salé » par la clé), pas un algorithme
   cryptographique. En réel : AES-CCM du 802.15.4 (LLSEC de Contiki-NG) ou DTLS. */
#ifndef CLE_RESEAU
#define CLE_RESEAU 0x5A17C3E9UL
#endif

static inline uint16_t
mac_octets(const void *donnees, uint8_t n, uint32_t cle)
{
  const uint8_t *o = (const uint8_t *)donnees;
  uint32_t h = 2166136261UL ^ cle;
  uint8_t i;
  for(i = 0; i < n; i++) { h ^= o[i]; h *= 16777619UL; }
  h ^= cle >> 7;
  h *= 16777619UL;
  return (uint16_t)(h ^ (h >> 16));
}
#define MAC_RAPPORT(r) mac_octets((r), sizeof(rapport_t) - 2, CLE_RESEAU)
#define MAC_ACQUIT(a)  mac_octets((a), sizeof(acquit_t) - 2, CLE_RESEAU)

/* ------------------------------------------------------------------ temps */
static inline uint32_t
maintenant_ms(void)
{
  return (uint32_t)(clock_time() * 1000UL / CLOCK_SECOND);
}
#define MS(ms) ((clock_time_t)((ms) * CLOCK_SECOND / 1000UL))   /* ms -> tops etimer */

static inline uint16_t
heure_usine(uint32_t t_ms)
{
  uint32_t min = HEURE_DEBUT_MIN + (t_ms / 1000UL) * ACCEL / 60UL;
  return (uint16_t)(min % 1440UL);
}
static inline bool
heures_ouvrees(uint16_t h)
{
  return h >= OUVERTURE_MIN && h < FERMETURE_MIN;
}

/* Écrit 752 sous la forme 75.2 et 1142 sous la forme 19:02 */
#define DIXIEMES(v) (int)((v) / 10), (int)(((v) < 0 ? -(v) : (v)) % 10)
#define HHMM(m)     (int)((m) / 60), (int)((m) % 60)

#endif
