/*
 * CONFIGURATION PublicationC : câblage du service de publication des nœuds capteurs.
 *
 *   application ──Publication──> PublicationP ──Send──> CTP (CollectionC) ──> radio ──> passerelle
 *                                     ^
 *                                     └──── acquittements diffusés par la passerelle (Drip)
 *
 * CTP (Collection Tree Protocol, tos/lib/net/ctp) construit tout seul un ARBRE
 * dont la racine est la passerelle : chaque nœud choisit un « parent » plus proche
 * de la racine (au sens du coût ETX) et lui confie ses paquets, qui remontent
 * ainsi de saut en saut jusqu'au puits.
 * Drip (tos/lib/net/drip) fait l'inverse : il propage une valeur de la passerelle
 * vers TOUS les nœuds (ici, la liste des rapports bien reçus).
 */
#include "Usine.h"

configuration PublicationC {
  provides interface Publication;
}
implementation {
  components PublicationP, MainC, ActiveMessageC, ConsoleC, LedsC;
  components CollectionC as Collecteur;                 /* le protocole CTP */
  components new CollectionSenderC(COL_USINE) as Emetteur;
  components DisseminationC;                            /* le protocole Drip */
  components new DisseminatorC(acquit_t, CLE_ACQUIT) as Acquits;
  components new TimerMilliC() as Surveillance;
  components new TimerMilliC() as Reessai;

  Publication = PublicationP;
  PublicationP.Boot                 -> MainC;
  PublicationP.RadioControl         -> ActiveMessageC;
  PublicationP.RoutingControl       -> Collecteur;
  PublicationP.DisseminationControl -> DisseminationC;
  PublicationP.Send                 -> Emetteur;
  PublicationP.CtpInfo              -> Collecteur;
  PublicationP.Acquit               -> Acquits;
  PublicationP.Surveillance         -> Surveillance;
  PublicationP.Reessai              -> Reessai;
  PublicationP.Console              -> ConsoleC;
  PublicationP.Leds                 -> LedsC;
}
