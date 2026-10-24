#!/bin/bash
# Diagnostic d'un test : bash etat_test.sh <test> [t_debut_ms] [t_fin_ms]
D="$HOME/projets/02_simulation_projet/resultats/$1"
L="$D/COOJA.testlog"
A=${2:-0}; B=${3:-999999999}
echo "--- types de lignes entre $A et $B ms"
awk -v a=$A -v b=$B '$1=="L" && $2>a && $2<b {print $3, $4}' "$L" | sort | uniq -c | sort -rn | head -25
echo "--- premières lignes de la fenêtre (hors PUB)"
awk -v a=$A -v b=$B '$1=="L" && $2>a && $2<b && $4!="PUB"' "$L" | head -40
grep -E "^CMD" "$L" | head
