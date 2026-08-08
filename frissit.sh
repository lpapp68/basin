#!/bin/bash
# frissit.sh — a teljes frissítési ciklus egyetlen belépési ponttal.
#
#   ./frissit.sh oras    -> csak a mércék (óránként)
#   ./frissit.sh napi    -> a légköri és talajtagok is (naponta egyszer)
#   ./frissit.sh         -> automatikus: napi, ha ma még nem futott; egyébként óras
#
# A dátumot EGY helyen számoljuk ki, és minden napi scriptnek átadjuk — így nem
# csúszhatnak szét éjfél körül, és a mérleg tagjai egyetlen naphoz tartoznak.

set -uo pipefail
cd "$(dirname "$0")"

VENV="${VENV:-$HOME/cds-env}"
if [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
fi

MOD="${1:-auto}"
JELZO="archiv/.utolso-napi"
GRACE_JELZO="archiv/.utolso-grace"
NAP=$(date -u -v-1d +%Y-%m-%d 2>/dev/null || date -u -d "yesterday" +%Y-%m-%d)
HONAP=$(date -u +%Y-%m)

mkdir -p archiv

if [ "$MOD" = "auto" ]; then
  if [ "$(cat "$JELZO" 2>/dev/null)" = "$NAP" ]; then MOD=oras; else MOD=napi; fi
fi

# Minden napi tag hibáját összegyűjtjük, hogy a futás végén egy helyen látszódjon.
HIBAK=""
futtat() {                      # futtat <cimke> <parancs...>
  local cimke="$1"; shift
  echo "-- $cimke"
  if "$@"; then return 0; fi
  echo "!! $cimke ELHASALT"
  HIBAK="$HIBAK $cimke"
  return 1
}

if [ "$MOD" = "napi" ]; then
  echo "== napi frissítés: $NAP"

  # Csapadék: IMERG az elsődleges, mert néhány órás késésű.
  # Ha elérhetetlen, az ERA5-Land ugyanarra a napra tartalékként beugrik.
  if ! futtat "IMERG csapadék" python imerg_precip.py "$NAP"; then
    echo "-- tartalék: ERA5-Land"
    if python era5_precip.py "$NAP"; then
      echo "   ERA5-Land pótolta a csapadékot"
      HIBAK="${HIBAK/ IMERG csapadék/}"
    else
      echo "!! az ERA5-Land tartalék is elhasalt"
    fi
  fi

  futtat "LSA SAF párolgás"  python lsasaf_et.py    "$NAP"
  futtat "öntözésigény"      python ontozesigeny.py "$NAP"
  futtat "talaj vízhiány"    python aszaly.py       "$NAP"
  futtat "vízkivétel"        python kivetel.py      "$NAP"

  # A teljes medence két fala: SHMÚ Dévény és INHGA Baziás. Napi ritmusú, esőd.
  # A magyar doboz ettől függetlenül működik; kimaradása csak a medence-
  # szekciót hagyja a korábbi állapotában.
  futtat "teljes medence falai" python kulfold.py


  # A GRACE havi termék, 40–60 napos késéssel — havonta egyszer elég.
  if [ "$(cat "$GRACE_JELZO" 2>/dev/null)" != "$HONAP" ]; then
    if futtat "GRACE készlet-idősor" python grace.py; then
      echo "$HONAP" > "$GRACE_JELZO"
    fi
  fi

  echo "$NAP" > "$JELZO"
fi

echo "== mércék"
python fetch_data.py || { echo "!! a mérce-lekérés elhasalt"; exit 1; }

if [ -n "$HIBAK" ]; then
  echo "== FIGYELEM, kimaradt tagok:$HIBAK"
fi

# Publikálás. Csak akkor, ha be van állítva a Cloudflare Pages projekt.
if [ -n "${BASIN_PAGES_PROJECT:-}" ]; then
  echo "== publikálás"
  mkdir -p _publish
  cp index.html data.js data.json _publish/
  npx --yes wrangler pages deploy _publish \
      --project-name "$BASIN_PAGES_PROJECT" --commit-dirty=true
fi
