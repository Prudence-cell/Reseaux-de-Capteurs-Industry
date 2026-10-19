#!/bin/bash
echo "== Makefile RCTL"; cat ~/tinyos-main/apps/RadioCountToLeds/Makefile
echo "== PlatformSerialC telosb"; f=$(ls ~/tinyos-main/tos/platforms/telos*/PlatformSerialC.nc | head -1); echo $f; cat $f
echo "== TelosSerialP"; cat $(ls ~/tinyos-main/tos/platforms/telos*/TelosSerialP.nc | head -1)
echo "== test.csc (fin)"; sed -n 70,200p ~/tinyos-cooja/test.csc
echo "== dbg.js"; head -40 ~/tinyos-cooja/dbg.js
echo "== history"; grep -E 'cooja|gradlew|telosb|\.sky|nogui|no-gui' ~/.bash_history | tail -25
echo "== display"; echo "DISPLAY=$DISPLAY WAYLAND=$WAYLAND_DISPLAY"; ls /mnt/wslg 2>/dev/null | head -3
