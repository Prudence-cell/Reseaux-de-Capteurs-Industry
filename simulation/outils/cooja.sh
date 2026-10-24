#!/bin/bash
# Lance Cooja. Usage : bash cooja.sh [options Cooja] [fichier.csc]
# - Si les bibliothèques de Cooja sont trouvées : lancement direct avec Java
#   (permet d'ouvrir plusieurs Cooja à la fois).
# - Sinon (autre machine Linux) : lancement classique avec Gradle.
COOJA="${COOJA_DIR:-$HOME/contiki-ng/tools/cooja}"
M2="$HOME/.gradle/caches/modules-2/files-2.1"
JAVA=/opt/jdk-25/bin/java; [ -x "$JAVA" ] || JAVA=java
cd "$COOJA" || { echo "Cooja introuvable dans $COOJA (définir COOJA_DIR)"; exit 1; }

CP="$COOJA/build/classes/java/main:$COOJA/build/resources/main:$COOJA/lib/jipv6.jar"
manque=0
for j in logback-classic-1.5.37 json-simple-4.0.1 flatlaf-3.7.1 syntaxpane-1.3.0 picocli-4.7.7 \
         jdom2-2.0.6.1 jfreechart-1.5.6 nashorn-core-15.7 slf4j-api-2.0.18 swingx-autocomplete-1.6.5-1 \
         logback-core-1.5.37 asm-commons-7.3.1 asm-util-7.3.1 asm-analysis-7.3.1 asm-tree-7.3.1 \
         asm-7.3.1 swingx-common-1.6.5-1; do
  f=$(find "$M2" -name "$j.jar" -print -quit 2>/dev/null)
  if [ -n "$f" ]; then CP="$CP:$f"; else manque=1; fi
done

if [ $manque = 1 ] || [ ! -d "$COOJA/build/classes/java/main" ]; then
  exec ./gradlew -q run --args="$*"
fi
exec "$JAVA" -Dpicocli.disable.closures=true --enable-native-access ALL-UNNAMED \
  -Xms400M -Xmx2048M -Dfile.encoding=UTF-8 -cp "$CP" org.contikios.cooja.Main --cooja "$COOJA" "$@"
