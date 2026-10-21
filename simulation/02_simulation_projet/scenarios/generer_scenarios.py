# -*- coding: utf-8 -*-
"""
Génère, à partir du PLAN D'IMPLANTATION (source unique architecture/generer_plan.py
et architecture/noeuds_cooja.csv) :

  1. commun/Plan.h          : repères, familles, numéros de machine/poste/zone et seuils,
                              lus par le code nesC (les seuils ne sont écrits qu'une fois) ;
  2. <sortie>/usine.csc      : la simulation AVEC fenêtres (positions du plan en mètres) ;
  3. <sortie>/test_*.csc     : une simulation SANS fenêtre par test automatique ;
  4. <sortie>/test_*.js      : le script de chaque test = commun.js + script du test.

Usage :  python3 generer_scenarios.py <dossier_firmwares> <dossier_sortie>
Si on déplace un nœud dans generer_plan.py, on relance construire.sh et Cooja suit.
"""
import csv
import pathlib
import re
import sys
import unicodedata
from xml.sax.saxutils import escape

ICI = pathlib.Path(__file__).resolve().parent
PROJET = ICI.parent
ARCHI = PROJET.parent.parent / "architecture"

# ----------------------------------------------------------------------------- lecture du plan
NOEUDS = []
with open(ARCHI / "noeuds_cooja.csv", encoding="utf-8") as fh:
    for ligne in csv.DictReader(fh, delimiter=";"):
        NOEUDS.append(dict(id=int(ligne["id_cooja"]), repere=ligne["repere"], fam=ligne["famille"],
                           x=float(ligne["x_m"]), y=float(ligne["y_m"]), zone=ligne["zone"]))
NOEUDS.sort(key=lambda n: n["id"])

# Les seuils sont dans la liste MACHINES de generer_plan.py : ("M1", "Découpe", x0, x1, "85 °C", capteur)
texte_plan = (ARCHI / "generer_plan.py").read_text(encoding="utf-8")
MACHINES = re.findall(r'\("(M\d)",\s*"([^"]+)",\s*[\d.]+,\s*[\d.]+,\s*"(\d+) °C"', texte_plan)
PORTEE = float(re.search(r"PORTEE_COOJA\s*=\s*([\d.]+)", texte_plan).group(1))
assert len(MACHINES) == 3, MACHINES

FAMILLES = {"infra": 0, "temp": 1, "count": 2, "pir": 3}
FIRMWARE = {"infra": "passerelle", "temp": "thermique", "count": "comptage", "pir": "intrusion"}


