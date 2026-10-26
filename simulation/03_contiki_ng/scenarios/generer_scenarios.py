# -*- coding: utf-8 -*-
"""
Version Contiki-NG du générateur de scénarios. À partir du PLAN D'IMPLANTATION
(architecture/noeuds_cooja.csv et architecture/generer_plan.py), il écrit :

  1. commun/plan.h      : repères, familles, numéros de machine/poste/zone et seuils ;
  2. <sortie>/usine.csc : la simulation AVEC fenêtres (Cooja motes aux positions du plan) ;
  3. <sortie>/test_*.csc et test_*.js : une simulation SANS fenêtre par test.

Les scripts de test sont ceux de la version TinyOS (../02_simulation_projet/scenarios/tests),
car les programmes Contiki écrivent exactement les mêmes lignes (PUB, RX, PARENT, ALERTE...).
Un script placé dans scenarios/tests/ de ce dossier remplace celui de TinyOS.

Usage :  python3 generer_scenarios.py <dossier_sources_linux> <dossier_sortie>
"""
import csv
import pathlib
import re
import sys
import unicodedata
from xml.sax.saxutils import escape

ICI = pathlib.Path(__file__).resolve().parent
PROJET = ICI.parent
SIMULATION = PROJET.parent
ARCHI = SIMULATION.parent / "architecture"
TESTS_TINYOS = SIMULATION / "02_simulation_projet" / "scenarios"

NOEUDS = []
with open(ARCHI / "noeuds_cooja.csv", encoding="utf-8") as fh:
    for ligne in csv.DictReader(fh, delimiter=";"):
        NOEUDS.append(dict(id=int(ligne["id_cooja"]), repere=ligne["repere"], fam=ligne["famille"],
                           x=float(ligne["x_m"]), y=float(ligne["y_m"])))
NOEUDS.sort(key=lambda n: n["id"])
texte_plan = (ARCHI / "generer_plan.py").read_text(encoding="utf-8")
MACHINES = re.findall(r'\("(M\d)",\s*"([^"]+)",\s*[\d.]+,\s*[\d.]+,\s*"(\d+) °C"', texte_plan)
PORTEE = float(re.search(r"PORTEE_COOJA\s*=\s*([\d.]+)", texte_plan).group(1))

FAMILLES = {"infra": 0, "temp": 1, "count": 2, "pir": 3}
PROGRAMME = {"infra": "passerelle", "temp": "thermique", "count": "comptage", "pir": "intrusion"}


