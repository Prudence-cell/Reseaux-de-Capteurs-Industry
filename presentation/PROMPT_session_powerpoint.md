# Prompt — génération du PowerPoint de l'exposé (Groupe 7)

> À coller tel quel au début d'une nouvelle session Claude Code ouverte dans le dossier
> `D:\IFRI\Réseaux de capteurs`.

---

Tu prépares le **support PowerPoint de l'exposé oral** du Groupe 7 (IFRI, cours « Réseaux de
capteurs sans fil & IoT », Dr Ida Tognisse). Le projet : un **système de surveillance d'une ligne de
production industrielle** (température des machines, comptage des pièces, détection d'intrusion,
alertes centralisées). Tout le travail est déjà fait et se trouve dans ce dossier. Ton rôle est d'en
tirer une présentation claire et professionnelle, **pas de refaire le projet ni de modifier ses fichiers**.

Écris tout en français. L'utilisateur est étudiant : explique brièvement tes choix au fur et à mesure.

## 1. Avant de produire quoi que ce soit, pose ces questions (une seule fois, regroupées)

1. **Durée de l'exposé** et nombre de diapositives souhaité (par défaut : 20 min → 16 à 20 diapos).
2. **Noms des membres** du groupe et répartition de la parole (pour la page de titre et, si
   besoin, une mention de l'orateur par partie).
3. **Date de la soutenance**.
4. **Prototype physique** : les 3 ESP32 ont-ils été montés et testés pour de vrai ? Y a-t-il des
   **photos** (montage, moniteur série, sortie `mosquitto_sub`) ou des **captures** à intégrer ? Où
   sont-elles ? Si rien n'a été testé physiquement, présente la procédure de test, **jamais** des
   résultats inventés.
5. Faut-il présenter la **version Contiki-NG** de la simulation (comparaison avec TinyOS), ou
   seulement la version TinyOS ?

## 2. Le fil de l'exposé (deux parties demandées par le groupe)

**Partie A — Ce qu'il faudrait faire en industrie** (la solution cible, dimensionnée pour l'usine)
**Partie B — Ce que nous avons réalisé** (simulation Cooja + prototype ESP32), avec les résultats
mesurés et les écarts assumés par rapport à la cible.

Plan proposé (à adapter à la durée) :

