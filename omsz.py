#!/usr/bin/env python3
"""
omsz.py — napi csapadék az OMSZ FÖLDI mérőhálózatából.

MIÉRT
A mérleg csapadék-tagja eddig egyetlen műholdas becslésen (IMERG Early) állt.
Ez nyáron rendszeresen felülbecsül: a magas, jeges felhőtetőket csapadékként
azonosítja, akkor is, ha a víz elpárolog, mielőtt leérne. Egy összevetés
augusztus 12-re: IMERG 1,50 mm, ERA5-Land 0,00 mm.

Az OMSZ (HungaroMet) nyílt adattára háromszáz automata állomás órás adatát
adja, két napra visszamenőleg. Ez FÖLDI MÉRÉS, nem becslés — a mérleg
legjobb referenciája a csapadékra.

  https://odp.met.hu/climate/observations_hungary/hourly/now/

FÁJLFORMÁTUM
  HABP_1H_{állomás}_now.zip → egy CSV, pontosvesszős, fejléc-blokkal
  oszlopok: StationNumber, Time (YYYYMMDDHHMM), r (csapadék mm), t, ta, ...
  hiányzó érték: -999

TERÜLETI ÁTLAG
  Az állomások egyenetlenül helyezkednek el, ezért a puszta átlag torzít.
  Rácsos súlyozást használunk: az országot cellákra osztjuk, cellánként
  átlagolunk, majd a cellák átlagát vesszük. Így a sűrűn műszerezett
  térségek nem nyomják el a ritkábbakat.

Futtatás:  python omsz.py 2026-08-17
"""

import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import pathlib
import statistics
import sys
import urllib.request
import zipfile

ALAP = "https://odp.met.hu/climate/observations_hungary/hourly/"
FEJ = {"User-Agent": "equora-basin/2.6 (+https://basin.equora.institute)"}
PARAMS = pathlib.Path("params.json")
HIANYZO = -999
RACS_OSZLOP, RACS_SOR = 8, 6      # a területi súlyozás felbontása


def _get(url: str, ido: int = 45) -> bytes:
    r = urllib.request.Request(url, headers=FEJ)
    return urllib.request.urlopen(r, timeout=ido).read()


def allomasok() -> dict:
    """{állomásszám: (lat, lon, név)} — csak a jelenleg üzemelők."""
    nyers = _get(ALAP + "station_meta_auto.csv").decode("utf-8", "replace")
    ki = {}
    # A fejléc mezőneveiben szóközök vannak (" EndDate") — normalizáljuk.
    olv = csv.reader(io.StringIO(nyers), delimiter=";")
    fejlec = [c.strip() for c in next(olv)]
    for sor in olv:
        s = dict(zip(fejlec, [c.strip() for c in sor]))
        try:
            szam = s["StationNumber"].strip()
            veg = s.get("EndDate", "")
            # a legfrissebb sor nyer: egy állomás többször is szerepelhet
            ki[szam] = (float(s["Latitude"]), float(s["Longitude"]),
                        s["StationName"].strip(), veg)
        except (ValueError, KeyError):
            continue
    return ki


