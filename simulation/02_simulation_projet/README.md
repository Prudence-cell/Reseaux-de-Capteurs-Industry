# Simulation complète du projet — Groupe 7 (TinyOS + Cooja)

Surveillance d'une ligne de production : **10 cartes simulées** aux positions exactes du plan
d'implantation (`architecture/generer_plan.py`), un réseau radio **multi-saut** (protocole CTP),
des capteurs simulés (température, comptage, présence) et une **passerelle** qui produit les
messages MQTT du cahier des charges et déclenche les alertes.

Ce guide explique, étape par étape, comment compiler, tester et regarder la simulation sous Linux.
Les résultats chiffrés et les explications détaillées sont dans le rapport :
`rapport/rapport_simulation.html` (et `.pdf`).

---

## 1. Ce qu'on simule

| Nœud Cooja | Repère du plan | Rôle | Programme (firmware) |
|---|---|---|---|
| 1 | GW | Passerelle, racine de l'arbre CTP | `passerelle.sky` |
| 2, 3, 4 | T1, T2, T3 | Température de M1 (découpe, seuil 85 °C), M2 (presse, 90 °C), M3 (four, 220 °C) | `thermique.sky` |
| 5, 6, 7 | C1, C2, C3 | Comptage des pièces en sortie de chaque machine | `comptage.sky` |
| 8, 9, 10 | P1, P2, P3 | Détection d'intrusion (PIR + buzzer = LED bleue) | `intrusion.sky` |

Correspondance avec le système réel : ESP32 → carte **Sky / TelosB** (`make telosb`) ;
WiFi → radio **IEEE 802.15.4** (CC2420) ; portée réglée à **20 m** (modèle radio UDGM).
À 20 m, P1, P2 et P3 sont trop loin de la passerelle : leurs messages passent par un voisin.

## 2. Organisation des fichiers

```
02_simulation_projet/
├── commun/              code partagé par les 4 applications
│   ├── Usine.h            paramètres (30 s, horloge d'usine...) + format du message radio
│   ├── Plan.h             GÉNÉRÉ depuis le plan : repères, n° de machine, seuils
│   ├── Console*.nc        écrire du texte lisible / recevoir des commandes (port série)
│   ├── Publication*.nc    envoi des rapports par CTP (petit tampon, suivi du parent)
│   ├── FlashInterneC.nc   mémoire flash interne (le compteur survit au redémarrage)
│   └── Makefile.commun    options de compilation communes
├── passerelle/  thermique/  comptage/  intrusion/    une application (= un type de carte) chacune
├── scenarios/
│   ├── generer_scenarios.py   plan d'implantation → fichiers .csc de Cooja
│   ├── scenario_demo.js       scénario automatique de la version avec fenêtres
│   ├── tests/                 un script de test par exigence (T1, T2, T4...)
│   └── csc/                   copie des .csc générés (usine.csc avec fenêtres + test_*.csc)
├── construire.sh        compile tout et génère les scénarios
├── tester.sh            lance les tests sans fenêtre
├── tout_relancer.sh     compile tout puis lance tous les tests
├── ouvrir_cooja.sh      ouvre la simulation avec fenêtres
├── firmwares/           copie des binaires .sky produits
├── resultats/           journaux des tests (un .log par test)
└── rapport/             rapport de simulation (HTML + PDF) et son générateur
```

## 3. Avant de commencer

Tout se passe dans la distribution WSL **Contiki** (Ubuntu 20.04), où sont déjà installés
TinyOS (`~/tinyos-main`), le compilateur `msp430-gcc`, `nescc` et Cooja (`~/contiki-ng/tools/cooja`).
Rien à installer.

Ouvrir un terminal Linux :

```bash
wsl -d Contiki
cd "/mnt/d/IFRI/Réseaux de capteurs/simulation/02_simulation_projet"
```

> **Pourquoi on ne compile pas directement ici ?** Le système de compilation de TinyOS échoue si le
> chemin contient des espaces ou des accents (« Réseaux de capteurs »). `construire.sh` copie donc
> les sources dans `~/projets/02_simulation_projet` et compile là-bas.

## 4. Étape 1 — Compiler

```bash
bash construire.sh          # ou : bash tout_relancer.sh  (compile puis lance tous les tests)
```

