#!/bin/bash
# Compile l'application TinyOS pour la carte telosb (= "Sky" dans Cooja)
# et prépare les fichiers de simulation.
# Usage (dans WSL) : bash construire.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"           # dossier Windows (/mnt/d/...)
DST="$HOME/projets/01_demo_tinyos_cooja"       # copie de travail Linux (pas d'espace ni d'accent)

mkdir -p "$DST"
cp "$SRC"/*.nc "$SRC"/*.h "$SRC"/Makefile "$SRC"/test_demo.js "$DST"/
cd "$DST"

echo "=== 1. Compilation nesC -> C -> binaire MSP430 (make telosb)"
make telosb

echo "=== 2. Le binaire produit est build/telosb/main.exe ; on le renomme pour Cooja"
cp build/telosb/main.exe demo_usine.sky
msp430-size demo_usine.sky

echo "=== 3. Scénarios Cooja avec le bon chemin vers le firmware"
sed "s|@DOSSIER@|$DST|g" "$SRC/demo_usine.csc" > demo_usine.csc
# Version de test sans fenêtre : on remplace les fenêtres par le script de test
python3 - "$DST" <<'PY'
import re, sys
d = sys.argv[1]
xml = open(f"{d}/demo_usine.csc", encoding="utf-8").read()
xml = re.sub(r"\s*<plugin>.*</plugin>", "", xml, flags=re.S)
xml = xml.replace("</simconf>", f"""  <plugin>
    org.contikios.cooja.plugins.ScriptRunner
    <plugin_config>
      <scriptfile>{d}/test_demo.js</scriptfile>
      <active>true</active>
    </plugin_config>
  </plugin>
</simconf>""")
open(f"{d}/test_demo.csc", "w", encoding="utf-8").write(xml)
PY

cp demo_usine.sky "$SRC"/
echo "OK : $DST/demo_usine.sky et $DST/demo_usine.csc"
