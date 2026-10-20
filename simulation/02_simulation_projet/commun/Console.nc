/*
 * INTERFACE Console : écrire du texte lisible sur le port série (fenêtre
 * « Mote output » de Cooja) et recevoir des commandes d'un caractère.
 * Une interface = une liste de « commandes » (ce qu'on peut demander au composant)
 * et d'« événements » (ce que le composant nous signale).
 */
interface Console {
  command void texte(const char *s);      /* écrit une chaîne */
  command void nombre(uint32_t n);         /* écrit un entier positif : 245 */
  command void entier(int32_t n);          /* écrit un entier signé : -3 */
  command void dixiemes(int32_t v);        /* écrit 752 sous la forme 75.2 */
  command void heure(uint16_t minutes);    /* écrit 1142 sous la forme 19:02 */
  command void car(char c);                /* écrit un caractère */

  /* Un caractère est arrivé sur le port série (tapé dans Cooja ou envoyé par un test) */
  event void commande(char c);
}
