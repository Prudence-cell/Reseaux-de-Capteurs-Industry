#!/bin/bash
# Compile les applications TinyOS pour la carte telosb (= « Sky » dans Cooja)
# et génère les scénarios Cooja à partir du plan d'implantation.
#
# Usage (dans WSL) :  bash construire.sh                 → tout (4 rôles + nœud intrus)
#                     bash construire.sh thermique       → seulement ce rôle
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"           # dossier Windows (/mnt/d/...) : espaces et accents
DST="$HOME/projets/02_simulation_projet"       # copie de travail Linux : make y fonctionne
APPS="${*:-passerelle thermique comptage intrusion}"
TOUT=$([ -z "$*" ] && echo 1 || echo 0)

echo "=== 1. Plan d'implantation -> commun/Plan.h + scénarios .csc"
mkdir -p "$DST"
# On repart de zéro pour les fichiers générés (évite de relancer un ancien test ou firmware)
rm -f "$DST"/test_*.csc "$DST"/test_*.js "$DST"/*.sky "$DST"/usine.csc
[ "$TOUT" = 1 ] && rm -rf "$SRC/scenarios/csc" "$SRC/firmwares"
python3 "$SRC/scenarios/generer_scenarios.py" "$DST" "$DST"

echo "=== 2. Copie des sources vers $DST"
for d in commun passerelle thermique comptage intrusion; do
  mkdir -p "$DST/$d"
  cp "$SRC/$d"/*.nc "$SRC/$d"/Makefile* "$DST/$d"/ 2>/dev/null || true
  cp "$SRC/$d"/*.h "$DST/$d"/ 2>/dev/null || true
done

compiler() {   # compiler <dossier> <nom du .sky> [options make]
  local dossier=$1 nom=$2; shift 2
  echo "--- make telosb $* dans $dossier -> $nom.sky"
  cd "$DST/$dossier"
  rm -rf build
  if ! make telosb "$@" > "$DST/make_$nom.log" 2>&1; then
    grep -E "error|Error|ERROR" -A2 "$DST/make_$nom.log" | head -40
    echo "ECHEC de compilation : voir $DST/make_$nom.log"; exit 1
  fi
  cp build/telosb/main.exe "$DST/$nom.sky"
  msp430-size "$DST/$nom.sky" | tail -1 | awk '{printf "    ROM (text+data) = %d octets, RAM (data+bss) = %d octets\n", $1+$2, $2+$3}'
}

echo "=== 3. Compilation nesC -> C -> binaire MSP430"
for a in $APPS; do compiler "$a" "$a"; done
if [ "$TOUT" = 1 ]; then
  echo "=== 4. Variante : nœud intrus (mauvaise clé, test ENF6)"
  mkdir -p "$DST/intrus" && cp "$DST/thermique"/* "$DST/intrus"/ 2>/dev/null || true
  compiler intrus intrus CLE=0x0BADC0DE
fi

mkdir -p "$SRC/firmwares"
cp "$DST"/*.sky "$SRC/firmwares"/
cp "$SRC/commun/Plan.h" "$DST/commun/"
# Copie des scénarios Cooja générés (avec fenêtres + tests) pour pouvoir les lire depuis Windows
mkdir -p "$SRC/scenarios/csc"
cp "$DST"/*.csc "$DST"/test_*.js "$DST"/scenario_demo.js "$SRC/scenarios/csc"/
echo "OK : firmwares dans $DST (copie dans firmwares/) et scénarios $DST/*.csc"