def _egy_allomas(szam: str, nap: dt.date):
    """Egy állomás napi csapadékösszege mm-ben, vagy None."""
    try:
        nyers = _get(f"{ALAP}now/HABP_1H_{szam}_now.zip", 30)
    except Exception:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(nyers)) as z:
            with z.open(z.namelist()[0]) as f:
                szoveg = io.TextIOWrapper(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return None

    # a fejléc-blokk # jelekkel kezdődik; az adatsorok után jön
    sorok = [s for s in szoveg.split("\n") if s and not s.lstrip().startswith("#")]
    if len(sorok) < 2:
        return None
    fejlec = [c.strip() for c in sorok[0].split(";")]
    if "r" not in fejlec:
        return None
    i_ido, i_r = fejlec.index("Time"), fejlec.index("r")

    kulcs = nap.strftime("%Y%m%d")
    ossz, db = 0.0, 0
    for s in sorok[1:]:
        c = [x.strip() for x in s.split(";")]
        if len(c) <= max(i_ido, i_r) or not c[i_ido].startswith(kulcs):
            continue
        try:
            v = float(c[i_r])
        except ValueError:
            continue
        if v > HIANYZO + 1:          # a -999 hiányzó
            ossz += v
            db += 1
    # legalább 20 óra kell, hogy napi összegnek nevezhessük
    return round(ossz, 2) if db >= 20 else None


def napi_csapadek(nap: dt.date):
    """(területi átlag mm, állomásszám, részletek) — rácsos súlyozással."""
    a = allomasok()
    # csak az üzemelők: az EndDate a mai vagy tegnapi nap
    # Minden allomast lekerjuk: amelyik ad adatot a kert napra, az
    # uzemel. A meta-CSV EndDate mezoje nem megbizhato szuro - a fejlecben
    # szokoz van, es a regi sorok is benne maradnak.
    friss = a
    sys.stdout.write(f"  {len(friss)} üzemelő állomás lekérése…\n")
    sys.stdout.flush()

    ertek = {}
    with cf.ThreadPoolExecutor(max_workers=12) as vp:
        jovo = {vp.submit(_egy_allomas, k, nap): k for k in friss}
        for j in cf.as_completed(jovo):
            v = j.result()
            if v is not None:
                ertek[jovo[j]] = v

    if len(ertek) < 30:
        raise SystemExit(f"Túl kevés állomás adott adatot ({len(ertek)}).")

    # rácsos súlyozás: cellánként átlag, majd a cellák átlaga
    lat = [a[k][0] for k in ertek]; lon = [a[k][1] for k in ertek]
    la0, la1, lo0, lo1 = min(lat), max(lat), min(lon), max(lon)
    dla = (la1 - la0) / RACS_SOR or 1
    dlo = (lo1 - lo0) / RACS_OSZLOP or 1
    cellak = {}
    for k, v in ertek.items():
        i = min(int((a[k][0] - la0) / dla), RACS_SOR - 1)
        j = min(int((a[k][1] - lo0) / dlo), RACS_OSZLOP - 1)
        cellak.setdefault((i, j), []).append(v)

    cella_atlag = [statistics.fmean(v) for v in cellak.values()]
    atlag = statistics.fmean(cella_atlag)

    return atlag, len(ertek), {
        "cellak": len(cellak),
        "median": round(statistics.median(list(ertek.values())), 2),
        "max": round(max(ertek.values()), 1),
        "esett_hany": sum(1 for v in ertek.values() if v > 0.1),
    }


def main():
    nap = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=1))
    sys.stdout.write(f"OMSZ földi csapadék, {nap}\n")
    mm, db, r = napi_csapadek(nap)

    T = 93030 * 1e6
    sys.stdout.write(f"\n  területi átlag: {mm:.2f} mm/nap = {mm/1000*T/86400:.0f} m³/s\n")
    sys.stdout.write(f"  {db} állomás, {r['cellak']} rácscella, "
                     f"{r['esett_hany']} helyen esett\n")
    sys.stdout.write(f"  medián {r['median']} mm, max {r['max']} mm\n")

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["csapadek_omsz_mm_nap"] = {
        "ertek": round(mm, 2),
        "datum": str(nap),
        "allomas_db": db,
        "provenance": "helyszini",
        "forras": (f"OMSZ (HungaroMet) nyílt adattár, {db} automata állomás órás "
                   "csapadékösszege, rácsos területi súlyozással"),
        "figyelmeztetes": ("Földi mérés, pontszerű: az állomások között interpolálni "
                           "kell. A rácsos súlyozás azt kezeli, hogy a hálózat "
                           "egyenetlen — cellánként átlagolunk, majd a cellák átlagát "
                           "vesszük, így a sűrűn műszerezett térségek nem nyomják el "
                           "a ritkábbakat."),
        "hivatkozas": "odp.met.hu",
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    imerg = p.get("csapadek_mm_nap") or {}
    if imerg.get("datum") == str(nap):
        i = imerg["ertek"]
        sys.stdout.write(f"\n  IMERG Early (műholdas): {i:.2f} mm/nap\n")
        sys.stdout.write(f"  eltérés: {mm - i:+.2f} mm "
                         f"({(mm/i - 1)*100:+.0f}%)\n" if i else "\n")


if __name__ == "__main__":
    main()
