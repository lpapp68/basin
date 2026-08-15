#!/usr/bin/env python3
"""
aszaly.py — talajnedvesség és vízhiány az OVF aszálymonitoring-hálózatából.

Futtatás:  python aszaly.py [YYYY-MM-DD]

MIÉRT EZ HIÁNYZOTT
A mérleg eddig a folyókat és a légkört mérte, a köztes rekeszt nem. Pedig a talaj
az, ahol a víz napokig-hetekig marad, és ahol az aszály valójában zajlik. A folyón
átfolyó víz és a hátsági szárazság KÉT KÜLÖNBÖZŐ REKESZ — ezt mutatja meg ez az adat.

MIT AD
  TalajNedv10…75  óránkénti talajnedvesség hat mélységben, térfogatszázalékban
  WD35, WD80      napi vízhiány MILLIMÉTERBEN a 35, illetve 80 cm-es rétegre
  Csapadek60      állomási csapadék

A WD80 a fontos: nem index, hanem milliméter — közvetlenül összemérhető a mérleg
többi tagjával, és megmondja, mennyi víz hiányzik a gyökérzónából.

A VÉGPONT
Nincs dokumentálva; a lap JavaScriptjéből fejtettük vissza (hydroinfo_v5.js,
retrieveDroughtData). Az index.php JSON-t ad vissza egy generált ZIP útvonalával.
FIGYELEM: a 'confirm', 'sepchar', 'dateformat' paraméterek jelenléte 4-es hibát okoz —
ezeket NEM szabad elküldeni. A lekérhető időszak legfeljebb 90 nap.

Mivel visszafejtett és nem dokumentált felület, TÖRÉKENY. Az OVF-adatigénylésben
ezt is érdemes megemlíteni: van-e hivatalos gépi hozzáférés ehhez az adathoz.
"""

import datetime as dt
import io
import json
import pathlib
import statistics
import sys
import urllib.parse
import urllib.request
import zipfile

BASE = "https://aszalymonitoring.vizugy.hu/"
PARAMS = pathlib.Path("params.json")
ALLOMASOK = pathlib.Path("aszaly_allomasok.json")

# Kezdéshez néhány állomás. A hátságiak külön érdekesek, mert ott a legmélyebb a hiány.
ALAP_ALLOMASOK = {
    # Tíz állomás, az ország egészére elosztva (legtávolabbi-pont mintavétel).
    # Az azonosítót futáskor az aszaly_allomasok.json adja, ezért itt None elég.
    "Kölcse": None,
    "Bernecebaráti": None,
    "Püski": None,
    "Egyek": None,
    "Nagykőrös": None,
    "Vasszentmihály": None,
    "Enying": None,
    "Sarkad": None,
    "Röszke": None,
    "Felsőszentmárton": None,
}
MEZOK = ["TalajNedv10", "TalajNedv20", "TalajNedv30", "TalajNedv45",
         "TalajNedv60", "TalajNedv75", "Csapadek60", "WD35", "WD80",
         "coords", "statname"]


def ms(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def allomasjegyzek() -> dict:
    """A választólista az aszálymonitoring nyitóoldalán van, GUID-okkal."""
    if ALLOMASOK.exists():
        return json.loads(ALLOMASOK.read_text(encoding="utf-8"))
    import re
    req = urllib.request.Request(BASE, headers={"User-Agent": "Mozilla/5.0"})
    t = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    sel = re.search(r"<select[^>]*drought_station.*?</select>", t, re.S)
    d = {nev.strip(): voa for voa, nev in
         re.findall(r"<option[^>]*value=['\"]([^'\"]+)['\"][^>]*>([^<]*)", sel.group(0))
         if voa.strip()}
    ALLOMASOK.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def letolt(voak: list, kezd: dt.date, veg: dt.date) -> str:
    """FONTOS: csak ezt az öt paramétert küldjük. Bármi más 4-es hibát ad."""
    p = {"view": "downloading", "voa[]": voak, "param[]": MEZOK,
         "start": ms(kezd), "end": ms(veg)}
    url = BASE + "index.php?" + urllib.parse.urlencode(p, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "X-Requested-With": "XMLHttpRequest"})
    d = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
    if "error" in d:
        raise RuntimeError(f"A szolgáltatás hibakódja: {d['error']}")
    zurl = BASE + urllib.parse.quote(d["dfile"]["file"].replace("\\", "/"))
    req = urllib.request.Request(zurl, headers={"User-Agent": "Mozilla/5.0"})
    nyers = urllib.request.urlopen(req, timeout=180).read()
    with zipfile.ZipFile(io.BytesIO(nyers)) as z:
        return z.read(z.namelist()[0]).decode("utf-8", "replace")


def feldolgoz(szoveg: str) -> list:
    sorok = []
    for s in szoveg.splitlines()[1:]:
        r = s.split(";")
        if len(r) < 8:
            continue
        try:
            ertek = float(r[5])
        except ValueError:
            continue
        sorok.append({"ido": r[0], "param": r[1], "allomas": r[2],
                      "ertek": ertek, "egyseg": r[6], "melyseg": r[7]})
    return sorok


def main():
    veg = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=1))
    kezd = veg - dt.timedelta(days=30)

    jegyzek = allomasjegyzek()
    voak, nevek = [], []
    for nev in ALAP_ALLOMASOK:
        v = jegyzek.get(nev)
        if v:
            voak.append(v)
            nevek.append(nev)
    if not voak:
        raise RuntimeError("Egyetlen állomást sem találtam a jegyzékben.")
    print(f"  állomások: {', '.join(nevek)}")

    # Egyszerre több állomás 4-es hibát ad — egyesével kérjük.
    sorok = []
    for nev, v in zip(nevek, voak):
        try:
            sorok += feldolgoz(letolt([v], kezd, veg))
        except Exception as e:
            print(f"    {nev}: kimaradt ({e})")
    print(f"  {len(sorok)} adatsor {kezd} – {veg}")

    # A vízhiány a lényeg: milliméterben, a 80 cm-es rétegre, a legutolsó napra.
    wd = [r for r in sorok if r["param"].startswith("Vízhiány") and "80" in r["melyseg"]]
    utolso = {}
    for r in sorted(wd, key=lambda x: x["ido"]):
        utolso[r["allomas"]] = r

    if utolso:
        ertekek = [r["ertek"] for r in utolso.values()]
        atlag = statistics.fmean(ertekek)
        p = json.loads(PARAMS.read_text(encoding="utf-8"))
        p["talaj_vizhiany"] = {
            "datum": max(r["ido"] for r in utolso.values()),
            "atlag_mm": round(atlag, 1),
            "min_mm": round(min(ertekek), 1),
            "max_mm": round(max(ertekek), 1),
            "allomasok": {nev: round(r["ertek"], 1) for nev, r in sorted(utolso.items())},
            "melyseg": "80 cm",
            "provenance": "mert",
            "forras": "OVF Aszálymonitoring — Operatív Vízhiány Értékelő "
                      "és Előrejelző Rendszer (aszalymonitoring.vizugy.hu)",
            "figyelmeztetes": ("Néhány állomás, nem országos átlag. A végpont nincs "
                               "dokumentálva, a lap JavaScriptjéből visszafejtve — "
                               "bármikor elromolhat."),
        }
        PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n  vízhiány a 80 cm-es rétegben, {p['talaj_vizhiany']['datum']}:")
        for nev, e in sorted(utolso.items()):
            print(f"    {nev:<22}{e['ertek']:>7.1f} mm")
        print(f"    {'ÁTLAG':<22}{atlag:>7.1f} mm")


if __name__ == "__main__":
    main()
