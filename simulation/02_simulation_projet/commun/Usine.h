#ifndef USINE_H
#define USINE_H
/*
 * En-tête COMMUN aux 4 applications (passerelle, thermique, comptage, intrusion).
 * Il fixe le « contrat » entre les capteurs et la passerelle :
 *   - les paramètres de temps (période de mesure, horloge d'usine...) ;
 *   - le format binaire du message radio (l'équivalent du JSON du cahier des charges) ;
 *   - le petit code d'authentification (ENF6).
 * Toute modification ici impose de recompiler les 4 applications (construire.sh le fait).
 */
#include "Plan.h"   /* généré depuis architecture/generer_plan.py : repères, seuils, zones */

/* ------------------------------------------------------------------ unités de temps
   PIÈGE TinyOS : une « milliseconde » de TimerMilli vaut 1/1024 s (milliseconde binaire).
   Demander 30000 donnerait 29,3 s réelles. On convertit donc toujours :
     TICKS(ms) : vraies millisecondes -> tops de minuterie (pour startPeriodic...)
     EN_MS(t)  : tops de minuterie (getNow) -> vraies millisecondes (×125/128, sans débordement) */
#define TICKS(ms) ((uint32_t)(ms) + ((uint32_t)(ms) * 3UL) / 125UL)
#define EN_MS(t)  ((uint32_t)(t) - ((uint32_t)(t) * 3UL) / 128UL)

/* ------------------------------------------------------------------ paramètres (en vraies ms) */
#ifndef PERIODE_MS
#define PERIODE_MS      30000UL  /* EF1 : un rapport toutes les 30 s */
#endif
#define LECTURE_MS      2000UL   /* lecture locale du capteur toutes les 2 s (coût radio nul) */
#define SURVEILLANCE_MS 1000UL   /* contrôle du parent CTP chaque seconde */
#define REESSAI_MS      2000UL   /* attente avant de réessayer un envoi échoué */
#define CAPACITE_TAMPON 16       /* rapports en attente d'envoi (ex. pendant une reconvergence CTP) */

/* Horloge d'usine ACCÉLÉRÉE (pour voir le jour et la nuit en quelques minutes) :
   1 s de simulation = ACCEL s d'usine. Avec 60 : 1 s = 1 min, 24 h = 24 min.
   L'usine « démarre » à HEURE_DEBUT_MIN (17h00), la nuit commence donc à t = 60 s. */
#define ACCEL           60UL
#define HEURE_DEBUT_MIN (17 * 60)
#define OUVERTURE_MIN   (8 * 60)    /* 08h00 */
#define FERMETURE_MIN   (18 * 60)   /* 18h00 */
#define EPOCH_DEBUT     1792512000UL /* 2026-10-20 17:00:00 (UTC+1) : base des « timestamp » JSON */

/* Passerelle : un nœud est déclaré muet après 3 périodes sans nouvelles (+ marge) */
#define SILENCE_MS      (3 * PERIODE_MS + 5000UL)
#define STATS_MS        60000UL

/* Hystérésis : on sort de l'alerte de surchauffe 2,0 °C sous le seuil */
#define HYSTERESIS_DIXIEMES 20

/* ------------------------------------------------------------------ identifiants radio */
enum {
  COL_USINE = 0x47,   /* identifiant de « collection » CTP (comme un port réseau) */
  ID_PUITS  = 1,      /* nœud 1 = passerelle = racine de l'arbre CTP */
};

/* Types de rapport */
enum {
  TYPE_TEMPERATURE = 1,
  TYPE_COMPTAGE    = 2,
  TYPE_PRESENCE    = 3,
};

/* États (champ « status » du JSON) */
enum {
  ETAT_OK        = 0,   /* température normale / comptage normal */
  ETAT_ALERTE    = 1,   /* surchauffe */
  ETAT_FIN_ALERTE= 2,   /* retour sous le seuil */
  ETAT_VEILLE    = 3,   /* intrusion : heures ouvrées, détection désarmée */
  ETAT_ARME      = 4,   /* intrusion : nuit, surveillance armée, rien vu */
  ETAT_INTRUSION = 5,   /* intrusion : présence hors heures ouvrées */
};

/* ------------------------------------------------------------------ message radio
   nx_ = « network types » : TinyOS gère l'ordre des octets pour nous.
   22 octets + 8 octets d'en-tête CTP : on dépasse les 28 octets par défaut,
   d'où TOSH_DATA_LENGTH=48 dans les Makefiles. */
typedef nx_struct rapport {
  nx_uint8_t  type;       /* TYPE_... */
  nx_uint8_t  etat;       /* ETAT_... */
  nx_uint16_t source;     /* numéro du nœud (couvert par l'authentification) */
  nx_uint16_t seq;        /* numéro de séquence : sert au calcul du taux de livraison */
  nx_uint32_t age_ms;     /* âge de la mesure au moment de l'envoi (0 si envoyée tout de suite) */
  nx_int16_t  valeur;     /* T : dixièmes de °C · C : cadence (pièces/min) · P : heure usine (min) */
  nx_uint32_t compteur;   /* C : pièces cumulées · P : nombre de détections */
  nx_uint16_t parent;     /* parent CTP au moment de l'envoi (pour dessiner l'arbre) */
  nx_uint16_t etx;        /* coût de la route (ETX ×10) annoncé par CTP */
  nx_uint16_t mac;        /* code d'authentification (ENF6) */
} rapport_t;

/* ------------------------------------------------------------------ authentification (ENF6)
   Code d'authentification de message (MAC) sur 16 bits, calculé avec une clé partagée
   par tous les nœuds légitimes. Un nœud qui ne connaît pas la clé ne peut pas fabriquer
   un message accepté par la passerelle.
   ATTENTION : c'est un démonstrateur pédagogique (hachage FNV-1a « salé » par la clé),
   pas un algorithme cryptographique. En réel : AES-CCM du CC2420 / TLS côté ESP32-MQTT. */
#ifndef CLE_RESEAU
#define CLE_RESEAU 0x5A17C3E9UL
#endif

static inline uint16_t macOctets(const void *donnees, uint8_t n, uint32_t cle) {
  const uint8_t *o = (const uint8_t *)donnees;
  uint8_t i;
  uint32_t h = 2166136261UL ^ cle;
  for (i = 0; i < n; i++) { h ^= o[i]; h *= 16777619UL; }
  h ^= cle >> 7;
  h *= 16777619UL;
  return (uint16_t)(h ^ (h >> 16));
}
/* Le champ mac est toujours le DERNIER de la structure : on signe tout ce qui le précède */
static inline uint16_t calculerMac(const rapport_t *r, uint32_t cle) {
  return macOctets(r, sizeof(rapport_t) - 2, cle);
}
/* Heure d'usine (en minutes depuis minuit) à partir de l'horloge locale du nœud (vraies ms) */
static inline uint16_t heureUsine(uint32_t maintenant_ms) {
  uint32_t min = HEURE_DEBUT_MIN + (maintenant_ms / 1000UL) * ACCEL / 60UL;
  return (uint16_t)(min % 1440UL);
}
static inline bool heuresOuvrees(uint16_t h) {
  return h >= OUVERTURE_MIN && h < FERMETURE_MIN;
}

#endif
