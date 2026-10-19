/*
 * CONFIGURATION : le "schéma de câblage" de l'application.
 * En nesC, on ne fait pas d'appels directs entre fichiers : on déclare des
 * composants et on relie leurs interfaces avec la flèche ->.
 */
#include "DemoUsine.h"

configuration DemoUsineAppC {}
implementation {
  components MainC;                          /* démarrage de la carte */
  components DemoUsineC as App;              /* notre code (DemoUsineC.nc) */
  components LedsC;                          /* les 3 LED de la carte */
  components new TimerMilliC() as Minuterie; /* une minuterie en millisecondes */
  components ActiveMessageC;                 /* la radio CC2420 */
  components new AMSenderC(AM_MESURE_MSG);   /* émetteur sur notre canal */
  components new AMReceiverC(AM_MESURE_MSG); /* récepteur sur notre canal */
  components RandomC;                        /* générateur aléatoire */
  components PlatformSerialC;                /* port série → fenêtre "Mote output" de Cooja */

  App.Boot         -> MainC;
  App.Leds         -> LedsC;
  App.Minuterie    -> Minuterie;
  App.RadioControl -> ActiveMessageC;
  App.AMSend       -> AMSenderC;
  App.Packet       -> AMSenderC;
  App.Receive      -> AMReceiverC;
  App.Random       -> RandomC;
  App.SerieControl -> PlatformSerialC;
  App.UartByte     -> PlatformSerialC;
}
