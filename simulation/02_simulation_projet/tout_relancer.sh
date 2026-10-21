#!/bin/bash
# Recompile tout puis lance les tests : bash tout_relancer.sh [test1 test2 ...]
# Sans argument : tous les tests.
ICI="$(cd "$(dirname "$0")" && pwd)"
bash "$ICI/construire.sh" | grep -E "ECHEC|OK :|ROM" || exit 1
bash "$ICI/tester.sh" "$@"
