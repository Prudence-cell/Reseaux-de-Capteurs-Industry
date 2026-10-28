# Simulation du projet — version Contiki-NG (Groupe 7)

C'est la **traduction en Contiki-NG** de la simulation TinyOS (`../02_simulation_projet`).
Même usine, mêmes 10 nœuds aux positions du plan, mêmes rôles, même format de messages et
**mêmes tests automatiques**. Seul le système d'exploitation des nœuds change.

Exigences non fonctionnelles retenues : **ENF1** (latence < 10 s), **ENF6** (messages
authentifiés), **ENF8** (un nœud défaillant peut être retiré sans arrêter le reste).

---

## 1. TinyOS → Contiki-NG : ce qui change

| | TinyOS (version 02) | Contiki-NG (cette version) |
|---|---|---|
| Langage | nesC : composants câblés avec `->`, événements | C classique : **processus** (`PROCESS_THREAD`) qui attendent des événements (`PROCESS_WAIT_EVENT`) |
| Carte simulée | Sky (MSP430) émulée au cycle près | **Cooja mote** : le code Contiki tourne directement dans Cooja |
| Routage multi-saut | **CTP** (arbre de collecte vers la racine) | **RPL** (routage IPv6 des réseaux basse consommation), passerelle = racine |
| Transport | message CTP | **UDP sur IPv6** (6LoWPAN) vers l'adresse de la racine |
| Accusé de réception | du voisin (CTP `sendDone`) | **de la passerelle** : acquittement UDP signé, renvoi au bout de 3 s sans réponse |
| Minuteries | `TimerMilli` (1/1024 s, piège !) | `etimer` en vraies millisecondes |
| Affichage | composant maison `ConsoleC` (UartByte) | `printf` |
| Commandes série | `UartStream.receivedByte` | événement `serial_line_event_message` |
| Mémoire persistante | flash interne du MSP430 | fichier du système de fichiers **CFS** de Contiki |
| Nombre de sauts | champ THL de CTP | champ *hop limit* d'IPv6 (64 moins 1 par relais) |

Les lignes écrites par les nœuds sont **identiques** à celles de TinyOS (`PUB`, `RX ... | topic {json}`,
`PARENT`, `ALERTE ...`, `STAT`) : les scripts de test sont donc réutilisés tels quels
(sauf `scenarios/tests/commun.js`, voir § 6).

## 2. Les fichiers

```
03_contiki_ng/
├── commun/
│   ├── usine.h          paramètres, format du message, authentification, heure d'usine
│   ├── plan.h           GÉNÉRÉ depuis le plan : repères, n° de machine, seuils
│   ├── publication.c/.h envoi UDP vers la racine RPL : tampon, acquittement, renvoi, parent
│   └── conf-commune.h   réglages Contiki (journaux internes coupés, taille des lignes série)
├── passerelle/  thermique/  comptage/  intrusion/   un programme Contiki chacun
├── intrus/              le programme thermique avec une autre clé (test ENF6)
├── scenarios/
│   ├── generer_scenarios.py   plan d'implantation → plan.h + fichiers .csc (Cooja motes)
│   ├── tests/commun.js        seule différence avec les tests TinyOS
│   └── csc/                   copie des .csc générés
├── construire.sh  tester.sh  ouvrir_cooja.sh  tout_relancer.sh
└── resultats/           journaux des tests
```

Chaque dossier de programme contient un `Makefile` (qui inclut celui de Contiki-NG) et un
`project-conf.h` (qui inclut `conf-commune.h`).

## 3. Compiler

```bash
wsl -d Contiki
cd "/mnt/d/IFRI/Réseaux de capteurs/simulation/03_contiki_ng"
bash construire.sh
```

Le script copie les sources dans `~/projets/03_contiki_ng` (Contiki, comme TinyOS, n'aime pas
les espaces ni les accents dans les chemins), génère `plan.h` et les `.csc`, puis compile chaque
programme avec `make TARGET=cooja`. Résultat attendu : `OK (0 avertissement(s))` pour les 5 programmes.

> Pourquoi des **Cooja motes** et pas des cartes Sky ? Contiki-NG exige `msp430-gcc` ≥ 4.7 pour
> la Sky ; celui installé (4.6.3) est celui de TinyOS. Les Cooja motes sont la plateforme des
> exemples et tests officiels de Contiki-NG et ne demandent rien d'installer.

