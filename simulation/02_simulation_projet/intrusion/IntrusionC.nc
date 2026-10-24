/*
 * MODULE du nœud intrusion.
 *
 * Horloge d'usine accélérée (Usine.h) : 1 s de simulation = 1 min d'usine,
 * départ à 17h00. Heures ouvrées : 08h00–18h00 (B4).
 *
 *   - De JOUR, le personnel passe devant le capteur : détections aléatoires,
 *     comptées mais SANS alerte (surveillance désarmée).
 *   - De NUIT, toute présence (EF6) déclenche immédiatement :
 *       · un rapport « INTRUSION » vers la passerelle (sans attendre les 30 s),
 *       · le buzzer local (représenté par la LED bleue) pendant 5 s.
 *     Pour ne pas saturer le réseau, au plus une alerte toutes les 10 s.
 *   - Toutes les 30 s : rapport de « vie » (VEILLE le jour, ARME la nuit),
 *     qui permet aussi à la passerelle de savoir que le nœud fonctionne (ENF8).
 *
 * Commande série : P = une présence devant le capteur (tests T5).
 */
#include "Usine.h"

module IntrusionC {
  uses {
    interface Boot;
    interface Leds;
    interface Random;
    interface Console;
    interface Publication;
    interface Timer<TMilli> as Lecture;
    interface Timer<TMilli> as Rapport;
    interface Timer<TMilli> as Buzzer;
  }
}
implementation {
  enum { ANTI_REBOND_MS = 10000, DUREE_BUZZER_MS = 5000 };

  uint32_t detections = 0;
  uint32_t derniereAlerte = 0;
  bool dejaAlerte = FALSE;
  bool nuit = FALSE;
  bool premierRapport = TRUE;

  uint32_t maintenant() { return EN_MS(call Lecture.getNow()); }

  event void Boot.booted() {
    uint16_t h = heureUsine(0);
    nuit = !heuresOuvrees(h);
    call Console.texte("BOOT intrusion "); call Console.texte(REPERE[TOS_NODE_ID]);
    call Console.texte(" zone ");          call Console.nombre(INDICE[TOS_NODE_ID]);
    call Console.texte(" heure usine ");   call Console.heure(h);
    call Console.texte(nuit ? " (nuit : armee)\n" : " (jour : desarmee)\n");
  }

  event void Publication.pret() {
    call Lecture.startPeriodic(TICKS(LECTURE_MS));
    call Rapport.startOneShot(TICKS(5000 + call Random.rand16() % 10000));
  }

  /* Quelqu'un passe devant le détecteur */
  void presence() {
    uint16_t h = heureUsine(maintenant());
    detections++;
    if (heuresOuvrees(h)) {
      call Leds.led0Toggle();
      call Console.texte("DETECTION heure="); call Console.heure(h);
      call Console.texte(" heures ouvrees : pas d'alerte\n");
      return;
    }
    if (dejaAlerte && maintenant() - derniereAlerte < ANTI_REBOND_MS) {
      call Console.texte("DETECTION heure="); call Console.heure(h);
      call Console.texte(" (alerte deja envoyee il y a moins de 10 s)\n");
      return;
    }
    dejaAlerte = TRUE;
    derniereAlerte = maintenant();
    call Leds.led2On();                                   /* buzzer ! */
    call Buzzer.startOneShot(TICKS(DUREE_BUZZER_MS));
    call Console.texte("INTRUSION heure="); call Console.heure(h);
    call Console.texte(" hors heures ouvrees -> alerte + buzzer\n");
    call Publication.publier(TYPE_PRESENCE, ETAT_INTRUSION, (int16_t)h, detections);
  }

  event void Buzzer.fired() { call Leds.led2Off(); }

  /* Toutes les 2 s : on suit l'horloge et on simule les passages du personnel en journée */
  event void Lecture.fired() {
    uint16_t h = heureUsine(maintenant());
    bool estNuit = !heuresOuvrees(h);
    if (estNuit != nuit) {
      nuit = estNuit;
      call Console.texte("HORLOGE "); call Console.heure(h);
      call Console.texte(nuit ? " mode nuit : surveillance armee\n" : " mode jour : surveillance desarmee\n");
    }
    if (!nuit && call Random.rand16() % 12 == 0) presence();   /* ≈ un passage toutes les 24 s */
  }

  event void Rapport.fired() {
    uint16_t h = heureUsine(maintenant());
    if (premierRapport) { premierRapport = FALSE; call Rapport.startPeriodic(TICKS(PERIODE_MS)); }
    call Publication.publier(TYPE_PRESENCE, nuit ? ETAT_ARME : ETAT_VEILLE, (int16_t)h, detections);
  }

  event void Console.commande(char c) {
    if (c == 'P') {
      call Console.texte("SCENARIO presence devant le capteur\n");
      presence();
    }
  }
}
