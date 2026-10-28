#!/bin/bash
# Version Contiki-NG : copie les sources dans ~/projets (pas d'espace ni d'accent dans le chemin),
# génère plan.h et les scénarios .csc depuis le plan, puis compile chaque programme pour
# Cooja mote (make TARGET=cooja) afin de vérifier qu'il n'y a pas d'erreur.
# (Cooja recompile lui-même les programmes en chargeant un .csc.)
# Usage (dans WSL) :  bash construire.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="$HOME/projets/03_contiki_ng"
PROGRAMMES="passerelle thermique comptage intrusion intrus"

echo "=== 1. Plan d'implantation -> commun/plan.h + scénarios .csc"
mkdir -p "$DST"
rm -f "$DST"/test_*.csc "$DST"/test_*.js "$DST"/usine.csc
python3 "$SRC/scenarios/generer_scenarios.py" "$DST" "$DST"

echo "=== 2. Copie des sources vers $DST"
for d in commun $PROGRAMMES; do
  mkdir -p "$DST/$d"
  cp "$SRC/$d"/*.[ch] "$DST/$d"/ 2>/dev/null || true
  # Cooja lance « make » sans la variable HOME : on écrit le chemin de Contiki en clair
  [ -f "$SRC/$d/Makefile" ] && sed "s|\$(HOME)/contiki-ng|$HOME/contiki-ng|" "$SRC/$d/Makefile" > "$DST/$d/Makefile"
done

echo "=== 3. Compilation Contiki-NG (TARGET=cooja)"
for p in $PROGRAMMES; do
  cd "$DST/$p"
  if ! make TARGET=cooja "$p.cooja" > "$DST/make_$p.log" 2>&1; then
    grep -E "error|Error" -A3 "$DST/make_$p.log" | head -40
    echo "ECHEC de compilation : voir $DST/make_$p.log"; exit 1
  fi
  echo "--- $p : OK ($(grep -c warning "$DST/make_$p.log") avertissement(s))"
done

rm -rf "$SRC/scenarios/csc" && mkdir -p "$SRC/scenarios/csc"
cp "$DST"/*.csc "$DST"/test_*.js "$DST"/scenario_demo.js "$SRC/scenarios/csc"/
echo "OK : programmes compilés et scénarios dans $DST"
