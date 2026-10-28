# Implémentation physique — 3 ESP32 + VPS

Version matérielle de la simulation `simulation/02_simulation_projet`, avec **un capteur de chaque type** :

| Carte | Croquis | Capteur | Broche | Topic de données |
|---|---|---|---|---|
| ESP32 n°1 | `esp32_thermique/` | DHT11 (température machine M1) | GPIO 4 | `factory/machines/MACHINE_01` |
| ESP32 n°2 | `esp32_comptage/` | Module IR d'obstacle (comptage poste 1) | GPIO 27 | `factory/production/POSTE_01` |
| ESP32 n°3 | `esp32_intrusion/` | PIR HC-SR501 (intrusion zone 1) | GPIO 26 | `factory/security/ZONE_01` |

Le **VPS** héberge le broker MQTT (Mosquitto) et le serveur / la base de connaissances.

```
 ESP32 thermique ─┐
 ESP32 comptage  ─┼── Wi-Fi ── Internet ──► VPS : Mosquitto (MQTT) ──► serveur + base
 ESP32 intrusion ─┘                              ▲
                                                 └── commandes : factory/cmd/<NODE_ID>
```

## Différences avec la simulation (à dire dans le rapport)

- **Topologie en étoile Wi-Fi** au lieu d'un arbre multi-sauts CTP : chaque ESP32 parle directement au
  broker. Il n'y a plus de nœud passerelle : c'est le VPS qui joue ce rôle (alertes, suivi des nœuds).
- **DHT11 : 0 à 50 °C seulement.** Le seuil réel de M1 (85 °C) est inatteignable : la démo utilise
  `SEUIL_C = 30 °C` (pincer le capteur entre les doigts suffit). En production : thermocouple K + MAX6675.
- **ENF6 (authentification)** : un identifiant/mot de passe Mosquitto par nœud + ACL (un nœud ne peut
  publier que sur ses topics). Le MAC FNV-1a de la simulation n'est plus nécessaire. TLS (port 8883)
  recommandé, sinon les mots de passe circulent en clair sur Internet.
- **ENF8 (nœud retiré)** : « testament » MQTT (Last Will). Si une carte est débranchée, le broker publie
  lui-même `{"online":false}` sur `factory/status/<NODE_ID>` après ~15 s (keep-alive 10 s).
- **ENF1 (latence)** : alertes (surchauffe, intrusion) publiées dès la détection, sans attendre les 30 s.
- Comme dans la simulation : rapport toutes les 30 s, numéro `seq` (taux de livraison calculé par le
  serveur), tampon de 16 messages si le broker est injoignable, compteur de pièces sauvegardé en flash.

## Câblage

- **DHT11** (module 3 broches) : VCC → 3V3, GND → GND, DATA → GPIO 4 (DHT11 nu : 10 kΩ entre DATA et 3V3).
- **IR (FC-51 / TCRT5000)** : VCC → **3V3** (pas 5 V), GND → GND, OUT → GPIO 27. Sortie à 0 V devant un objet.
- **PIR HC-SR501** : VCC → **VIN (5 V)**, GND → GND, OUT → GPIO 26. Cavalier sur « H », potentiomètre de
  durée au minimum. Prévoir ~60 s de chauffe (les détections sont ignorées pendant ce temps).

## Arduino IDE

1. Paquet de cartes **esp32** (Espressif), carte « ESP32 Dev Module ».
2. Bibliothèques : **PubSubClient** (Nick O'Leary), **DHT sensor library** (Adafruit) + **Adafruit Unified Sensor**.
3. Dans chaque `.ino`, remplir le bloc « À ADAPTER » (Wi-Fi, IP du VPS, mot de passe du nœud).
4. Téléverser, ouvrir le moniteur série à **115200 bauds**.

Les trois croquis compilent avec le paquet esp32 3.3.5 (~70 % de la flash).
Attention : l'ESP32 ne fonctionne qu'en Wi-Fi **2,4 GHz** (un partage de connexion de téléphone convient).

## VPS (Ubuntu/Debian)

```bash
sudo apt install mosquitto mosquitto-clients
sudo cp vps/usine.conf /etc/mosquitto/conf.d/
sudo cp vps/acl /etc/mosquitto/acl
sudo mosquitto_passwd -c /etc/mosquitto/passwd MACHINE_01   # -c seulement la 1re fois
sudo mosquitto_passwd    /etc/mosquitto/passwd POSTE_01
sudo mosquitto_passwd    /etc/mosquitto/passwd ZONE_01
sudo mosquitto_passwd    /etc/mosquitto/passwd serveur
sudo chown mosquitto: /etc/mosquitto/passwd /etc/mosquitto/acl
sudo systemctl restart mosquitto
sudo ufw allow 1883/tcp        # ou 8883 avec TLS
```

## Tester

```bash
# tout voir
mosquitto_sub -h IP_DU_VPS -u serveur -P MOT_DE_PASSE -t 'factory/#' -v

# démo intrusion en journée : forcer l'armement, puis revenir à l'horaire 08h-18h
mosquitto_pub -h IP_DU_VPS -u serveur -P MOT_DE_PASSE -t factory/cmd/ZONE_01 -m ARME
mosquitto_pub -h IP_DU_VPS -u serveur -P MOT_DE_PASSE -t factory/cmd/ZONE_01 -m AUTO

# remise à zéro du compteur, rapport immédiat d'un nœud
mosquitto_pub -h IP_DU_VPS -u serveur -P MOT_DE_PASSE -t factory/cmd/POSTE_01 -m RAZ
mosquitto_pub -h IP_DU_VPS -u serveur -P MOT_DE_PASSE -t factory/cmd/MACHINE_01 -m STATUT
```

| Test | Action | Attendu |
|---|---|---|
| EF1 | attendre | un message par nœud toutes les 30 s |
| EF2 / ENF1 | pincer le DHT11 | `"status":"ALERTE"` immédiat, puis `"OK"` sous 28 °C |
| EF5 | passer la main devant l'IR 10 fois | `production_count` +10 ; conservé après un reset de la carte |
| EF6 / ENF1 | `ARME`, puis bouger devant le PIR | `"status":"INTRUSION"` immédiat |
| ENF6 | mauvais mot de passe dans un croquis | moniteur série : `echec (code 5)`, rien publié |
| ENF8 | débrancher une carte | `factory/status/<NODE_ID>` → `"online":false` en ~15 s |

Exemple de message (thermique) :

```json
{"node_id":"MACHINE_01","timestamp":1792512000,"temperature_c":31.0,"humidity_pct":55,"seuil_c":30.0,
 "seuil_reel_c":85.0,"machine":"Decoupe","status":"ALERTE","seq":12,"rssi_dbm":-58}
```
