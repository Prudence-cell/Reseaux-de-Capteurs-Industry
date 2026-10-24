/*
 * ESP32 n°3 — NŒUD D'INTRUSION (zone 1) avec un capteur PIR HC-SR501.
 *
 * Équivalent physique de simulation/02_simulation_projet/intrusion :
 *   - de 08h00 à 18h00 (heures ouvrées) la détection est DÉSARMÉE (« VEILLE ») :
 *     les passages sont comptés mais ne déclenchent pas d'alerte ;
 *   - hors heures ouvrées elle est ARMÉE : toute présence publie TOUT DE SUITE
 *     un message « INTRUSION » (EF6, ENF1) ;
 *   - toutes les 30 s : rapport de « vie » (VEILLE ou ARME).
 *
 * L'heure vient d'Internet (NTP). Pour la démonstration en journée, on force le mode
 * par MQTT : publier « ARME », « VEILLE » ou « AUTO » sur factory/cmd/ZONE_01.
 *
 * Réseau : Wi-Fi → broker MQTT Mosquitto sur le VPS.
 *   publie   factory/security/ZONE_01   (mesures, JSON)
 *   publie   factory/status/ZONE_01     (en ligne / hors ligne, « retained »)
 *   écoute   factory/cmd/ZONE_01        (ARME / VEILLE / AUTO / STATUT)
 *
 * Câblage HC-SR501 : VCC → VIN (5 V, il ne fonctionne pas bien en 3,3 V), GND → GND,
 *   OUT → GPIO 26 (sa sortie vaut 3,3 V : sans danger pour l'ESP32).
 *   Cavalier en position « H » (redéclenchable) ; potentiomètre « Tx » (durée) au minimum (~3 s),
 *   potentiomètre « Sx » (portée) à mi-course. Il lui faut ~60 s de chauffe à la mise sous tension.
 *
 * Bibliothèque : « PubSubClient » (Nick O'Leary). Carte : « ESP32 Dev Module ».
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>

/* ================================================================== À ADAPTER */
#define WIFI_SSID      "NOM_DU_WIFI"
#define WIFI_MDP       "MOT_DE_PASSE_WIFI"
#define MQTT_HOTE      "IP_OU_NOM_DU_VPS"
#define MQTT_UTILISATEUR "ZONE_01"            /* un compte Mosquitto PAR nœud (ENF6) */
#define MQTT_MDP       "MOT_DE_PASSE_ZONE_01"
#define UTILISER_TLS   0                      /* 1 = port 8883 chiffré (recommandé sur Internet) */

#define NODE_ID        "ZONE_01"
/* ================================================================== */

#if UTILISER_TLS
#include <WiFiClientSecure.h>
#define MQTT_PORT 8883
static const char CA_CERT[] = "";             /* voir esp32_thermique.ino */
WiFiClientSecure reseau;
#else
#define MQTT_PORT 1883
WiFiClient reseau;
#endif
PubSubClient mqtt(reseau);

/* ------------------------------------------------------------------ paramètres */
const uint32_t PERIODE_MS      = 30000;   /* EF1 */
const uint32_t REESSAI_MQTT_MS = 5000;
const uint32_t CHAUFFE_PIR_MS  = 60000;   /* détections ignorées pendant la chauffe du PIR */
const uint32_t ANTI_RAFALE_MS  = 5000;    /* au plus une alerte INTRUSION toutes les 5 s */
const int OUVERTURE_MIN = 8 * 60;         /* 08h00 */
const int FERMETURE_MIN = 18 * 60;        /* 18h00 */

const int BROCHE_PIR = 26;
const int BROCHE_LED = 2;                 /* allumée = surveillance armée */

char topicDonnees[64], topicStatut[64], topicCommande[64];

enum Mode { MODE_AUTO, MODE_ARME, MODE_VEILLE };
Mode mode = MODE_AUTO;

volatile bool presenceIsr = false;        /* positionné par l'interruption du PIR */
uint32_t detections = 0;
bool armee = false;
uint32_t seq = 0;
uint32_t dernierRapport = 0, dernierEssaiMqtt = 0, derniereAlerte = 0;
bool alerteEnvoyee = false;

