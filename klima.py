#!/usr/bin/env python3
"""
klima.py — sokéves vízstressz-viszonyítás az LSA SAF archívumából.

Futtatás:  python klima.py [ÉVEK] [ABLAK]
           python klima.py 10 7     -> 10 év, a mai nap ±7 napja

MIÉRT KELL
A vízstressz-index (ET_act / ET_ref) ma 0,30. Ez azt mondja meg, a felszín a
LEHETSÉGES párolgás hányad részén működik — azt viszont nem, hogy ez sok vagy
kevés augusztusban. Nyáron ez az arány csapadékos évben is 1 alatt van.

Viszonyítási alaphoz több év kell. Ez a script ugyanannak a naptári napnak a
környékét tölti le az elmúlt N évből, és kiszámolja a sokéves átlagot ÉS a
szórást. A szórás legalább annyira fontos: ha az adott nap évről évre 0,15-ös
szórással ingadozik, akkor a mai 0,30 belefér a szokásosba, és ezt ki kell
mondani. Enélkül a „szokásosnál szárazabb" állítás megalapozatlan volna.

MENNYI IDŐ
Naponta két fájl (METREF és DMETv3), ablak × év darabszámban. 10 év ±7 nap =
300 fájl, néhány tíz perc. A már kiszámolt naptári napokat kihagyja, tehát a
második futás gyors.

AZ EREDMÉNY NAPTÁRI NAPRA SZÓL
A params.json `parolgas_klima` mezőjébe kerül, MM-DD kulccsal. A tábla
fokozatosan telik fel, ahogy telnek a napok — nem kell az egész évet letölteni.
"""

import datetime as dt
import json
import pathlib
import statistics
import sys

import maszk
import ontozesigeny as O

PARAMS = pathlib.Path("params.json")


def egy_nap(nap: dt.date):
    """Egy nap ET_act és ET_ref országos átlaga, majd az arányuk. None, ha hiányzik."""
    try:
        ref = O.mezo(O.letolt(O.URL_REF.format(d=nap)), ("METREF", "ETref", "ET"))
        act = O.mezo(O.letolt(O.URL_ACT.format(d=nap)), ("ET",))
    except Exception as e:
        print(f"    {nap}: kimaradt ({str(e)[:60]})")
        return None
    r, _, _ = maszk.sulyozott_atlag(ref, "lat", "lon")
    a, _, _ = maszk.sulyozott_atlag(act, "lat", "lon")
    if r is None or a is None or r <= 0:
        return None
    return float(a), float(r), float(a) / float(r)


def main():
    evek = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    ablak = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    ma = dt.date.today()

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    klima = p.get("parolgas_klima") or {}

    for eltol in range(-ablak, ablak + 1):
        cel = ma + dt.timedelta(days=eltol)
        kulcs = cel.strftime("%m-%d")
        if klima.get(kulcs, {}).get("evek", 0) >= evek - 2:
            print(f"  {kulcs}: már megvan ({klima[kulcs]['evek']} év)")
            continue

        print(f"  {kulcs}:")
        aranyok, act, ref = [], [], []
        for e in range(1, evek + 1):
            try:
                nap = cel.replace(year=cel.year - e)
            except ValueError:            # február 29.
                continue
            r = egy_nap(nap)
            if r:
                act.append(r[0]); ref.append(r[1]); aranyok.append(r[2])
                print(f"    {nap}: {r[0]:.2f} / {r[1]:.2f} = {r[2]:.3f}")

        if len(aranyok) < 3:
            print(f"    kevés év ({len(aranyok)}), kihagyva")
            continue

        klima[kulcs] = {
            "arany_atlag": round(statistics.fmean(aranyok), 3),
            "arany_szoras": round(statistics.pstdev(aranyok), 3) if len(aranyok) > 1 else None,
            "et_act_atlag": round(statistics.fmean(act), 2),
            "et_ref_atlag": round(statistics.fmean(ref), 2),
            "evek": len(aranyok),
            "tartomany": f"{ma.year - evek}–{ma.year - 1}",
        }
        print(f"    ÁTLAG {klima[kulcs]['arany_atlag']} "
              f"(szórás {klima[kulcs]['arany_szoras']}, {len(aranyok)} év)")

        # Minden nap után mentünk: a futás órákig tarthat, kár volna elveszíteni.
        p["parolgas_klima"] = klima
        PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    p["parolgas_klima"] = klima
    p["_klima_megjegyzes"] = (
        "Sokéves vízstressz-viszonyítás az EUMETSAT LSA SAF archívumából, naptári nap "
        "szerint. Az arány ET_act/ET_ref; az átlag ugyanannak a naptári napnak az "
        "elmúlt évekbeli értékeiből származik. A szórás megmutatja, mennyire ingadozik "
        "az adott nap évről évre — ha nagy, a mai eltérés kevésbé rendkívüli.")
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nparams.json: {len(klima)} naptári nap klimatológiája")


if __name__ == "__main__":
    main()
