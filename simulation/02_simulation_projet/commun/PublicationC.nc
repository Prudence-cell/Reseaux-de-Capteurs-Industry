/*
 * CONFIGURATION PublicationC : câblage du service de publication des nœuds capteurs.
 *
 *   application ──Publication──> PublicationP ──Send──> CTP (CollectionC) ──> radio CC2420
 *
 * CTP (Collection Tree Protocol, tos/lib/net/ctp) construit tout seul un ARBRE
 * dont la racine est la passerelle : chaque nœud choisit un « parent » plus proche
 * de la racine (au sens du coût ETX) et lui confie ses paquets, qui remontent
 * ainsi de saut en saut jusqu'au puits.
 */
#include "Usine.h"

configuration PublicationC {
  provides interface Publication;
}
implementation {
  components PublicationP, MainC, ActiveMessageC, ConsoleC, LedsC;
  components CollectionC as Collecteur;                 /* le protocole CTP */
  components new CollectionSenderC(COL_USINE) as Emetteur;
  components new TimerMilliC() as Surveillance;
  components new TimerMilliC() as Reessai;

  Publication = PublicationP;
  PublicationP.Boot           -> MainC;
  PublicationP.RadioControl   -> ActiveMessageC;
  PublicationP.RoutingControl -> Collecteur;
  PublicationP.Send           -> Emetteur;
  PublicationP.CtpInfo        -> Collecteur;
  PublicationP.Surveillance   -> Surveillance;
  PublicationP.Reessai        -> Reessai;
  PublicationP.Console        -> ConsoleC;
  PublicationP.Leds           -> LedsC;
}
