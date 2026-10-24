#!/bin/bash
# Ouvre Cooja AVEC fenêtres et charge directement le scénario de démo.
# Ensuite : cliquer sur "Start" en haut, et regarder les fenêtres.
DST="$HOME/projets/01_demo_tinyos_cooja"
OUTILS="$(cd "$(dirname "$0")/../outils" && pwd)"
echo "Ouverture de Cooja (patiente ~15 s)..."
bash "$OUTILS/cooja.sh" "$DST/demo_usine.csc"