void IRAM_ATTR mouvement() { presenceIsr = true; }

/* ------------------------------------------------------------------ tampon hors ligne */
const int CAPACITE_TAMPON = 16;
const int TAILLE_MSG      = 256;
char tampon[CAPACITE_TAMPON][TAILLE_MSG];
int teteTampon = 0, nbEnAttente = 0;

void mettreEnTampon(const char *msg) {
  if (nbEnAttente == CAPACITE_TAMPON) {          /* plein : on sacrifie le plus ancien */
    teteTampon = (teteTampon + 1) % CAPACITE_TAMPON;
    nbEnAttente--;
  }
  strlcpy(tampon[(teteTampon + nbEnAttente) % CAPACITE_TAMPON], msg, TAILLE_MSG);
  nbEnAttente++;
}

void viderTampon() {
  while (nbEnAttente > 0 && mqtt.publish(topicDonnees, tampon[teteTampon])) {
    teteTampon = (teteTampon + 1) % CAPACITE_TAMPON;
    nbEnAttente--;
  }
}

void publier(const char *msg) {
  Serial.print("TX "); Serial.print(topicDonnees); Serial.print(' '); Serial.println(msg);
  if (!mqtt.connected() || !mqtt.publish(topicDonnees, msg)) {
    mettreEnTampon(msg);
    Serial.println("   (broker injoignable : message mis en tampon)");
  }
}

uint32_t horodatage() {
  time_t t = time(nullptr);
  return t > 1700000000 ? (uint32_t)t : 0;
}

/* Heure locale en minutes depuis minuit ; -1 tant que NTP n'a pas répondu */
int minutesDuJour() {
  struct tm tm;
  if (horodatage() == 0 || !getLocalTime(&tm, 0)) return -1;
  return tm.tm_hour * 60 + tm.tm_min;
}

/* Faut-il surveiller maintenant ? Sans heure connue on reste ARMÉ (choix prudent). */
bool calculerArmement() {
  if (mode == MODE_ARME)   return true;
  if (mode == MODE_VEILLE) return false;
  int h = minutesDuJour();
  if (h < 0) return true;
  return !(h >= OUVERTURE_MIN && h < FERMETURE_MIN);
}

const char *texteMode() {
  return mode == MODE_AUTO ? "AUTO" : mode == MODE_ARME ? "FORCE_ARME" : "FORCE_VEILLE";
}

/* ------------------------------------------------------------------ rapport JSON */
void envoyerRapport(const char *statut, bool presence) {
  char msg[TAILLE_MSG];
  char heure[8] = "--:--";
  int h = minutesDuJour();
  if (h >= 0) snprintf(heure, sizeof heure, "%02d:%02d", h / 60, h % 60);
  snprintf(msg, sizeof msg,
           "{\"node_id\":\"%s\",\"timestamp\":%lu,\"presence\":%s,\"detections\":%lu,"
           "\"heure\":\"%s\",\"mode\":\"%s\",\"status\":\"%s\",\"seq\":%lu,\"rssi_dbm\":%d}",
           NODE_ID, (unsigned long)horodatage(), presence ? "true" : "false",
           (unsigned long)detections, heure, texteMode(), statut,
           (unsigned long)++seq, (int)WiFi.RSSI());
  publier(msg);
  dernierRapport = millis();
}

void rapportDeVie() { envoyerRapport(armee ? "ARME" : "VEILLE", false); }

/* ------------------------------------------------------------------ MQTT */
void recevoirCommande(char *topic, byte *contenu, unsigned int n) {
  String cmd;
  for (unsigned int i = 0; i < n; i++) cmd += (char)contenu[i];
  cmd.trim();
  Serial.print("CMD "); Serial.println(cmd);
  if      (cmd == "ARME")   mode = MODE_ARME;
  else if (cmd == "VEILLE") mode = MODE_VEILLE;
  else if (cmd == "AUTO")   mode = MODE_AUTO;
  else if (cmd != "STATUT") return;
  armee = calculerArmement();
  digitalWrite(BROCHE_LED, armee ? HIGH : LOW);
  rapportDeVie();
}

