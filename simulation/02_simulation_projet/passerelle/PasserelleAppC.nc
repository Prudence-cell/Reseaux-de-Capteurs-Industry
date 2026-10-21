/*
 * CONFIGURATION de la passerelle (nœud 1 = GW du plan, racine de l'arbre CTP).
 * En réel : Raspberry Pi 4 + Mosquitto/Node-RED/InfluxDB/Grafana.
 * Ici : une carte Sky qui reçoit tout le trafic CTP et écrit, sur son port série,
 * les messages MQTT qu'elle publierait (topic + JSON du cahier des charges).
 */
#include "Usine.h"

configuration PasserelleAppC {}
implementation {
  components MainC, LedsC, ActiveMessageC, ConsoleC;
  components PasserelleC as App;
  components CollectionC as Collecteur;          /* CTP, dont ce nœud est la racine */
  components new TimerMilliC() as Stats;
  components new TimerMilliC() as Supervision;

  App.Boot           -> MainC;
  App.Leds           -> LedsC;
  App.Console        -> ConsoleC;
  App.RadioControl   -> ActiveMessageC;
  App.RoutingControl -> Collecteur;
  App.RootControl    -> Collecteur;
  App.Receive        -> Collecteur.Receive[COL_USINE];  /* paquets arrivés à la racine */
  App.CtpPacket      -> Collecteur;                     /* lire le nombre de sauts */
  App.Stats          -> Stats;
  App.Supervision    -> Supervision;
}