## 4. Lancer les tests (sans fenêtre)

```bash
bash tester.sh                  # tous les tests (environ 1 min)
bash tester.sh T9_panne         # un seul test
bash tout_relancer.sh           # compile puis lance tout
```

Mêmes tests que la version TinyOS : `T1_periode`, `T2_surchauffe`, `T4_comptage`,
`T5_intrusion`, `T6_reseau` (ENF1), `T6b_pertes`, `T9_panne` (ENF8), `ENF6_auth` (ENF6),
plus les incréments `I1_direct` et `I2_multisaut` (`bash tester.sh I1_direct I2_multisaut`).

## 5. Regarder la simulation avec les fenêtres

```bash
bash ouvrir_cooja.sh
```

Cooja compile les programmes (quelques secondes), puis cliquer sur **Start**. Le scénario de
démonstration est le même qu'en TinyOS (P2 à 17h40 sans alerte, surchauffe de M2 à 90 s,
intrusion à l'entrée à 100 s...). Pour envoyer une commande à un nœud : clic droit →
*Mote tools* → **Serial port**, taper la commande (`H`, `N`, `+`, `A`, `M`, `Z`, `R`, `P`, `S`).
Dans **Radio messages**, on voit cette fois les paquets IPv6/RPL (DIO, DAO, UDP).

## 6. Résultats (code actuel)

| Exigence | Test | TinyOS (CTP) | Contiki-NG (RPL + UDP) |
|---|---|---|---|
| EF1 : période 30 s ± 2 s | T1 | 30,00 s | 30,00 s |
| EF2/ENF1 : 95 °C → alerte < 10 s | T2 | 0,87 s | 0,86 s |
| EF5 : 100 pièces → 100 | T4 | 100 / 100 | 100 / 100 |
| EF6 : intrusion de nuit → alerte < 5 s | T5 | 0,05 s | 0,03 à 0,05 s |
| ENF1 : latence capteur → passerelle | T6 | moy. 30 ms, max 47 ms | moy. 50 ms, 95 % < 72 ms, max 4,9 s* |
| Taux de livraison | T6 / T6b | 100 % / 100 % | 100 % / 100 % |
| ENF8 : relais T1 retiré | T9 | rapports de P1 rétablis en 44 s | rétablis en 15 s |
| ENF6 : intrus rejeté | ENF6 | 10 rapports rejetés, 0 légitime | 96 envois rejetés, 0 légitime |

\* Le maximum de 4,9 s est le **tout premier rapport** de C1, qui a attendu que RPL rattache le
nœud au réseau. Ensuite, aucun rapport ne dépasse 200 ms.

Ce qu'on observe :
- **Entrée dans le réseau plus lente avec RPL** : un nœud n'est « joignable » qu'après l'échange
  DIO → DAO → DAO-ACK avec la racine (≈ 10 à 17 s au démarrage), alors que CTP envoie dès qu'il
  a un parent. C'est pourquoi `tests/commun.js` compte comme « différé » (et exclut des latences)
  un rapport resté plus de 5 s dans le tampon (champ `age` de la ligne RX).
- **Reconvergence plus rapide avec RPL** (T9) : 15 s au lieu de 44 s, grâce à l'acquittement de
  bout en bout renvoyé au bout de 3 s et à la détection de parent injoignable de RPL.
- **Plus de trafic pour l'intrus** (ENF6) : sans acquittement valable, il renvoie toutes les 3 s.

## 7. Limites propres à cette version

- **Pas de vrai redémarrage** : sur un Cooja mote, `watchdog_reboot()` ne fait rien. La commande
  `R` du nœud de comptage fait un **redémarrage logiciel** (mémoire du programme remise à zéro,
  numéros de rapport repartis de 1, compteur relu dans le fichier CFS). Le test T4 vérifie donc la
  logique de sauvegarde, pas une vraie coupure d'alimentation.
- **Pas d'émulation de la carte** : pas de contrainte de mémoire (10 Ko de RAM sur une Sky) ni de
  temps processeur réaliste. Pour une comparaison stricte avec TinyOS, il faudrait installer un
  `msp430-gcc` récent et compiler pour `TARGET=sky`.
- Mêmes limites que la version TinyOS pour le reste (modèle radio UDGM idéal, authentification
  pédagogique, trajet passerelle → serveur MQTT non simulé).
