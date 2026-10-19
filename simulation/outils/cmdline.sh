#!/bin/bash
for p in $(pgrep -f 'org.contikios.cooja.Main|picocli'); do
  echo "PID $p  CWD=$(readlink /proc/$p/cwd)  START=$(ps -o lstart= -p $p)"
  tr '\0' '\n' < /proc/$p/cmdline
  echo "-----"
done