1. Titre (projet, groupe, membres, cours, enseignante, date)
2. Contexte et problème : pourquoi surveiller une ligne de production
3. Besoins et exigences du cahier des charges : B1–B4, EF1/EF2/EF5/EF6, et les **3 exigences non
   fonctionnelles retenues : ENF1 (latence < 10 s), ENF6 (messages authentifiés), ENF8 (un nœud
   défaillant n'arrête pas le reste)**
4. **Partie A** — Architecture cible : capteurs → réseau → passerelle → serveur → alertes / tableau de bord
5. Plan d'implantation dans l'usine (zones Z1–Z8, machines M1–M3, 9 nœuds + passerelle) — image du plan
6. Choix des capteurs et des seuils (DS18B20, thermocouple K + MAX6675 pour le four, barrière IR,
   PIR HC-SR501 ; seuils M1 85 °C, M2 90 °C, M3 220 °C)
7. Réseau et protocoles : Wi-Fi 2,4 GHz + MQTT (topics `factory/...`, format JSON du cahier) ;
   pourquoi un réseau multi-saut basse consommation (802.15.4) pour les nœuds sur batterie
8. Plateforme de supervision : Mosquitto, Node-RED, InfluxDB, Grafana, alertes e-mail/SMS, onduleur
9. Sécurité et fiabilité en production (TLS, comptes et ACL par nœud, Last Will, stockage local)
10. **Partie B** — Démarche : simulation d'abord (Cooja), puis prototype matériel
11. Simulation : 10 nœuds aux positions du plan, 4 rôles, routage multi-saut (CTP sous TinyOS ;
    RPL sous Contiki-NG si l'utilisateur le veut) — figure de l'arbre de routage
12. Tests automatiques et résultats chiffrés (tableau exigence → test → valeur → verdict)
13. Focus sur les résultats marquants : alerte de surchauffe en < 1 s, latence moyenne ~30 ms,
    reconvergence après la panne d'un relais, rejet du nœud intrus
14. Prototype : 3 ESP32 (DHT11, IR, PIR) en Wi-Fi → Mosquitto sur un VPS — schéma + câblage
15. Prototype : comment chaque exigence est couverte (Last Will pour ENF8, comptes/ACL pour ENF6,
    publication immédiate des alertes pour ENF1, compteur sauvegardé en flash pour EF5)
16. Écarts entre la cible et le prototype, et limites (DHT11 limité à 50 °C → seuil de démo à 30 °C,
    étoile Wi-Fi au lieu de multi-saut, MQTT sans TLS en démo, modèle radio idéal en simulation)
17. Ce que nous retenons (difficultés rencontrées et ce qu'elles nous ont appris)
18. Conclusion et perspectives
19. Questions

## 3. Où trouver la matière (lis ces fichiers avant d'écrire une seule diapo)

| Sujet | Fichier |
|---|---|
| Plan d'implantation, nomenclature, justification des emplacements, architecture cible (ESP32, AP Wi-Fi, Raspberry Pi, Mosquitto, Node-RED, InfluxDB, Grafana, onduleur, routeur 4G, écrans) | `architecture/plan_implantation.html`, `architecture/generer_plan.py` (listes `ZONES`, `MACHINES`, `EQUIPEMENTS`) |
| Image du plan | `architecture/plan_implantation.png` |
| Simulation TinyOS : architecture, code, tests, **résultats chiffrés**, tableau des exigences, limites | `simulation/02_simulation_projet/rapport/rapport_simulation.html` (source de vérité des chiffres) et `simulation/02_simulation_projet/README.md` |
| Figures prêtes de la simulation | `simulation/02_simulation_projet/rapport/figures/topologie.png` (arbre de routage avant/après panne), `latence.png`, `t2_temperatures.png` |
| Journaux bruts des tests (pour vérifier un chiffre) | `simulation/02_simulation_projet/resultats/*.log` (lignes `MESURE` et `VERDICT`) |
| Version Contiki-NG et comparaison TinyOS ↔ Contiki | `simulation/03_contiki_ng/README.md` (§ 1 et § 6) |
| Prototype matériel : schéma, câblage, rôle du VPS, différences avec la simulation, procédure de test | `materiel/README.md`, `materiel/esp32_*/esp32_*.ino` (en-têtes), `materiel/vps/usine.conf` |
| Vocabulaire et notions du cours | `Reseaux de capteurs sans fil et IOT SEIOT 3.pdf` (support de cours, 111 pages) |

**Règle absolue sur les chiffres** : chaque valeur affichée doit venir de ces fichiers. Relève-la
dans `rapport_simulation.html` ou dans les journaux, et ne l'arrondis que de façon honnête.
Si une information manque (photo, résultat du prototype), demande-la ou présente-la comme
« à venir ». Rappels utiles, **à revérifier dans les fichiers** avant usage :
- simulation TinyOS : période 30,00 s ; alerte de surchauffe ≈ 0,87 s après la mise à 95 °C ;
  100 pièces → compteur 100 ; alerte d'intrusion de nuit ≈ 0,05 s ; latence moyenne ≈ 30 ms
  (max < 50 ms) ; taux de livraison 100 % (aussi avec liens dégradés) ; relais T1 retiré → les
  8 autres nœuds continuent, rapports de P1 rétablis en ≈ 44 s ; intrus : 10 rapports rejetés ;
- Contiki-NG : mêmes tests au vert ; rétablissement après panne ≈ 15 s ; latence moyenne ≈ 50 ms.

## 4. Style : professionnel et sobre

- Format **16:9**, fond blanc ou très clair, **une seule couleur d'accent** (le vert-bleu
  `#0E746D` du plan d'implantation) et une couleur sombre pour le texte (`#17293B`). Les couleurs
  par famille de nœud du plan (thermique `#C63F29`, comptage `#1F66AE`, intrusion `#7B3FAF`) ne
  servent **que** dans les schémas, pour identifier les nœuds.
- **Interdits** : dégradés voyants, ombres portées, effets 3D, cliparts, émojis, formes décoratives
  sans rôle, soulignements, texte en couleur fantaisie, polices variées, animations et transitions
  tape-à-l'œil, WordArt.
- Polices disponibles sur tout PC Windows : **Calibri** ou **Segoe UI** (titres en gras, corps
  normal). Titres 28–32 pt, texte ≥ 18 pt, légendes ≥ 12 pt.
- Une idée par diapo. Le **titre est une phrase qui dit le message** (« L'alerte de surchauffe
  arrive en moins d'une seconde »), pas un simple mot (« Résultats »).
- Au plus 5 puces courtes par diapo ; privilégier schémas, tableaux et chiffres clés.
- Mise en page cohérente : mêmes marges, même position du titre, numéro de diapo et rappel discret
  « Groupe 7 · Surveillance d'une ligne de production » en pied de page. Un bandeau ou une étiquette
  sobre indique la partie en cours (« A · Solution industrielle », « B · Réalisation »).
- Schémas d'architecture **dessinés avec des formes PowerPoint** (rectangles, flèches, texte),
  modifiables, plutôt qu'en images. Les figures existantes (plan, arbre de routage, courbes)
  sont insérées en image, nettes et non déformées.
- **Notes de l'orateur** en français sous chaque diapo : ce qu'il faut dire en 3 à 6 phrases,
  avec les chiffres à citer.

## 5. Comment le produire

- Livrable : un vrai fichier **`.pptx`** dans `presentation/Expose_Groupe7.pptx` (créer le dossier
  si besoin). Utilise la compétence/skill PowerPoint disponible (`pptx`), ou `python-pptx` en
  dernier recours. N'utilise pas Gamma, Adobe Express ou un autre service en ligne, sauf si
  l'utilisateur le demande.
- Mets le script de génération à côté (`presentation/generer_presentation.py`), pour pouvoir
  régénérer le fichier après une correction.
- **Vérifie visuellement le résultat** avant de l'annoncer : exporte chaque diapo en image (par
  exemple avec PowerPoint via PowerShell/COM, ou LibreOffice s'il est installé) et regarde-les une
  par une. Cherche les textes qui débordent, les chevauchements, les images déformées, les
  diapos trop chargées et les fautes. Corrige, puis vérifie de nouveau.
- Exporte aussi une version **PDF** (`presentation/Expose_Groupe7.pdf`) pour l'impression ou en
  cas de souci de projection.
- Ne modifie aucun fichier existant du projet et ne fais **aucun commit** sans que l'utilisateur
  le demande.

## 6. À la fin

Résume en quelques lignes : le nombre de diapos et le plan final, d'où vient chaque chiffre, ce
qui manque encore (par exemple photos du prototype, noms à compléter), et comment régénérer le
fichier.
