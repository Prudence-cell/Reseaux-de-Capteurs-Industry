/*
 * ESP32 n°1 — NŒUD THERMIQUE (machine M1) avec un DHT11.
 *
 * Équivalent physique de simulation/02_simulation_projet/thermique :
 *   - LECTURE toutes les 2 s : si la température dépasse le seuil, on publie TOUT DE SUITE
 *     un message « ALERTE » (sans attendre les 30 s) → ENF1 (latence) ;
 *   - retour sous (seuil - 2 °C) : message « OK » immédiat (hystérésis, pas de clignotement) ;
 *   - toutes les 30 s : rapport périodique (EF1).
 *
 * Réseau : Wi-Fi → broker MQTT Mosquitto sur le VPS.
 *   publie   factory/machines/MACHINE_01   (mesures, JSON)
 *   publie   factory/status/MACHINE_01     (en ligne / hors ligne, « retained »)
 *   écoute   factory/cmd/MACHINE_01        (commande : STATUT = rapport tout de suite)
 *
 * Câblage DHT11 (module 3 broches) : VCC → 3V3, GND → GND, DATA → GPIO 4.
 *   (DHT11 nu à 4 broches : ajouter une résistance de 10 kΩ entre DATA et 3V3.)
 *
 * Bibliothèques (Gestionnaire de bibliothèques) : « PubSubClient » (Nick O'Leary),
 *   « DHT sensor library » (Adafruit) + « Adafruit Unified Sensor ».
 * Carte : « ESP32 Dev Module » (paquet esp32 d'Espressif).
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <time.h>

/* ================================================================== À ADAPTER */
#define WIFI_SSID      "NOM_DU_WIFI"
#define WIFI_MDP       "MOT_DE_PASSE_WIFI"
#define MQTT_HOTE      "IP_OU_NOM_DU_VPS"
#define MQTT_UTILISATEUR "MACHINE_01"         /* un compte Mosquitto PAR nœud (ENF6) */
#define MQTT_MDP       "MOT_DE_PASSE_MACHINE_01"
#define UTILISER_TLS   0                      /* 1 = port 8883 chiffré (recommandé sur Internet) */

#define NODE_ID        "MACHINE_01"
#define NOM_MACHINE    "Decoupe"

/* PIÈGE DHT11 : il ne mesure que de 0 à 50 °C. Le vrai seuil de M1 (85 °C) est donc
   impossible à atteindre : pour la démonstration on prend 30 °C (il suffit de pincer
   le capteur entre les doigts ou de souffler dessus). En production : sonde type K + MAX6675. */
#define SEUIL_C        30.0f
#define SEUIL_REEL_C   85.0f                  /* seulement recopié dans le JSON, pour mémoire */
#define HYSTERESIS_C   2.0f
/* ================================================================== */

#if UTILISER_TLS
#include <WiFiClientSecure.h>
#define MQTT_PORT 8883
/* Certificat de l'autorité qui a signé celui du VPS (ex. ISRG Root X1 pour Let's Encrypt).
   Laissé vide : chiffrement sans vérification du serveur (acceptable pour un TP seulement). */
static const char CA_CERT[] = "";
WiFiClientSecure reseau;
#else
#define MQTT_PORT 1883
WiFiClient reseau;
#endif
PubSubClient mqtt(reseau);

/* ------------------------------------------------------------------ paramètres (ms) */
const uint32_t PERIODE_MS      = 30000;   /* EF1 : un rapport toutes les 30 s */
const uint32_t LECTURE_MS      = 2000;    /* le DHT11 ne supporte pas plus d'une lecture/s */
const uint32_t REESSAI_MQTT_MS = 5000;
const int      ERREURS_MAX     = 3;       /* lectures ratées d'affilée avant « ERREUR_CAPTEUR » */

const int BROCHE_DHT = 4;
const int BROCHE_LED = 2;                 /* LED bleue de la carte = machine en alerte */

DHT dht(BROCHE_DHT, DHT11);

char topicDonnees[64], topicStatut[64], topicCommande[64];

float temperature = NAN, humidite = NAN;
bool enAlerte = false;
int erreursDht = 0;
uint32_t seq = 0;
uint32_t derniereLecture = 0, dernierRapport = 0, dernierEssaiMqtt = 0;

/* ------------------------------------------------------------------ tampon hors ligne
   Comme CAPACITE_TAMPON dans la simulation : si le broker est injoignable, on garde
   les 16 derniers messages (chacun porte déjà son horodatage) et on les envoie au retour. */
const int CAPACITE_TAMPON = 16;
const int TAILLE_MSG      = 256;
char tampon[CAPACITE_TAMPON][TAILLE_MSG];
int teteTampon = 0, nbEnAttente = 0;
uint32_t perdusTampon = 0;

