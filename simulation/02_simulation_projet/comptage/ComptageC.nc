/*
 * MODULE du nœud de comptage.
 *
 * Modèle : les pièces sortent de la machine à intervalles aléatoires de 2 à 6 s
 * (≈ 15 pièces/min). Chaque pièce qui coupe la barrière IR incrémente le compteur (EF5).
 * Le compteur cumulé est écrit en FLASH à chaque pièce : après un redémarrage
 * (coupure d'alimentation, chien de garde...), le comptage reprend où il en était.
 * Toutes les 30 s, rapport : compteur cumulé + cadence (pièces/min) de la période.
 *
 * Commandes série : + = une pièce (test T4), A = arrêt des arrivées automatiques,
 *                   M = marche automatique, Z = remise à zéro, R = redémarrage forcé.
 */
#include "Usine.h"

module ComptageC {
  uses {
    interface Boot;
    interface Leds;
    interface Random;
    interface Console;
    interface Publication;
    interface InternalFlash as Flash;
    interface Timer<TMilli> as Piece;
    interface Timer<TMilli> as Rapport;
  }
}
implementation {
  enum { MAGIQUE = 0xC0DE };
  /* Ce qu'on range en flash. « controle » permet de reconnaître une flash vierge ou abîmée. */
  typedef struct { uint16_t magique; uint32_t compteur; uint16_t controle; } sauvegarde_t;

  uint32_t compteur = 0;
  uint16_t piecesPeriode = 0;
  bool automatique = TRUE;
  bool premierRapport = TRUE;

  uint16_t controle(uint32_t c) { return (uint16_t)(c ^ (c >> 16) ^ 0xA5A5); }

  void sauvegarder() {
    sauvegarde_t s;
    s.magique = MAGIQUE; s.compteur = compteur; s.controle = controle(compteur);
    call Flash.write((void *)0, &s, sizeof(s));
  }

  event void Boot.booted() {
    sauvegarde_t s;
    call Flash.read((void *)0, &s, sizeof(s));
    call Console.texte("BOOT comptage "); call Console.texte(REPERE[TOS_NODE_ID]);
    call Console.texte(" poste ");        call Console.nombre(INDICE[TOS_NODE_ID]);
    if (s.magique == MAGIQUE && s.controle == controle(s.compteur)) {
      compteur = s.compteur;
      call Console.texte(" RESTAURE compteur=");
    } else {
      call Console.texte(" flash vierge, compteur=");
    }
    call Console.nombre(compteur);
    call Console.car('\n');
  }

  void prochainePiece() {
    call Piece.startOneShot(TICKS(2000 + call Random.rand16() % 4000));
  }

  event void Publication.pret() {
    prochainePiece();
    call Rapport.startOneShot(TICKS(5000 + call Random.rand16() % 10000));
  }

  /* Une pièce coupe la barrière infrarouge */
  void unePiece() {
    compteur++;
    piecesPeriode++;
    sauvegarder();
    call Leds.led0Toggle();
    call Console.texte("PIECE n="); call Console.nombre(compteur);
    call Console.car('\n');
  }

  event void Piece.fired() {
    if (automatique) unePiece();
    prochainePiece();
  }

  event void Rapport.fired() {
    int16_t cadence;
    if (premierRapport) { premierRapport = FALSE; call Rapport.startPeriodic(TICKS(PERIODE_MS)); }
    cadence = (int16_t)((uint32_t)piecesPeriode * 60000UL / PERIODE_MS);   /* pièces par minute */
    piecesPeriode = 0;
    call Publication.publier(TYPE_COMPTAGE, ETAT_OK, cadence, compteur);
  }

  event void Console.commande(char c) {
    if (c == '+') unePiece();
    else if (c == 'A') { automatique = FALSE; call Console.texte("MODE manuel\n"); }
    else if (c == 'M') { automatique = TRUE;  call Console.texte("MODE automatique\n"); }
    else if (c == 'Z') { compteur = 0; piecesPeriode = 0; sauvegarder(); call Console.texte("RAZ compteur=0\n"); }
    else if (c == 'R') {
      call Console.texte("REDEMARRAGE demande (chien de garde)\n");
      /* Écrire dans le registre du chien de garde SANS son mot de passe (0x5A)
         provoque un redémarrage immédiat du microcontrôleur, comme une coupure. */
      WDTCTL = 0;
    }
  }
}
