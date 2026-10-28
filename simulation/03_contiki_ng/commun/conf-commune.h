#ifndef CONF_COMMUNE_H
#define CONF_COMMUNE_H
/*
 * Configuration Contiki-NG commune aux 4 programmes (incluse par chaque project-conf.h).
 * Équivalent des options de commun/Makefile.commun de la version TinyOS.
 */

/* Silence des journaux internes de Contiki (RPL, IPv6, MAC...) : seules nos lignes
   (PUB, RX, PARENT, ALERTE...) apparaissent dans Mote output, comme en TinyOS. */
#define LOG_CONF_LEVEL_RPL      LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_TCPIP    LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_IPV6     LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_6LOWPAN  LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_MAC      LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_FRAMER   LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_MAIN     LOG_LEVEL_NONE

/* Une ligne de commande série tient en 32 caractères */
#define SERIAL_LINE_CONF_BUFSIZE 32

#endif
