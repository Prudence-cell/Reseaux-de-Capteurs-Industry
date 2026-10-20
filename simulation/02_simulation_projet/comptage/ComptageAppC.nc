/*
 * CONFIGURATION du nœud de comptage (C1, C2, C3 du plan = nœuds Cooja 5, 6, 7).
 * En réel : ESP32 + barrière infrarouge FC-51 à la sortie de chaque machine.
 */
#include "Usine.h"

configuration ComptageAppC {}
implementation {
  components MainC, LedsC, RandomC, ConsoleC, PublicationC, FlashInterneC;
  components ComptageC as App;
  components new TimerMilliC() as Piece;
  components new TimerMilliC() as Rapport;

  App.Boot        -> MainC;
  App.Leds        -> LedsC;
  App.Random      -> RandomC;
  App.Console     -> ConsoleC;
  App.Publication -> PublicationC;
  App.Flash       -> FlashInterneC;   /* mémoire qui survit au redémarrage */
  App.Piece       -> Piece;
  App.Rapport     -> Rapport;
}
