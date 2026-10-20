/*
 * CONFIGURATION du nœud thermique (T1, T2, T3 du plan = nœuds Cooja 2, 3, 4).
 * En réel : ESP32 + DS18B20 (M1, M2) ou thermocouple K / MAX6675 (M3, four).
 */
#include "Usine.h"

configuration ThermiqueAppC {}
implementation {
  components MainC, LedsC, RandomC, ConsoleC, PublicationC;
  components ThermiqueC as App;
  components new TimerMilliC() as Lecture;
  components new TimerMilliC() as Rapport;

  App.Boot        -> MainC;
  App.Leds        -> LedsC;
  App.Random      -> RandomC;
  App.Console     -> ConsoleC;
  App.Publication -> PublicationC;
  App.Lecture     -> Lecture;
  App.Rapport     -> Rapport;
}
