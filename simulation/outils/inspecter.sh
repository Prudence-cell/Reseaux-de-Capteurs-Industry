#!/bin/bash
echo "== env"; env | grep -E 'TOS|MAKERULES|CLASSPATH|PYTHONPATH'
echo "== bashrc"; grep -nE 'TOS|MAKERULES|CLASSPATH|tinyos' ~/.bashrc ~/.profile 2>/dev/null
echo "== nescc"; nescc --version 2>&1 | head -2
echo "== test.csc"; head -70 ~/tinyos-cooja/test.csc
echo "== testlog"; tail -15 ~/tinyos-cooja/COOJA.testlog
echo "== apps"; ls ~/tinyos-main/apps | tr '\n' ' '; echo
echo "== build"; ls ~/tinyos-main/apps/RadioCountToLeds ~/tinyos-main/apps/Blink 2>&1
