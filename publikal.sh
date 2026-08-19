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

# ── Frissesség-ellenőrzés ────────────────────────────────────────────────
# A publikal.sh a MEGLÉVŐ data.json-t viszi ki. Ha az régi — mert csak a
# lapot szerkesztettük, és nem futott adatgenerálás —, akkor felülírja a bot
# friss adatát az élő lapon. Ez 2026-08-19-én háromszor megtörtént: a bot
# 07:48-kor kitette a friss mérleget, három kézi publikálás visszaírta a
# tegnapit, és a lap 17 órásnak látszott.
if [ -f data.json ]; then
  KOR=$(( $(date +%s) - $(stat -f %m data.json 2>/dev/null || stat -c %Y data.json) ))
  if [ "$KOR" -gt 10800 ]; then          # három óra
    ORA=$(( KOR / 3600 ))
    echo ""
    echo "!! A data.json ${ORA} órája nem frissült."
    echo "   Ha most publikálsz, a bot frissebb adatát írod felül az élő lapon."
    echo "   Adatfrissítéshez:  ./frissit.sh"
    echo ""
    printf "   Mégis folytatod? [i/N] "
    read -r VALASZ
    case "$VALASZ" in
      i|I|igen|y|Y) echo "   Rendben, folytatom." ;;
      *) echo "   Kilépés."; exit 1 ;;
    esac
  fi
fi

cd "$(dirname "$0")"

ELO="https://basin.equora.institute"
# Az angol valtozat a magyar forrasbol generalodik, kozvetlenul publikalas elott,
          # igy a ket nyelv nem tud szetcsuszni.
mkdir -p _publish
cp index.html logo.png logo.svg terkep.json robots.txt sitemap.xml llms.txt googled3302b927f898901.html favicon.ico favicon-32.png apple-touch-icon.png _publish/

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
