/*
 * MODULE ConsoleP : un petit « printf » maison.
 * PrintfC de TinyOS envoie des paquets binaires, illisibles dans Mote output ;
 * ici on envoie les caractères un par un (UartByte), comme dans la démo 01.
 *
 * Réception : chaque octet reçu déclenche une interruption (événement « async »).
 * On ne peut pas faire grand-chose dans une interruption, donc on range l'octet
 * dans une petite file et on « poste une tâche » qui le traitera plus tard,
 * dans le contexte normal du programme.
 */
module ConsoleP {
  provides interface Console;
  uses {
    interface StdControl as SerieControl;
    interface UartByte;
    interface UartStream;
  }
}
implementation {
  enum { TAILLE_FILE = 16 };
  bool demarree = FALSE;
  char file[TAILLE_FILE];
  norace uint8_t tete = 0, queue = 0;   /* norace : accès protégés à la main (atomic) */

  task void traiterCommande();

  /* Le port série est allumé au premier usage */
  void demarrer() {
    if (demarree) return;
    demarree = TRUE;
    call SerieControl.start();
    call UartStream.enableReceiveInterrupt();
  }

  command void Console.car(char c) {
    demarrer();
    call UartByte.send((uint8_t)c);
  }

  command void Console.texte(const char *s) {
    demarrer();
    while (*s) call UartByte.send((uint8_t)*s++);
  }

  command void Console.nombre(uint32_t n) {
    char chiffres[10];
    uint8_t i = 0;
    demarrer();
    do { chiffres[i++] = '0' + (n % 10); n /= 10; } while (n > 0);
    while (i > 0) call UartByte.send(chiffres[--i]);
  }

  command void Console.entier(int32_t n) {
    if (n < 0) { call Console.car('-'); n = -n; }
    call Console.nombre((uint32_t)n);
  }

  command void Console.dixiemes(int32_t v) {
    if (v < 0) { call Console.car('-'); v = -v; }
    call Console.nombre((uint32_t)v / 10);
    call Console.car('.');
    call Console.car('0' + (char)((uint32_t)v % 10));
  }

  command void Console.heure(uint16_t minutes) {
    uint16_t h = minutes / 60, m = minutes % 60;
    call Console.car('0' + h / 10); call Console.car('0' + h % 10);
    call Console.car(':');
    call Console.car('0' + m / 10); call Console.car('0' + m % 10);
  }

  /* Interruption : un octet est arrivé. On le range (sauf fins de ligne). */
  async event void UartStream.receivedByte(uint8_t octet) {
    if (octet == '\n' || octet == '\r' || octet == ' ') return;
    atomic {
      uint8_t suivant = (tete + 1) % TAILLE_FILE;
      if (suivant != queue) { file[tete] = (char)octet; tete = suivant; }
    }
    post traiterCommande();
  }

  task void traiterCommande() {
    char c;
    bool vide;
    atomic {
      vide = (queue == tete);
      if (!vide) { c = file[queue]; queue = (queue + 1) % TAILLE_FILE; }
    }
    if (vide) return;
    signal Console.commande(c);
    post traiterCommande();          /* s'il reste d'autres caractères */
  }

  async event void UartStream.sendDone(uint8_t *buf, uint16_t len, error_t err) {}
  async event void UartStream.receiveDone(uint8_t *buf, uint16_t len, error_t err) {}

  default event void Console.commande(char c) {}
}
