/*
 * ESP32 n°2 — NŒUD DE COMPTAGE (poste 1) avec un capteur infrarouge.
 *
 * Équivalent physique de simulation/02_simulation_projet/comptage :
 *   - chaque pièce qui coupe le faisceau IR incrémente le compteur (EF5) ;
 *   - le compteur cumulé est sauvegardé en mémoire flash (NVS) à chaque pièce :
 *     après une coupure de courant le comptage reprend où il en était ;
 *   - toutes les 30 s : rapport avec le compteur cumulé et la cadence (pièces/min).
 *
 * Réseau : Wi-Fi → broker MQTT Mosquitto sur le VPS.
 *   publie   factory/production/POSTE_01   (mesures, JSON)
 *   publie   factory/status/POSTE_01       (en ligne / hors ligne, « retained »)
 *   écoute   factory/cmd/POSTE_01          (STATUT = rapport tout de suite, RAZ = compteur à 0)
 *
 * Câblage module IR d'obstacle (FC-51 / TCRT5000, 3 broches) :
 *   VCC → 3V3 (PAS 5 V : sa sortie aurait alors 5 V, trop pour l'ESP32), GND → GND, OUT → GPIO 27.
 *   La sortie passe à 0 V quand un objet est devant (LED verte du module allumée).
 *   Régler la distance de détection avec le potentiomètre bleu du module.
 *
 * Bibliothèque : « PubSubClient » (Nick O'Leary). Carte : « ESP32 Dev Module ».
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <time.h>

/* ================================================================== À ADAPTER */
#define WIFI_SSID      "NOM_DU_WIFI"
#define WIFI_MDP       "MOT_DE_PASSE_WIFI"
#define MQTT_HOTE      "IP_OU_NOM_DU_VPS"
#define MQTT_UTILISATEUR "POSTE_01"           /* un compte Mosquitto PAR nœud (ENF6) */
#define MQTT_MDP       "MOT_DE_PASSE_POSTE_01"
#define UTILISER_TLS   0                      /* 1 = port 8883 chiffré (recommandé sur Internet) */

#define NODE_ID        "POSTE_01"
#define IR_ACTIF_BAS   1      /* 1 : sortie à 0 V quand objet (FC-51). 0 : capteur actif à l'état haut */
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
Preferences flash;

/* ------------------------------------------------------------------ paramètres (ms) */
const uint32_t PERIODE_MS      = 30000;   /* EF1 */
const uint32_t REESSAI_MQTT_MS = 5000;
/* Anti-rebond : deux pièces ne peuvent pas passer à moins de 150 ms l'une de l'autre.
   Le comparateur du module « rebondit » quand le bord de la pièce entre dans le faisceau. */
const uint32_t ANTI_REBOND_MS  = 150;

const int BROCHE_IR  = 27;
const int BROCHE_LED = 2;                 /* clignote à chaque pièce */

char topicDonnees[64], topicStatut[64], topicCommande[64];

/* Partagés avec l'interruption : « volatile » */
volatile uint32_t piecesIsr = 0;          /* pièces vues par l'interruption, pas encore traitées */
volatile uint32_t dernierFrontMs = 0;

uint32_t compteur = 0;                    /* compteur cumulé (sauvegardé en flash) */
uint32_t piecesPeriode = 0;
uint32_t debutPeriode = 0;
uint32_t seq = 0;
uint32_t dernierRapport = 0, dernierEssaiMqtt = 0;

/* ------------------------------------------------------------------ interruption IR
   Elle ne fait que compter : écrire en flash ou publier depuis une interruption est interdit. */
void IRAM_ATTR pieceDetectee() {
  uint32_t t = millis();
  if (t - dernierFrontMs >= ANTI_REBOND_MS) {
    piecesIsr++;
    dernierFrontMs = t;
  }
}

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

/* ------------------------------------------------------------------ rapport JSON */
void envoyerRapport() {
  char msg[TAILLE_MSG];
  uint32_t duree = millis() - debutPeriode;
  /* cadence = pièces de la période ramenées à une minute */
  uint32_t cadence = duree > 0 ? (piecesPeriode * 60000UL + duree / 2) / duree : 0;
  snprintf(msg, sizeof msg,
           "{\"node_id\":\"%s\",\"timestamp\":%lu,\"production_count\":%lu,\"cadence_ppm\":%lu,"
           "\"status\":\"OK\",\"seq\":%lu,\"rssi_dbm\":%d}",
           NODE_ID, (unsigned long)horodatage(), (unsigned long)compteur, (unsigned long)cadence,
           (unsigned long)++seq, (int)WiFi.RSSI());
  publier(msg);
  piecesPeriode = 0;
  debutPeriode = millis();
  dernierRapport = millis();
}

void sauvegarder() {
  flash.putULong("compteur", compteur);
}

/* ------------------------------------------------------------------ MQTT */
void recevoirCommande(char *topic, byte *contenu, unsigned int n) {
  String cmd;
  for (unsigned int i = 0; i < n; i++) cmd += (char)contenu[i];
  cmd.trim();
  Serial.print("CMD "); Serial.println(cmd);
  if (cmd == "RAZ") {
    compteur = 0;
    piecesPeriode = 0;
    sauvegarder();
    envoyerRapport();
  } else if (cmd == "STATUT") {
    envoyerRapport();
  }
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
  pinMode(BROCHE_IR, INPUT_PULLUP);

  snprintf(topicDonnees,  sizeof topicDonnees,  "factory/production/%s", NODE_ID);
  snprintf(topicStatut,   sizeof topicStatut,   "factory/status/%s",     NODE_ID);
  snprintf(topicCommande, sizeof topicCommande, "factory/cmd/%s",        NODE_ID);

  /* Restauration du compteur (flash NVS, espace de noms « comptage ») */
  flash.begin("comptage", false);
  compteur = flash.getULong("compteur", 0);
  Serial.printf("\nBOOT comptage %s compteur restaure=%lu\n", NODE_ID, (unsigned long)compteur);

  /* Front « l'objet arrive devant le capteur » : descendant si actif bas */
  attachInterrupt(digitalPinToInterrupt(BROCHE_IR), pieceDetectee, IR_ACTIF_BAS ? FALLING : RISING);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_MDP);
  configTime(3600, 0, "pool.ntp.org", "time.google.com");

#if UTILISER_TLS
  if (strlen(CA_CERT) > 0) reseau.setCACert(CA_CERT); else reseau.setInsecure();
#endif
  mqtt.setServer(MQTT_HOTE, MQTT_PORT);
  mqtt.setCallback(recevoirCommande);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(10);
  mqtt.setSocketTimeout(3);

  debutPeriode = millis();
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

  /* Récupère les pièces comptées par l'interruption (section critique : lecture + remise à 0) */
  noInterrupts();
  uint32_t nouvelles = piecesIsr;
  piecesIsr = 0;
  interrupts();
  if (nouvelles > 0) {
    compteur += nouvelles;
    piecesPeriode += nouvelles;
    sauvegarder();
    digitalWrite(BROCHE_LED, !digitalRead(BROCHE_LED));
    Serial.printf("PIECE n=%lu\n", (unsigned long)compteur);
  }

  if (millis() - dernierRapport >= PERIODE_MS) envoyerRapport();
}
