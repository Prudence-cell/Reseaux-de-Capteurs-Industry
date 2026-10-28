#!/bin/bash
# Lance les tests automatiques SANS fenêtre (Cooja --no-gui + ScriptRunner)
# et range les journaux dans resultats/.
#
# Usage (dans WSL) :  bash tester.sh              → tous les tests
#                     bash tester.sh T2_surchauffe T5_intrusion
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="$HOME/projets/03_contiki_ng"
OUTILS="$(cd "$SRC/../outils" && pwd)"
if [ -n "$*" ]; then TESTS="$*"; else
  TESTS=$(ls "$DST"/test_*.csc | xargs -n1 basename | sed 's/^test_//; s/\.csc$//' | grep -v '^I[0-9]')
fi
mkdir -p "$SRC/resultats"
for t in $TESTS; do
  dossier="$DST/resultats/$t"
  rm -rf "$dossier"; mkdir -p "$dossier"
  debut=$(date +%s)
  echo "=== Test $t"
  bash "$OUTILS/cooja.sh" --no-gui --logdir="$dossier" "$DST/test_$t.csc" > "$dossier/console.log" 2>&1
  duree=$(( $(date +%s) - debut ))
  if [ -f "$dossier/COOJA.testlog" ]; then
    cp "$dossier/COOJA.testlog" "$SRC/resultats/$t.log"
    grep -E "^(MESURE|VERDICT|FIN)" "$dossier/COOJA.testlog"
    if ! grep -q "^FIN" "$dossier/COOJA.testlog"; then
      echo "!!! Le test s'est arrêté sans verdict. Erreur Cooja :"
      grep -E "ERROR|Exception" "$dossier/console.log" | head -5
    fi
  else
    echo "Pas de journal de test : fin de la console Cooja :"; tail -25 "$dossier/console.log"
  fi
  echo "    (durée réelle : ${duree} s)"
done
