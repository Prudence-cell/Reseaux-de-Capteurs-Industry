/*
 * MODULE du nœud thermique.
 *
 * Modèle de la machine (en dixièmes de °C pour rester en nombres entiers) :
 *   - au démarrage la machine est à la température ambiante (25 °C) et chauffe
 *     vers sa température de régime (1er ordre : elle rattrape 1/20 de l'écart
 *     toutes les 2 s, soit une constante de temps d'environ 40 s) ;
 *   - la température de régime dérive lentement (marche aléatoire bornée à ±3 °C) ;
 *   - un bruit de mesure de ±0,3 °C s'ajoute (EF1 demande ±1 °C).
 *
 * Fonctionnement :
 *   - LECTURE toutes les 2 s : si la température dépasse le seuil de la machine,
 *     on publie TOUT DE SUITE un rapport « ALERTE » (sans attendre les 30 s) ;
 *   - RAPPORT toutes les 30 s (EF1), quel que soit l'état.
 *
 * Commandes série : H = sonde forcée à seuil + 5 °C (95 °C sur M2 : test T2),
 *                   N = retour au fonctionnement normal.
 */
#include "Usine.h"

module ThermiqueC {
  uses {
    interface Boot;
    interface Leds;
    interface Random;
    interface Console;
    interface Publication;
    interface Timer<TMilli> as Lecture;
    interface Timer<TMilli> as Rapport;
  }
}
implementation {
  /* Température de régime de chaque machine (dixièmes de °C) : bien sous le seuil */
  const int16_t REGIME[4] = { 0, 680, 740, 1850 };   /* M1 68 °C, M2 74 °C, M3 185 °C */

  uint8_t machine;          /* 1, 2 ou 3 */
  int16_t seuil;
  int16_t temp = 250;       /* 25,0 °C au démarrage */
  int16_t consigne;         /* température vers laquelle la machine tend */
  int16_t derive = 0;
  bool surchauffe = FALSE;  /* scénario de test en cours */
  bool enAlerte = FALSE;
  bool premierRapport = TRUE;

  int16_t aleatoire(int16_t amplitude) {      /* entier dans [-amplitude ; +amplitude] */
    return (int16_t)(call Random.rand16() % (2 * amplitude + 1)) - amplitude;
  }

  event void Boot.booted() {
    /* un nœud absent du plan (l'intrus du test ENF6, n° 11) se fait passer pour T2 */
    uint16_t idPlan = (TOS_NODE_ID <= MAX_ID) ? TOS_NODE_ID : 3;
    machine = INDICE[idPlan];
    if (machine < 1 || machine > 3) machine = 1;
    seuil = SEUIL_DIXIEMES[machine];
    consigne = REGIME[machine];
    call Console.texte("BOOT thermique ");
    call Console.texte(TOS_NODE_ID <= MAX_ID ? REPERE[idPlan] : "INTRUS");
    call Console.texte(" machine M");  call Console.nombre(machine);
    call Console.texte(" (");          call Console.texte(NOM_MACHINE[machine]);
    call Console.texte(") seuil=");    call Console.dixiemes(seuil);
    call Console.texte(" C\n");
  }

  event void Publication.pret() {
    call Lecture.startPeriodic(TICKS(LECTURE_MS));
    /* premier rapport après 5 à 15 s : les nœuds ne parlent pas tous en même temps */
    call Rapport.startOneShot(TICKS(5000 + call Random.rand16() % 10000));
  }

  /* --------------------------------------------------------------- lecture du capteur */
  event void Lecture.fired() {
    if (surchauffe) {
      temp = seuil + 50 + aleatoire(3);        /* la sonde lit seuil + 5 °C */
    } else {
      derive += aleatoire(2);
      if (derive > 30) derive = 30;
      if (derive < -30) derive = -30;
      temp += (consigne + derive - temp) / 20;
      temp += aleatoire(3);                    /* bruit ±0,3 °C */
    }

    if (temp > seuil && !enAlerte) {
      enAlerte = TRUE;
      call Leds.led2On();                      /* LED bleue = machine en alerte */
      call Console.texte("DEPASSEMENT temp="); call Console.dixiemes(temp);
      call Console.texte(" seuil=");           call Console.dixiemes(seuil);
      call Console.car('\n');
      call Publication.publier(TYPE_TEMPERATURE, ETAT_ALERTE, temp, 0);
    } else if (enAlerte && temp <= seuil - HYSTERESIS_DIXIEMES) {
      enAlerte = FALSE;
      call Leds.led2Off();
      call Console.texte("RETOUR_NORMAL temp="); call Console.dixiemes(temp);
      call Console.car('\n');
      call Publication.publier(TYPE_TEMPERATURE, ETAT_FIN_ALERTE, temp, 0);
    }
  }

  /* --------------------------------------------------------------- rapport périodique */
  event void Rapport.fired() {
    if (premierRapport) {                      /* ensuite : toutes les 30 s pile */
      premierRapport = FALSE;
      call Rapport.startPeriodic(TICKS(PERIODE_MS));
    }
    call Leds.led0Toggle();
    call Publication.publier(TYPE_TEMPERATURE, enAlerte ? ETAT_ALERTE : ETAT_OK, temp, 0);
  }

  /* --------------------------------------------------------------- banc d'essai */
  event void Console.commande(char c) {
    if (c == 'H') {
      surchauffe = TRUE;
      call Console.texte("SCENARIO surchauffe : sonde a ");
      call Console.dixiemes(seuil + 50);
      call Console.texte(" C\n");
    } else if (c == 'N') {
      surchauffe = FALSE;
      temp = consigne;
      call Console.texte("SCENARIO fin de surchauffe\n");
    }
  }
}