void mettreEnTampon(const char *msg) {
  if (nbEnAttente == CAPACITE_TAMPON) {          /* plein : on sacrifie le plus ancien */
    teteTampon = (teteTampon + 1) % CAPACITE_TAMPON;
    nbEnAttente--;
    perdusTampon++;
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

/* Horodatage Unix (NTP) ; 0 tant que l'heure n'est pas encore connue */
uint32_t horodatage() {
  time_t t = time(nullptr);
  return t > 1700000000 ? (uint32_t)t : 0;
}

/* ------------------------------------------------------------------ rapport JSON */
void envoyerRapport(const char *statut) {
  char msg[TAILLE_MSG];
  char t[12], h[12];
  if (isnan(temperature)) strcpy(t, "null"); else snprintf(t, sizeof t, "%.1f", temperature);
  if (isnan(humidite))    strcpy(h, "null"); else snprintf(h, sizeof h, "%.0f", humidite);
  snprintf(msg, sizeof msg,
           "{\"node_id\":\"%s\",\"timestamp\":%lu,\"temperature_c\":%s,\"humidity_pct\":%s,"
           "\"seuil_c\":%.1f,\"seuil_reel_c\":%.1f,\"machine\":\"%s\",\"status\":\"%s\","
           "\"seq\":%lu,\"rssi_dbm\":%d}",
           NODE_ID, (unsigned long)horodatage(), t, h, SEUIL_C, SEUIL_REEL_C, NOM_MACHINE,
           statut, (unsigned long)++seq, (int)WiFi.RSSI());
  publier(msg);
  dernierRapport = millis();
}

const char *statutCourant() {
  if (erreursDht >= ERREURS_MAX) return "ERREUR_CAPTEUR";
  return enAlerte ? "ALERTE" : "OK";
}

/* ------------------------------------------------------------------ lecture du capteur */
void lireCapteur() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    erreursDht++;
    Serial.println("DHT11 : lecture ratee");
    if (erreursDht == ERREURS_MAX) envoyerRapport("ERREUR_CAPTEUR");   /* une seule fois */
    return;
  }
  erreursDht = 0;
  temperature = t;
  humidite = h;

  if (temperature > SEUIL_C && !enAlerte) {
    enAlerte = true;
    digitalWrite(BROCHE_LED, HIGH);
    Serial.printf("ALERTE surchauffe %.1f C > seuil %.1f C\n", temperature, SEUIL_C);
    envoyerRapport("ALERTE");                      /* tout de suite : ENF1 */
  } else if (enAlerte && temperature <= SEUIL_C - HYSTERESIS_C) {
    enAlerte = false;
    digitalWrite(BROCHE_LED, LOW);
    Serial.printf("FIN_ALERTE %.1f C\n", temperature);
    envoyerRapport("OK");
  }
}

/* ------------------------------------------------------------------ MQTT */
void recevoirCommande(char *topic, byte *contenu, unsigned int n) {
  String cmd;
  for (unsigned int i = 0; i < n; i++) cmd += (char)contenu[i];
  cmd.trim();
  Serial.print("CMD "); Serial.println(cmd);
  if (cmd == "STATUT") envoyerRapport(statutCourant());
}

void tenterConnexionMqtt() {
  char statutHorsLigne[96];
  snprintf(statutHorsLigne, sizeof statutHorsLigne, "{\"node_id\":\"%s\",\"online\":false}", NODE_ID);
  Serial.print("MQTT : connexion a " MQTT_HOTE "... ");
  /* « Testament » (Last Will) : si le nœud disparaît sans prévenir (pile débranchée,
     carte retirée), c'est le BROKER qui publiera « online:false » → ENF8. */
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
    Serial.printf("echec (code %d)\n", mqtt.state());   /* 4/5 = identifiants refusés (ENF6) */
  }
}

/* ------------------------------------------------------------------ démarrage */
void setup() {
  Serial.begin(115200);
  pinMode(BROCHE_LED, OUTPUT);
  dht.begin();

  snprintf(topicDonnees,  sizeof topicDonnees,  "factory/machines/%s", NODE_ID);
  snprintf(topicStatut,   sizeof topicStatut,   "factory/status/%s",   NODE_ID);
  snprintf(topicCommande, sizeof topicCommande, "factory/cmd/%s",      NODE_ID);
  Serial.printf("\nBOOT thermique %s (%s) seuil=%.1f C\n", NODE_ID, NOM_MACHINE, SEUIL_C);

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
  mqtt.setKeepAlive(10);        /* le broker déclare le nœud mort après ~15 s de silence */
  mqtt.setSocketTimeout(3);     /* ne pas rester bloqué 15 s si le VPS ne répond pas */

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

  if (maintenant - derniereLecture >= LECTURE_MS) {
    derniereLecture = maintenant;
    lireCapteur();
  }
  if (millis() - dernierRapport >= PERIODE_MS) envoyerRapport(statutCourant());
}
