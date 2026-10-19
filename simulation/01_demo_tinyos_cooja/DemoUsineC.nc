/*
 * MODULE : le comportement du nœud.
 * Le même programme tourne sur toutes les cartes ; chaque carte regarde son
 * numéro (TOS_NODE_ID, attribué par Cooja) pour savoir si elle est le puits
 * (nœud 1) ou un capteur (tous les autres).
 *
 * TinyOS est piloté par des ÉVÉNEMENTS : on n'écrit pas de boucle infinie,
 * on réagit à "la carte a démarré", "la minuterie a sonné", "un paquet est arrivé".
 */
#include "DemoUsine.h"

module DemoUsineC {
  uses {
    interface Boot;
    interface Leds;
    interface Timer<TMilli> as Minuterie;
    interface SplitControl as RadioControl;
    interface AMSend;
    interface Packet;
    interface Receive;
    interface Random;
    interface StdControl as SerieControl;
    interface UartByte;
  }
}
implementation {
  message_t paquet;          /* tampon du message à envoyer */
  bool occupe = FALSE;       /* vrai pendant qu'un envoi est en cours */
  uint16_t seq = 0;          /* numéro de séquence des mesures */
  uint16_t temperature;      /* température simulée, en °C */

  /* Petit "printf" maison : envoie du texte brut sur le port série.
     Cooja affiche chaque ligne dans la fenêtre "Mote output". */
  void ecrire(const char *s) {
    while (*s) call UartByte.send(*s++);
  }
  void ecrireNombre(uint16_t n) {
    char chiffres[6];
    uint8_t i = 0;
    if (n == 0) { call UartByte.send('0'); return; }
    while (n > 0) { chiffres[i++] = '0' + (n % 10); n /= 10; }
    while (i > 0) call UartByte.send(chiffres[--i]);
  }

  /* 1. La carte démarre */
  event void Boot.booted() {
    call SerieControl.start();
    temperature = 60 + TOS_NODE_ID * 3;
    ecrire("Demarrage noeud ");
    ecrireNombre(TOS_NODE_ID);
    ecrire(TOS_NODE_ID == ID_PUITS ? " (puits = passerelle)\n" : " (capteur de temperature)\n");
    call RadioControl.start();
  }

  /* 2. La radio est allumée : les capteurs lancent leur minuterie */
  event void RadioControl.startDone(error_t err) {
    if (err != SUCCESS) { call RadioControl.start(); return; }
    if (TOS_NODE_ID != ID_PUITS) call Minuterie.startPeriodic(PERIODE_MS);
  }
  event void RadioControl.stopDone(error_t err) {}

  /* 3. Toutes les 2 s, un capteur "mesure" puis envoie au puits */
  event void Minuterie.fired() {
    mesure_msg_t *m;

    /* Simulation de la machine : elle chauffe de 0 à 4 °C par mesure,
       puis refroidit d'un coup après 95 °C */
    temperature += call Random.rand16() % 5;
    if (temperature > 95) temperature = 60;

    if (occupe) return;
    m = (mesure_msg_t *) call Packet.getPayload(&paquet, sizeof(mesure_msg_t));
    if (m == NULL) return;
    m->noeud = TOS_NODE_ID;
    m->seq = ++seq;
    m->temperature = temperature;

    if (call AMSend.send(ID_PUITS, &paquet, sizeof(mesure_msg_t)) == SUCCESS) {
      occupe = TRUE;
      call Leds.led0Toggle();                  /* LED rouge = j'émets */
      ecrire("TX seq=");  ecrireNombre(seq);
      ecrire(" temp=");   ecrireNombre(temperature);
      ecrire(" C\n");
    }
  }

  event void AMSend.sendDone(message_t *msg, error_t err) {
    if (msg == &paquet) occupe = FALSE;
  }

  /* 4. Le puits reçoit un paquet radio */
  event message_t *Receive.receive(message_t *msg, void *payload, uint8_t len) {
    mesure_msg_t *m;
    if (TOS_NODE_ID != ID_PUITS || len != sizeof(mesure_msg_t)) return msg;
    m = (mesure_msg_t *) payload;

    call Leds.led1Toggle();                    /* LED verte = j'ai reçu */
    ecrire("RX noeud="); ecrireNombre(m->noeud);
    ecrire(" seq=");     ecrireNombre(m->seq);
    ecrire(" temp=");    ecrireNombre(m->temperature);
    ecrire(" C");
    if (m->temperature > SEUIL_ALERTE) {
      ecrire("  >>> ALERTE SURCHAUFFE");
      call Leds.led2On();                      /* LED bleue = alerte */
    }
    ecrire("\n");
    return msg;
  }
}
