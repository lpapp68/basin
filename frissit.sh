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
  # A kapu a FELDOLGOZOTT napot nézi, nem a kértet. Az IMERG Early késése miatt
  # a kért nap gyakran nincs meg; ilyenkor visszalépünk. Ha a kapu a kért napot
  # nézné, minden futás újra feldolgozná ugyanazt a napot, és a mérleg tartósan
  # két nappal lemaradna.
  #
  # Így viszont óránként újrapróbáljuk a friss napot, amíg a termék meg nem
  # érkezik — és amint megvan, a mérleg egy napot lép előre.
  FELDOLGOZOTT=$(cat archiv/.feldolgozott-napi 2>/dev/null || echo "")
  if [ "$FELDOLGOZOTT" = "$NAP" ]; then MOD=oras; else MOD=napi; fi
fi

# Minden napi tag hibáját összegyűjtjük, hogy a futás végén egy helyen látszódjon.
HIBAK=""
NAPLO="archiv/futas-hibak.txt"
: > "$NAPLO"
futtat() {                      # futtat <cimke> <parancs...>
  local cimke="$1"; shift
  echo "-- $cimke"
  local ki
  # A hibaüzenetet is elkapjuk: enélkül az Actionsben csend van, és csak
  # napokkal később derül ki, hogy egy tag megállt.
  if ki=$("$@" 2>&1); then
    echo "$ki"
    return 0
  fi
  echo "$ki"
  echo "!! $cimke ELHASALT"
  HIBAK="$HIBAK $cimke"
  # az utolsó két sor elég a diagnózishoz, és elfér a lapon
  printf '%s: %s\n' "$cimke" "$(echo "$ki" | tail -2 | tr '\n' ' ')" >> "$NAPLO"
  return 1
}