void tenterConnexionMqtt() {
  char statutHorsLigne[96];
  snprintf(statutHorsLigne, sizeof statutHorsLigne, "{\"node_id\":\"%s\",\"online\":false}", NODE_ID);
  Serial.print("MQTT : connexion a " MQTT_HOTE "... ");
  if (mqtt.connect(NODE_ID, MQTT_UTILISATEUR, MQTT_MDP, topicStatut, 1, true, statutHorsLigne)) {
    char statutEnLigne[128];
    snprintf(statutEnLigne, sizeof statutEnLigne,
             "{\"node_id\":\"%s\",\"online\":true,\"ip\":\"%s\"}", NODE_ID,
             WiFi.localIP().toString().c_str());
    mqtt.publish(topicStatut, statutEnLigne, true);
    mqtt.subscribe(topicCommande);
    Serial.println("OK");
    viderTampon();
  } else {
    Serial.printf("echec (code %d)\n", mqtt.state());
  }
}

/* ------------------------------------------------------------------ démarrage */
void setup() {
  Serial.begin(115200);
  pinMode(BROCHE_LED, OUTPUT);
  pinMode(BROCHE_PIR, INPUT_PULLDOWN);

  snprintf(topicDonnees,  sizeof topicDonnees,  "factory/security/%s", NODE_ID);
  snprintf(topicStatut,   sizeof topicStatut,   "factory/status/%s",   NODE_ID);
  snprintf(topicCommande, sizeof topicCommande, "factory/cmd/%s",      NODE_ID);
  Serial.printf("\nBOOT intrusion %s (chauffe du PIR : %lu s)\n", NODE_ID,
                (unsigned long)(CHAUFFE_PIR_MS / 1000));

  /* Interruption sur le front montant : quelqu'un entre dans le champ du PIR.
     Elle continue de fonctionner même si la boucle est bloquée dans une reconnexion MQTT. */
  attachInterrupt(digitalPinToInterrupt(BROCHE_PIR), mouvement, RISING);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_MDP);
  configTime(3600, 0, "pool.ntp.org", "time.google.com");   /* heure du Bénin : UTC+1 */

#if UTILISER_TLS
  if (strlen(CA_CERT) > 0) reseau.setCACert(CA_CERT); else reseau.setInsecure();
#endif
  mqtt.setServer(MQTT_HOTE, MQTT_PORT);
  mqtt.setCallback(recevoirCommande);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(10);
  mqtt.setSocketTimeout(3);

  armee = calculerArmement();
  digitalWrite(BROCHE_LED, armee ? HIGH : LOW);
  dernierRapport = millis() - PERIODE_MS + 5000;   /* premier rapport 5 s après le démarrage */
}

/* ------------------------------------------------------------------ boucle */
void loop() {
  uint32_t maintenant = millis();

  if (WiFi.status() == WL_CONNECTED) {
    if (!mqtt.connected() && maintenant - dernierEssaiMqtt >= REESSAI_MQTT_MS) {
      dernierEssaiMqtt = maintenant;
      tenterConnexionMqtt();
    }
    mqtt.loop();
  }

  /* Passage jour ↔ nuit (ou réception de l'heure NTP) : on le signale tout de suite */
  bool a = calculerArmement();
  if (a != armee) {
    armee = a;
    digitalWrite(BROCHE_LED, armee ? HIGH : LOW);
    Serial.println(armee ? "Surveillance ARMEE" : "Surveillance DESARMEE");
    rapportDeVie();
  }

  if (presenceIsr) {
    presenceIsr = false;
    if (millis() >= CHAUFFE_PIR_MS) {
      detections++;
      Serial.printf("DETECTION n=%lu (%s)\n", (unsigned long)detections, armee ? "armee" : "veille");
      if (armee && (!alerteEnvoyee || millis() - derniereAlerte >= ANTI_RAFALE_MS)) {
        alerteEnvoyee = true;
        derniereAlerte = millis();
        envoyerRapport("INTRUSION", true);       /* tout de suite : ENF1 */
      }
    }
  }

  if (millis() - dernierRapport >= PERIODE_MS) rapportDeVie();
}
