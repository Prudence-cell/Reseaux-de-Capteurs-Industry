#!/bin/bash
# Recompile tout puis lance les tests : bash tout_relancer.sh [test1 test2 ...]
ICI="$(cd "$(dirname "$0")" && pwd)"
bash "$ICI/construire.sh" | grep -E "ECHEC|OK|error" || exit 1
bash "$ICI/tester.sh" "$@"
