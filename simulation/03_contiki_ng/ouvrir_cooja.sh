#!/bin/bash
# Ouvre Cooja AVEC fenêtres sur la simulation complète (10 nœuds aux positions du plan).
# Ensuite : cliquer sur « Start » ; le scénario de démonstration se déroule tout seul.
DST="$HOME/projets/03_contiki_ng"
OUTILS="$(cd "$(dirname "$0")/../outils" && pwd)"
echo "Ouverture de Cooja (patiente ~15 s)..."
bash "$OUTILS/cooja.sh" "$DST/usine.csc"