def sans_accent(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def ecrire_plan_h():
    max_id = max(n["id"] for n in NOEUDS)
    par_id = {n["id"]: n for n in NOEUDS}
    val = lambda f, defaut: ", ".join(f(par_id[i]) if i in par_id else defaut for i in range(max_id + 1))
    # calculés à part : Python 3.8 (WSL) refuse les « \ » dans les expressions d'une f-string
    familles = val(lambda n: str(FAMILLES[n["fam"]]), "0")
    indices = val(lambda n: re.sub(r"\D", "", n["repere"]) or "0", "0")
    reperes = val(lambda n: '"' + n["repere"] + '"', '"?"')
    seuils = ", ".join(str(int(s) * 10) for _, _, s in MACHINES)
    noms = ", ".join('"' + sans_accent(n) + '"' for _, n, _ in MACHINES)
    h = f"""/* FICHIER GÉNÉRÉ par scenarios/generer_scenarios.py — ne pas modifier à la main.
   Source : architecture/generer_plan.py et architecture/noeuds_cooja.csv */
#ifndef PLAN_H
#define PLAN_H
#include <stdint.h>

#define MAX_ID {max_id}            /* plus grand numéro de nœud Cooja du plan */
enum {{ FAM_INFRA = 0, FAM_TEMP = 1, FAM_COUNT = 2, FAM_PIR = 3 }};

/* Indexés par le numéro de nœud Cooja (node_id) */
static const uint8_t FAMILLE[MAX_ID + 1] = {{ {familles} }};
static const uint8_t INDICE[MAX_ID + 1]  = {{ {indices} }};
static const char *const REPERE[MAX_ID + 1] = {{ {reperes} }};

/* Indexés par le numéro de machine (1 = M1 ...) : seuil d'alerte en dixièmes de °C (EF2) */
static const int16_t SEUIL_DIXIEMES[4] = {{ 0, {seuils} }};
static const char *const NOM_MACHINE[4] = {{ "?", {noms} }};

#endif
"""
    (PROJET / "commun" / "plan.h").write_bytes(h.encode("utf-8"))


INTERFACES = "\n".join(f"      <moteinterface>{i}</moteinterface>" for i in [
    "org.contikios.cooja.interfaces.Position",
    "org.contikios.cooja.interfaces.Battery",
    "org.contikios.cooja.contikimote.interfaces.ContikiVib",
    "org.contikios.cooja.contikimote.interfaces.ContikiMoteID",
    "org.contikios.cooja.contikimote.interfaces.ContikiRS232",
    "org.contikios.cooja.contikimote.interfaces.ContikiBeeper",
    "org.contikios.cooja.interfaces.RimeAddress",
    "org.contikios.cooja.contikimote.interfaces.ContikiIPAddress",
    "org.contikios.cooja.contikimote.interfaces.ContikiRadio",
    "org.contikios.cooja.contikimote.interfaces.ContikiButton",
    "org.contikios.cooja.contikimote.interfaces.ContikiPIR",
    "org.contikios.cooja.contikimote.interfaces.ContikiClock",
    "org.contikios.cooja.contikimote.interfaces.ContikiLED",
    "org.contikios.cooja.contikimote.interfaces.ContikiCFS",
    "org.contikios.cooja.contikimote.interfaces.ContikiEEPROM",
    "org.contikios.cooja.interfaces.Mote2MoteRelations",
    "org.contikios.cooja.interfaces.MoteAttributes",
])

DESCRIPTION = {
    "passerelle": "Passerelle GW (racine RPL)", "thermique": "Noeud thermique T1-T3",
    "comptage": "Noeud de comptage C1-C3", "intrusion": "Noeud intrusion P1-P3",
    "intrus": "Noeud INTRUS (mauvaise cle, test ENF6)",
}


def mote_xml(i, x, y):
    return f"""    <mote>
      <interface_config>
        org.contikios.cooja.interfaces.Position
        <x>{x}</x>
        <y>{y}</y>
        <z>0.0</z>
      </interface_config>
      <interface_config>
        org.contikios.cooja.contikimote.interfaces.ContikiMoteID
        <id>{i}</id>
      </interface_config>
      <interface_config>
        org.contikios.cooja.contikimote.interfaces.ContikiRadio
        <bitrate>250.0</bitrate>
      </interface_config>
      <motetype_identifier>{{type}}</motetype_identifier>
    </mote>"""


def simulation_xml(titre, sources, rx=1.0, intrus=False, noeuds=None):
    groupes = {}
    for n in NOEUDS:
        if noeuds and n["id"] not in noeuds:
            continue
        groupes.setdefault(PROGRAMME[n["fam"]], []).append((n["id"], n["x"], n["y"]))
    if intrus:
        groupes["intrus"] = [(11, 26.0, 14.0)]
    types, motes = [], []
    for prog, liste in groupes.items():
        ident = f"mt_{prog}"
        types.append(f"""    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <identifier>{ident}</identifier>
      <description>{DESCRIPTION[prog]}</description>
      <source>{sources}/{prog}/{prog}.c</source>
      <commands>$(MAKE) -j$(CPUS) {prog}.cooja TARGET=cooja</commands>
{INTERFACES}
    </motetype>""")
        motes += [mote_xml(i, x, y).replace("{type}", ident) for i, x, y in liste]
    return f"""  <simulation>
    <title>{escape(titre)}</title>
    <randomseed>123456</randomseed>
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
{chr(10).join(motes)}
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
      <analyzers name="6lowpan" />
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

TESTS = [
    ("I1_direct",     "Increment 1 - passerelle + T2 en liaison directe", {"noeuds": [1, 3]}),
    ("I2_multisaut",  "Increment 2 - P1 hors de portee, relaye par T1", {"noeuds": [1, 2, 8]}),
    ("T1_periode",    "T1 - une mesure toutes les 30 s", {}),
    ("T2_surchauffe", "T2 - 95 C sur M2 -> alerte < 10 s", {}),
    ("T4_comptage",   "T4 - 100 pieces -> compteur = 100 (+ redemarrage)", {}),
    ("T5_intrusion",  "T5 - presence hors heures -> alerte < 5 s", {}),
    ("T6_reseau",     "T6 - latence, PDR, sauts (10 noeuds)", {}),
    ("T6b_pertes",    "T6b - PDR avec liens radio degrades", {"rx": 0.8}),
    ("T9_panne",      "T9 - relais T1 retire, reconvergence", {}),
    ("ENF6_auth",     "ENF6 - message d'un noeud intrus rejete", {"intrus": True}),
]


def lire_test(nom):
    """Le script de ce dossier s'il existe, sinon celui de la version TinyOS."""
    for base in (ICI, TESTS_TINYOS):
        f = base / nom if nom == "scenario_demo.js" else base / "tests" / nom
        if f.exists():
            return f.read_text(encoding="utf-8")
    raise FileNotFoundError(nom)


def main():
    sources = sys.argv[1]
    sortie = pathlib.Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    ecrire_plan_h()
    commun_js = lire_test("commun.js")

    demo = sortie / "scenario_demo.js"
    demo.write_bytes((commun_js + "\n" + lire_test("scenario_demo.js")).encode("utf-8"))
    csc = ('<?xml version="1.0" encoding="UTF-8"?>\n<simconf>\n'
           + simulation_xml("Surveillance de la ligne de production - Groupe 7 (Contiki-NG)", sources) + "\n"
           + FENETRES + "\n" + script_runner(demo) + "\n</simconf>\n")
    (sortie / "usine.csc").write_bytes(csc.encode("utf-8"))

    for nom, titre, opt in TESTS:
        js = sortie / f"test_{nom}.js"
        js.write_bytes((commun_js + "\n" + lire_test(f"{nom}.js")).encode("utf-8"))
        csc = ('<?xml version="1.0" encoding="UTF-8"?>\n<simconf>\n'
               + simulation_xml(titre + " (Contiki-NG)", sources, rx=opt.get("rx", 1.0),
                                intrus=opt.get("intrus", False), noeuds=opt.get("noeuds")) + "\n"
               + script_runner(js) + "\n</simconf>\n")
        (sortie / f"test_{nom}.csc").write_bytes(csc.encode("utf-8"))
    print(f"OK : plan.h, usine.csc et {len(TESTS)} tests dans {sortie}")


if __name__ == "__main__":
    main()