def sans_accent(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def ecrire_plan_h():
    max_id = max(n["id"] for n in NOEUDS)
    par_id = {n["id"]: n for n in NOEUDS}
    fam = ", ".join(str(FAMILLES[par_id[i]["fam"]]) if i in par_id else "0" for i in range(max_id + 1))
    ind = ", ".join(re.sub(r"\D", "", par_id[i]["repere"]) or "0" if i in par_id else "0"
                    for i in range(max_id + 1))
    rep = ", ".join(f'"{par_id[i]["repere"]}"' if i in par_id else '"?"' for i in range(max_id + 1))
    seuils = ", ".join(str(int(s) * 10) for _, _, s in MACHINES)
    noms = ", ".join('"' + sans_accent(n) + '"' for _, n, _ in MACHINES)
    h = f"""/* FICHIER GÉNÉRÉ par scenarios/generer_scenarios.py — ne pas modifier à la main.
   Source : architecture/generer_plan.py et architecture/noeuds_cooja.csv */
#ifndef PLAN_H
#define PLAN_H

#define MAX_ID {max_id}            /* plus grand numéro de nœud Cooja du plan */
enum {{ FAM_INFRA = 0, FAM_TEMP = 1, FAM_COUNT = 2, FAM_PIR = 3 }};

/* Indexés par le numéro de nœud Cooja (TOS_NODE_ID) */
static const uint8_t FAMILLE[MAX_ID + 1] = {{ {fam} }};
static const uint8_t INDICE[MAX_ID + 1]  = {{ {ind} }};   /* n° de machine / poste / zone */
static const char *const REPERE[MAX_ID + 1] = {{ {rep} }};

/* Indexés par le numéro de machine (1 = M1 ...) : seuil d'alerte en dixièmes de °C (EF2) */
static const int16_t SEUIL_DIXIEMES[4] = {{ 0, {seuils} }};
static const char *const NOM_MACHINE[4] = {{ "?", {noms} }};

#endif
"""
    (PROJET / "commun" / "Plan.h").write_text(h, encoding="utf-8")


# ----------------------------------------------------------------------------- morceaux de .csc
INTERFACES = """      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspClock</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyButton</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyFlash</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.Msp802154Radio</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.MspSerial</moteinterface>
      <moteinterface>org.contikios.cooja.mspmote.interfaces.SkyLED</moteinterface>"""

DESCRIPTION = {
    "passerelle": "Passerelle GW (racine CTP)",
    "thermique": "Noeud thermique T1-T3",
    "comptage": "Noeud de comptage C1-C3",
    "intrusion": "Noeud intrusion P1-P3",
    "intrus": "Noeud INTRUS (mauvaise cle, test ENF6)",
}


def mote_xml(i, x, y):
    return f"""      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="{x}" y="{y}" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.mspmote.interfaces.MspMoteID
          <id>{i}</id>
        </interface_config>
      </mote>"""


def simulation_xml(titre, dossier, suffixe="", rx=1.0, intrus=False, graine=123456, noeuds=None):
    """Partie <simulation> : radio UDGM + 4 (ou 5) types de cartes + les nœuds aux positions du plan."""
    types = []
    groupes = {}
    for n in NOEUDS:
        if noeuds and n["id"] not in noeuds:
            continue
        groupes.setdefault(FIRMWARE[n["fam"]], []).append(mote_xml(n["id"], n["x"], n["y"]))
    if intrus:   # un nœud étranger posé à côté de T2, qui ne connaît pas la clé
        groupes["intrus"] = [mote_xml(11, 26.0, 14.0)]
    for fw, motes in groupes.items():
        types.append(f"""    <motetype>
      org.contikios.cooja.mspmote.SkyMoteType
      <description>{DESCRIPTION[fw]}</description>
      <firmware>{dossier}/{fw}{suffixe}.sky</firmware>
{INTERFACES}
{chr(10).join(motes)}
    </motetype>""")
    return f"""  <simulation>
    <title>{escape(titre)}</title>
    <randomseed>{graine}</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>{PORTEE}</transmitting_range>
      <interference_range>{2 * PORTEE}</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>{rx}</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>400000</logoutput>
    </events>
{chr(10).join(types)}
  </simulation>"""


def script_runner(chemin_js):
    return f"""  <plugin>
    org.contikios.cooja.plugins.ScriptRunner
    <plugin_config>
      <scriptfile>{chemin_js}</scriptfile>
      <active>true</active>
    </plugin_config>
    <bounds x="1040" y="440" height="300" width="560" />
  </plugin>"""


POWERTRACKER = """  <plugin>
    org.contikios.cooja.plugins.PowerTracker
    <bounds x="1040" y="0" height="440" width="560" />
  </plugin>"""

FENETRES = """  <plugin>
    org.contikios.cooja.plugins.Visualizer
    <plugin_config>
      <moterelations>true</moterelations>
      <skin>org.contikios.cooja.plugins.skins.IDVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.GridVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.UDGMVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.TrafficVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.LEDVisualizerSkin</skin>
      <viewport>11.0 0.0 0.0 11.0 40.0 40.0</viewport>
    </plugin_config>
    <bounds x="0" y="0" height="440" width="640" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.LogListener
    <plugin_config>
      <filter />
      <formatted_time />
      <coloring />
    </plugin_config>
    <bounds x="640" y="0" height="440" width="400" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.RadioLogger
    <plugin_config>
      <split>150</split>
      <formatted_time />
    </plugin_config>
    <bounds x="0" y="440" height="300" width="520" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.TimeLine
    <plugin_config>
      <showRadioRXTX />
      <showRadioHW />
      <showLEDs />
      <zoomfactor>500.0</zoomfactor>
    </plugin_config>
    <bounds x="520" y="440" height="300" width="520" />
  </plugin>"""

# ----------------------------------------------------------------------------- tests
# nom, titre, options
TESTS = [
    ("I1_direct",      "Increment 1 - passerelle + T2 en liaison directe", {"noeuds": [1, 3]}),
    ("I2_multisaut",   "Increment 2 - P1 hors de portee, relaye par T1", {"noeuds": [1, 2, 8]}),
    ("T1_periode",     "T1 - une mesure toutes les 30 s", {}),
    ("T2_surchauffe",  "T2 - 95 C sur M2 -> alerte < 10 s", {}),
    ("T4_comptage",    "T4 - 100 pieces -> compteur = 100 (+ redemarrage)", {}),
    ("T5_intrusion",   "T5 - presence hors heures -> alerte < 5 s", {}),
    ("T6_reseau",      "T6 - latence, PDR, sauts (10 noeuds)", {}),
    ("T6b_pertes",     "T6b - PDR avec liens radio degrades", {"rx": 0.8}),
    ("T7_coupure",     "T7 - coupure du puits puis renvoi", {}),
    ("T7c_court",      "T7c - coupure courte (5 min), diagnostic", {}),
    ("T9_panne",       "T9 - relais T1 retire, reconvergence", {}),
    ("ENF6_auth",      "ENF6 - message d'un noeud intrus rejete", {"intrus": True}),
    ("E_energie",      "Energie radio, radio toujours allumee", {"power": True}),
    ("E_energie_lpl",  "Energie radio, ecoute basse consommation (LPL 512 ms)", {"power": True, "lpl": "_lpl"}),
    ("E_energie_lpl1024", "Energie radio, LPL 1024 ms", {"power": True, "lpl": "_lpl1024"}),
    ("E_energie_lpl2048", "Energie radio, LPL 2048 ms", {"power": True, "lpl": "_lpl2048"}),
]


def main():
    dossier = sys.argv[1] if len(sys.argv) > 1 else "@DOSSIER@"
    sortie = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ICI / "genere"
    sortie.mkdir(parents=True, exist_ok=True)
    ecrire_plan_h()

    commun_js = (ICI / "tests" / "commun.js").read_text(encoding="utf-8")

    # Simulation avec fenêtres + scénario de démonstration commenté
    demo_js = sortie / "scenario_demo.js"
    demo_js.write_text(commun_js + "\n" + (ICI / "scenario_demo.js").read_text(encoding="utf-8"), encoding="utf-8")
    csc = ('<?xml version="1.0" encoding="UTF-8"?>\n<simconf version="2022112801">\n'
           + simulation_xml("Surveillance de la ligne de production - Groupe 7", dossier) + "\n"
           + FENETRES + "\n" + POWERTRACKER + "\n" + script_runner(demo_js) + "\n</simconf>\n")
    (sortie / "usine.csc").write_text(csc, encoding="utf-8")

    for nom, titre, opt in TESTS:
        js = sortie / f"test_{nom}.js"
        fichier = ICI / "tests" / f"{nom}.js"
        if not fichier.exists():
            continue
        corps = fichier.read_text(encoding="utf-8")
        corps = re.sub(r"/\*INCLURE (\S+)\*/",              # un test peut en réutiliser un autre
                       lambda m: (ICI / "tests" / m.group(1)).read_text(encoding="utf-8"), corps)
        js.write_bytes((commun_js + "\n" + corps).encode("utf-8"))
        csc = ('<?xml version="1.0" encoding="UTF-8"?>\n<simconf version="2022112801">\n'
               + simulation_xml(titre, dossier, opt.get("lpl", ""),
                                rx=opt.get("rx", 1.0), intrus=opt.get("intrus", False),
                                noeuds=opt.get("noeuds")) + "\n"
               + (POWERTRACKER + "\n" if opt.get("power") else "")
               + script_runner(js) + "\n</simconf>\n")
        (sortie / f"test_{nom}.csc").write_text(csc, encoding="utf-8")
    print(f"OK : Plan.h, usine.csc et {len(TESTS)} tests dans {sortie}")


if __name__ == "__main__":
    main()
