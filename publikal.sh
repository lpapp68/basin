#!/bin/bash
# publikal.sh — kézi publikálás úgy, hogy a bot friss adatát NE írjuk felül.
#
# A data.json és a data.js generált fájl: a bot óránként újraírja és kiteszi.
# Ha kézi deploykor a saját, régi példányunkat másoljuk fel, VISSZAÁLLÍTJUK a
# lapot egy korábbi állapotba — pontosan ez történt 2026-08-11-én, kilenc órát
# visszaléptetve az adatot.
#
# Ezért a kézi publikálás mindig az ÉLŐ adatot tölti le, és csak a statikus
# fájlokat cseréli. Ha a saját friss adatunkat akarjuk kitenni, előbb
# ./frissit.sh, ami maga is publikál.

set -euo pipefail
cd "$(dirname "$0")"

ELO="https://basin.equora.institute"
mkdir -p _publish
cp index.html logo.png logo.svg terkep.json robots.txt sitemap.xml googled3302b927f898901.html favicon.ico favicon-32.png apple-touch-icon.png _publish/

# Az élő adat marad érvényben; helyi másolattal csak akkor pótoljuk, ha a
# letöltés nem sikerül.
for f in data.json data.js; do
  if curl -fsSL -m 30 "$ELO/$f" -o "_publish/$f"; then
    echo "  $f: az élő példány marad"
  else
    echo "  !! $f nem tölthető le, a helyi másolat megy ki"
    cp "$f" "_publish/$f"
  fi
done

npx --yes wrangler pages deploy _publish \
    --project-name "${BASIN_PAGES_PROJECT:-basin}" --commit-dirty=true