Ce que fait le script :

1. **Lit le plan** (`architecture/noeuds_cooja.csv` et `generer_plan.py`) et écrit `commun/Plan.h`
   et les fichiers de simulation `.csc` avec les positions en mètres.
2. **Copie** les sources dans `~/projets/02_simulation_projet`.
3. **Compile** chaque application : `make telosb` transforme le nesC en C, puis en binaire pour le
   microcontrôleur MSP430. Le binaire `build/telosb/main.exe` est renommé `passerelle.sky`, etc.
4. Compile aussi le nœud **intrus** (mauvaise clé, pour le test d'authentification ENF6).

Pour ne recompiler qu'un rôle pendant une modification : `bash construire.sh thermique`.

Le script affiche la taille de chaque programme. Une carte Sky a 48 Ko de mémoire programme (ROM)
et 10 Ko de RAM : on en utilise environ 20 Ko et 2,2 Ko.

## 5. Étape 2 — Lancer les tests automatiques (sans fenêtre)

```bash
bash tester.sh                  # tous les tests (environ 3 min)
bash tester.sh T2_surchauffe    # un seul test
```

Chaque test démarre Cooja **sans fenêtre** (`--no-gui`) avec un script (plugin ScriptRunner) qui :
écoute ce que chaque carte écrit, injecte des événements au bon moment (« la sonde lit 95 °C »,
« quelqu'un passe à 19h00 »...), mesure les délais avec l'horloge de Cooja, puis écrit des lignes
`MESURE ...` et `VERDICT ... OK/ECHEC`. Le journal complet est copié dans `resultats/<test>.log`.

Exigences non fonctionnelles retenues par le groupe : **ENF1** (latence < 10 s), **ENF6** (messages
authentifiés) et **ENF8** (un nœud défaillant peut être retiré sans arrêter le reste).

| Test | Exigence vérifiée | Ce que fait le script |
|---|---|---|
| `T1_periode` | EF1 : une mesure toutes les 30 s ± 2 s | mesure l'écart entre rapports pendant 10 min |
| `T2_surchauffe` | EF2, ENF1 : 95 °C → alerte < 10 s | force la sonde de M2 à 95 °C, chronomètre l'ALERTE |
| `T4_comptage` | EF5 : 100 pièces → compteur = 100 | fait passer 100 pièces ; redémarre aussi un nœud |
| `T5_intrusion` | EF6 : présence hors heures → alerte < 5 s | présences à 17h30, 19h00 et 08h30 |
| `T6_reseau` | ENF1 : latence < 10 s ; taux de livraison | 20 min de fonctionnement normal, 10 nœuds |
| `T6b_pertes` | idem avec des liens radio dégradés | 20 % de pertes à la limite de portée |
| `T9_panne` | ENF8 : un nœud retiré, les autres continuent | retire le relais T1 de la simulation |
| `ENF6_auth` | ENF6 : messages authentifiés | ajoute un 11e nœud sans la clé |

## 6. Étape 3 — Regarder la simulation avec les fenêtres

```bash
bash ouvrir_cooja.sh
```

Patienter ~15 s, puis cliquer sur **Start** en haut de la fenêtre « Simulation control ».
Un scénario de démonstration se déroule tout seul :

| Instant | Événement | Ce qu'on voit |
|---|---|---|
| 0–15 s | démarrage, construction de l'arbre CTP | lignes `PARENT aucun->1` |
| 40 s | passage sur le quai de réception (P2) à 17h40 | `DETECTION ... pas d'alerte` |
| 60 s | 18h00 : l'usine ferme | `HORLOGE 18:00 mode nuit` sur P1–P3 |
| 90 s | la sonde de la presse (T2) lit 95 °C | `ALERTE SURCHAUFFE MACHINE_02`, LED bleue |
| 100 s | quelqu'un entre par l'accueil (P1) à 18h40 | `ALERTE INTRUSION ZONE_01`, buzzer = LED bleue de P1 |
| 150 s | retour à la normale de T2 | `FIN_ALERTE` |

Les fenêtres ouvertes :

- **Network** : les 10 nœuds à leurs positions du plan (1 m = 11 pixels ; origine = coin nord-ouest
  du bâtiment). Le cercle vert = portée radio de 20 m, le cercle gris = zone d'interférence.
  Cliquer sur un nœud montre sa portée. Les flèches montrent les paquets.
- **Mote output** : tout ce qu'écrivent les cartes. Taper `ALERTE` dans le champ *Filter* pour ne
  voir que les alertes, ou `ID:1` pour ne voir que la passerelle.
- **Radio messages** : chaque paquet radio (données CTP et balises de routage).
- **Timeline** : pour chaque nœud, quand sa radio écoute / émet (bleu/vert) et l'état des LED.
- **Simulation script editor** : le scénario de démonstration (on peut le modifier).

### Piloter la simulation soi-même

Clic droit sur un nœud → *Mote tools* → **Serial port** : on peut taper une commande puis *Entrée*.

| Carte | Commande | Effet |
|---|---|---|
| thermique (2, 3, 4) | `H` / `N` | sonde forcée à seuil + 5 °C / retour à la normale |
| comptage (5, 6, 7) | `+` `A` `M` `Z` `R` | une pièce / arrêt auto / marche auto / remise à zéro / redémarrage |
| intrusion (8, 9, 10) | `P` | une présence devant le capteur |
| passerelle (1) | `S` | statistiques tout de suite |

Pour simuler une panne : clic droit sur un nœud → *Remove mote*.

## 7. Lire les lignes de la passerelle

```
RX src=8 seq=12 sauts=2 parent=2 age=4 | factory/security/ZONE_01 {"node_id":"ZONE_01",...}
```

- `src`, `seq` : qui a envoyé, et le numéro du rapport (sert au taux de livraison) ;
- `sauts` : nombre de transmissions radio pour arriver (2 = un relais) ; `parent` : le premier relais ;
- `age` : temps passé dans le tampon du capteur (ms) ;
- après `|` : le **topic MQTT** et le **JSON** exactement comme dans le cahier des charges.

Autres lignes : `ALERTE SURCHAUFFE`, `ALERTE INTRUSION`, `ALERTE NOEUD_MUET`, `REJET_AUTH`,
`STAT` (toutes les 60 s : reçus, perdus, doublons, sauts, parent de chaque nœud).

## 8. Modifier la simulation

- **Déplacer un nœud** : changer ses coordonnées dans `architecture/generer_plan.py`, lancer
  `python generer_plan.py` (dans `architecture/`), puis `bash construire.sh`. Cooja et le plan
  restent identiques.
- **Changer un seuil** : dans la liste `MACHINES` de `generer_plan.py` (même procédure).
- **Changer la période** (30 s) ou l'horloge d'usine : `commun/Usine.h`.
- **Changer la portée radio** : `PORTEE_COOJA` dans `generer_plan.py`.

## 9. Pièges rencontrés (et corrigés) — utiles pour la suite

1. **La « milliseconde » de TinyOS vaut 1/1024 s.** `startPeriodic(30000)` donnait 29,3 s.
   Toutes les durées passent par `TICKS(ms)` (voir `Usine.h`).
2. **Écrire en flash avec les interruptions actives fait planter le MSP430** (mspsim l'émule :
   « Got interrupt while flash controller blocks CPU »). L'écriture est dans un bloc `atomic`.
3. **Accusés de réception radio matériels.** Par défaut, TinyOS les envoie par logiciel ; la
   passerelle, occupée à écrire sur le port série, en ratait et l'arbre CTP devenait instable.
   Option `CC2420_HW_ACKNOWLEDGEMENTS`.
4. Dans un script Cooja, `TIMEOUT(...)` doit contenir un **nombre écrit en clair**.
5. Les scripts `.sh` doivent avoir des fins de ligne **Unix (LF)**, sinon bash refuse de les lire.
6. `PrintfC` envoie du binaire : on écrit du texte brut avec `UartByte` (composant `ConsoleC`).
7. Si un Cooja est déjà ouvert, `./gradlew run` reste bloqué : on lance Cooja directement avec
   Java (`../outils/cooja.sh`).

## 10. Régénérer le rapport

Depuis Windows (Python + matplotlib) :

```bash
python rapport/generer_rapport.py
```

Il lit `resultats/*.log`, trace les graphiques et produit `rapport/rapport_simulation.html` ;
le PDF est imprimé avec Chrome en mode sans fenêtre (voir la fin du script).
