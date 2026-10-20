#!/bin/bash
# Diagnostic d'un test : bash etat_test.sh T7_coupure
D="$HOME/projets/02_simulation_projet/resultats/$1"
L="$D/COOJA.testlog"
echo "--- nombre de lignes par type après la coupure (t > 300 s)"
awk '$1=="L" && $2>300000 {print $3, $4}' "$L" | sort | uniq -c | sort -rn | head -20
echo "--- lignes autour de la coupure"
awk '$1=="L" && $2>299000 && $2<330000' "$L" | head -40
echo "--- dernières lignes"
tail -15 "$L"
echo "--- première alerte CC2420 dans console.log"
grep -n -m2 "too large" "$D/console.log"
grep -n "completed" "$D/console.log" | head -20
