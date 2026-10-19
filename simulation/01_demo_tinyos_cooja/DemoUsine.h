#ifndef DEMO_USINE_H
#define DEMO_USINE_H

/* Constantes partagées par tous les nœuds */
enum {
  AM_MESURE_MSG = 0x89,   /* "canal" logique des messages de mesure */
  PERIODE_MS    = 2000,   /* une mesure toutes les 2 s (30 s dans le vrai projet) */
  ID_PUITS      = 1,      /* le nœud 1 joue la passerelle */
  SEUIL_ALERTE  = 90,     /* °C */
};

/* Contenu d'un message radio : l'équivalent binaire du JSON du cahier des charges.
   nx_ = "network types" : TinyOS gère l'ordre des octets pour nous. */
typedef nx_struct mesure_msg {
  nx_uint16_t noeud;
  nx_uint16_t seq;
  nx_uint16_t temperature;
} mesure_msg_t;

#endif
