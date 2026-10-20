#!/bin/bash
T=$HOME/tinyos-main
C=~/contiki-ng/tools/cooja
OUT="$(dirname "$0")/explorer.log"
{
cat $T/tos/lib/net/Deluge/extra/msp430/InternalFlashC.nc | sed -n '30,200p'
echo "--- parser"
grep -n "replace\|write\|function" $C/java/org/contikios/cooja/script/ScriptParser.java | head -40
sed -n 40,80p $C/java/org/contikios/cooja/script/ScriptMote.java
sed -n 810,830p $C/java/org/contikios/cooja/Cooja.java
} > "$OUT" 2>&1
