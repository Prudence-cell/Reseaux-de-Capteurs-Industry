#!/bin/bash
# Lance la simulation SANS fenêtre et affiche le journal du test.
DST="$HOME/projets/01_demo_tinyos_cooja"
OUTILS="$(cd "$(dirname "$0")/../outils" && pwd)"
rm -f "$DST/COOJA.testlog"
bash "$OUTILS/cooja.sh" --no-gui --logdir="$DST" "$DST/test_demo.csc" > "$DST/cooja_console.log" 2>&1
echo "=== Journal (COOJA.testlog)"
cat "$DST/COOJA.testlog" 2>/dev/null || tail -30 "$DST/cooja_console.log"
