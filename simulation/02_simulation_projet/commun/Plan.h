/* FICHIER GÉNÉRÉ par scenarios/generer_scenarios.py — ne pas modifier à la main.
   Source : architecture/generer_plan.py et architecture/noeuds_cooja.csv */
#ifndef PLAN_H
#define PLAN_H

#define MAX_ID 10            /* plus grand numéro de nœud Cooja du plan */
enum { FAM_INFRA = 0, FAM_TEMP = 1, FAM_COUNT = 2, FAM_PIR = 3 };

/* Indexés par le numéro de nœud Cooja (TOS_NODE_ID) */
static const uint8_t FAMILLE[MAX_ID + 1] = { 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3 };
static const uint8_t INDICE[MAX_ID + 1]  = { 0, 0, 1, 2, 3, 1, 2, 3, 1, 2, 3 };   /* n° de machine / poste / zone */
static const char *const REPERE[MAX_ID + 1] = { "?", "GW", "T1", "T2", "T3", "C1", "C2", "C3", "P1", "P2", "P3" };

/* Indexés par le numéro de machine (1 = M1 ...) : seuil d'alerte en dixièmes de °C (EF2) */
static const int16_t SEUIL_DIXIEMES[4] = { 0, 850, 900, 2200 };
static const char *const NOM_MACHINE[4] = { "?", "Decoupe", "Presse", "Four" };

#endif
