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
  components new TimerMilliC() as Acquitter;
  components DisseminationC;                     /* Drip : diffusion vers tous les nœuds */
  components new DisseminatorC(acquit_t, CLE_ACQUIT) as Acquits;

  App.Boot           -> MainC;
  App.Leds           -> LedsC;
  App.Console        -> ConsoleC;
  App.RadioControl   -> ActiveMessageC;
  App.RoutingControl -> Collecteur;
  App.RootControl    -> Collecteur;
  App.Receive        -> Collecteur.Receive[COL_USINE];  /* paquets arrivés à la racine */
  App.CtpPacket      -> Collecteur;                     /* lire le nombre de sauts */
  App.CtpInfo        -> Collecteur;                     /* forcer une annonce de route */
  App.Stats          -> Stats;
  App.Supervision    -> Supervision;
  App.Acquitter      -> Acquitter;
  App.DisseminationControl -> DisseminationC;
  App.Acquit         -> Acquits;                /* la passerelle PUBLIE les acquittements */
#ifdef LOW_POWER_LISTENING
  App.LowPowerListening -> ActiveMessageC;
#endif
}
