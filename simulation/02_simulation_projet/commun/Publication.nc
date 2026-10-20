/*
 * INTERFACE Publication : « publier un rapport vers la passerelle ».
 * L'application (thermique, comptage, intrusion) remplit type, état, valeur, compteur ;
 * le composant s'occupe de tout le reste (numéro de séquence, horodatage, tampon,
 * routage CTP, authentification).
 */
#include "Usine.h"

interface Publication {
  /* Range le rapport dans le tampon puis l'envoie dès que possible.
     Renvoie le numéro de séquence attribué. */
  command uint16_t publier(uint8_t type, uint8_t etat, int16_t valeur, uint32_t compteur);

  /* Nombre de rapports qui attendent encore dans le tampon */
  command uint8_t enAttente();

  /* La radio et le routage sont démarrés : l'application peut lancer ses minuteries */
  event void pret();
}
