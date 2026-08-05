#!/bin/bash
# frissit.sh — a teljes frissítési ciklus egyetlen belépési ponttal.
#
#   ./frissit.sh oras    -> csak a mércék (óránként)
#   ./frissit.sh napi    -> légköri tagok + mércék (naponta egyszer)
#   ./frissit.sh         -> automatikus: napi, ha ma még nem futott; egyébként óras
#
# A dátumot EGY helyen számoljuk ki, és mindkét légköri scriptnek átadjuk —
# így nem csúszhatnak szét éjfél körül.

set -euo pipefail
cd "$(dirname "$0")"

VENV="${VENV:-$HOME/cds-env}"
if [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
fi

MOD="${1:-auto}"
JELZO="archiv/.utolso-napi"
NAP=$(date -u -v-1d +%Y-%m-%d 2>/dev/null || date -u -d "yesterday" +%Y-%m-%d)

mkdir -p archiv

if [ "$MOD" = "auto" ]; then
  if [ "$(cat "$JELZO" 2>/dev/null)" = "$NAP" ]; then MOD=oras; else MOD=napi; fi
fi

if [ "$MOD" = "napi" ]; then
  echo "== napi frissítés: $NAP"
  # Ha valamelyik forrás elérhetetlen, a mércék akkor is frissüljenek.
  python imerg_precip.py "$NAP" || echo "!! IMERG kimaradt"
  python lsasaf_et.py    "$NAP" || echo "!! LSA SAF kimaradt"
  echo "$NAP" > "$JELZO"
fi

echo "== mércék"
python fetch_data.py

# Publikálás. Csak akkor, ha be van állítva a Cloudflare Pages projekt.
if [ -n "${BASIN_PAGES_PROJECT:-}" ]; then
  echo "== publikálás"
  mkdir -p _publish
  cp index.html data.js data.json _publish/
  npx --yes wrangler pages deploy _publish \
      --project-name "$BASIN_PAGES_PROJECT" --commit-dirty=true
fi