if [ "$MOD" = "napi" ]; then
  # A visszalépés átírja a NAP-ot; a kapuhoz az EREDETI kért nap kell.
  KERT_NAP="$NAP"
  echo "== napi frissítés: $NAP"

  # A csapadék és a párolgás egyetlen naphoz tartozik. Az IMERG Early napi terméke
  # 24 óránál többet késik, ezért a legfrissebb nap gyakran hiányzik — ilyenkor
  # visszalépünk. A párolgás CSAK arra a napra fut, amelyikre a csapadék megvan.
  #
  # Az ERA5-Land tartalékot itt szándékosan mellőzzük: öt-hat napos késése miatt
  # egy egy-két napos dátumhoz sosem tud segíteni, viszont minden futásban
  # negyven másodperc CDS-sorbanállást emésztene fel. Visszamenőleges
  # feltöltéshez az era5_precip.py továbbra is kézzel futtatható.
  CSAPNAP=""
  for eltol in 1 2 3; do
    probal=$(date -u -v-${eltol}d +%Y-%m-%d 2>/dev/null \
             || date -u -d "${eltol} days ago" +%Y-%m-%d)
    if futtat "IMERG csapadék ($probal)" python imerg_precip.py "$probal"; then
      CSAPNAP="$probal"; break
    fi
  done

  if [ -n "$CSAPNAP" ]; then
    NAP="$CSAPNAP"
    # a korábbi napok sikertelen próbái nem hibák, csak a termék késése
    HIBAK=""
    : > "$NAPLO"
    # Az OMSZ földi mérőhálózata az elsődleges csapadék-forrás; az IMERG Early
    # csak tartalék és keresztellenőrzés. Nélküle a műholdas (gyakran
    # felülbecsülő) érték kerülne a mérlegbe.
    futtat "OMSZ földi csapadék" python omsz.py "$NAP" || true
    # A referencia-párolgás is földi mérésből: 248 állomás, FAO-56.
    # A sugárzást a többségen a hőmérséklet-ingásból becsüljük — a 39
    # mérő állomáson ellenőrizve az eltérés 0,7%, rendszeres torzítás nélkül.
    futtat "OMSZ referencia-párolgás" python omsz_et0.py "$NAP" || true

    futtat "LSA SAF párolgás" python lsasaf_et.py "$NAP"

    # FUGGETLEN keresztellenorzes: az ERA5-Land parolgasa. Ot-hat napos
    # kesessel jon, ezert het nappal ezelottre kerjuk - a lap kulon
    # panelben mutatja, non a merleg napjatol elterhet.
    ERA5_NAP=$(date -u -v-7d +%Y-%m-%d 2>/dev/null || date -u -d "7 days ago" +%Y-%m-%d)
    futtat "ERA5-Land parolgas keresztellenorzes" python era5_et.py "$ERA5_NAP" || true
  else
    echo "!! a csapadék három napra sem szerezhető meg — a párolgás sem fut,"
    echo "   hogy a mérleg egyetlen napon maradjon"
    HIBAK="$HIBAK csapadék-három-napra-sem"
  fi

  futtat "öntözésigény"      python ontozesigeny.py "$NAP"
  futtat "talaj vízhiány"    python aszaly.py       "$NAP"
  futtat "vízkivétel"        python kivetel.py      "$NAP"

  # A teljes medence két fala: SHMÚ Dévény és INHGA Baziás. Napi ritmusú, esőd.
  # A magyar doboz ettől függetlenül működik; kimaradása csak a medence-
  # szekciót hagyja a korábbi állapotában.
  futtat "teljes medence falai" python kulfold.py


  # A GRACE havi termék, a NASA-nál két-három hónapos feldolgozási késéssel.
  # HETENTE ellenőrizzük, nem havonta: a kiadás dátuma kiszámíthatatlan, és egy
  # havi kapuval hetekig nem vennénk észre az új szemcsét. A letöltés úgyis csak
  # akkor történik meg, ha tényleg van új adat.
  UTOLSO_GRACE=$(cat "$GRACE_JELZO" 2>/dev/null || echo "")
  MA_NAP=$(date -u +%Y-%m-%d)
  KELL_GRACE=1
  if [ -n "$UTOLSO_GRACE" ]; then
    HATAR=$(date -u -v-7d +%Y-%m-%d 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%d)
    if [ "$UTOLSO_GRACE" \> "$HATAR" ]; then KELL_GRACE=0; fi
  fi
  if [ "$KELL_GRACE" = "1" ]; then
    if futtat "GRACE készlet-idősor" python grace.py; then
      echo "$MA_NAP" > "$GRACE_JELZO"
    fi
  fi


  # A jelzőbe a KÉRT nap kerül (ma mire próbálkoztunk), nem a feldolgozott.
  # Enélkül a visszalépés beragasztja a ciklust: a kapu sosem látja
  # teljesítettnek a mai napot, viszont a visszalépés mindig ugyanoda jut.
  # A .utolso-napi a kért napot őrzi (mikor próbálkoztunk utoljára),
  # a .feldolgozott-napi azt, ameddig ténylegesen eljutottunk. A kapu ez
  # utóbbit nézi.
  echo "$KERT_NAP" > "$JELZO"
  echo "$NAP" > "archiv/.feldolgozott-napi"
fi

echo "== mércék"
python fetch_data.py || { echo "!! a mérce-lekérés elhasalt"; exit 1; }

if [ -n "$HIBAK" ]; then
  echo "== FIGYELEM, kimaradt tagok:$HIBAK"
fi

# Publikálás. Csak akkor, ha be van állítva a Cloudflare Pages projekt.
if [ -n "${BASIN_PAGES_PROJECT:-}" ]; then
  echo "== publikálás"
  # Minden publikálandó fájl egy helyen. Ami kimarad, azt a következő
  # botfutás letörli a lapról — ez korábban a logóval megtörtént.
  mkdir -p _publish
  cp index.html data.js data.json logo.png logo.svg terkep.json robots.txt sitemap.xml llms.txt googled3302b927f898901.html favicon.ico favicon-32.png apple-touch-icon.png _publish/
  npx --yes wrangler pages deploy _publish \
      --project-name "$BASIN_PAGES_PROJECT" --commit-dirty=true
fi
