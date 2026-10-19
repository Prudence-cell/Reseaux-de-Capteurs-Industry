#!/bin/bash
cd ~/contiki-ng/tools/cooja
ls build/libs
echo "== plugins"
unzip -l build/libs/cooja*.jar 2>/dev/null | grep -oE 'org/contikios/cooja/plugins/(skins/)?[A-Za-z]+\.class' | sort -u | tr '\n' ' '
echo; echo "== options"
grep -nE '"--[a-z-]+' java/org/contikios/cooja/Main.java 2>/dev/null | head -30
ls java/org/contikios/cooja/Main.java src/main/java 2>/dev/null | head
grep -rn "no-gui\|nogui" --include=*.java . 2>/dev/null | head -5
grep -rn "ActiveMessageAddressC\|TOS_NODE_ID" --include=*.java . 2>/dev/null | head -5
