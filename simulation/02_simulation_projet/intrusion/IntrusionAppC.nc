/*
 * CONFIGURATION du nœud intrusion (P1, P2, P3 du plan = nœuds Cooja 8, 9, 10).
 * En réel : ESP32 + détecteur de présence PIR HC-SR501 + buzzer.
 */
#include "Usine.h"

configuration IntrusionAppC {}
implementation {
  components MainC, LedsC, RandomC, ConsoleC, PublicationC;
  components IntrusionC as App;
  components new TimerMilliC() as Lecture;
  components new TimerMilliC() as Rapport;
  components new TimerMilliC() as Buzzer;

  App.Boot        -> MainC;
  App.Leds        -> LedsC;
  App.Random      -> RandomC;
  App.Console     -> ConsoleC;
  App.Publication -> PublicationC;
  App.Lecture     -> Lecture;
  App.Rapport     -> Rapport;
  App.Buzzer      -> Buzzer;
}
