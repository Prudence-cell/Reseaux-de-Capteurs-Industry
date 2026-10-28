#ifndef PUBLICATION_H
#define PUBLICATION_H
/*
 * Service de publication des nœuds capteurs (traduction de PublicationC / PublicationP).
 * L'application remplit type, état, valeur, compteur ; le service s'occupe du reste :
 * numéro de séquence, tampon, envoi UDP vers la racine RPL, acquittement, renvoi,
 * authentification, et écriture des lignes « PUB » et « PARENT ».
 */
#include "usine.h"

/* À appeler une fois au démarrage du programme */
void publication_demarrer(void);

/* Range le rapport dans le tampon et l'envoie dès que possible ; renvoie son seq */
uint16_t publier(uint8_t type, uint8_t etat, int16_t valeur, uint32_t compteur);

/* « Redémarrage logiciel » (test T4) : vide le tampon et repart à seq = 0 */
void publication_reinitialiser(void);

#endif
