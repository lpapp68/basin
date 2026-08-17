#!/usr/bin/env python3
"""
talajviz.py — a talajvíz évtizedes süllyedése, 487 kút mérésével.

MIÉRT EZ A MÉRŐSZÁM, ÉS NEM A NAPI VÁLTOZÁS
A napi szintváltozás mediánja nulla: a kutak 62%-a egyik napról a másikra
nem mozdul. A talajvíz LASSÚ rekesz — a lap három rekesze (napok, hetek,
évtizedek) közül a leglassabb. Az évszakos minimum szeptemberre esik, a
tartós fogyás pedig évtizedes folyamat.

Amit érdemes mérni: hol tart a szint MA ahhoz képest, ahol tíz éve tartott,
ugyanabban a naptári időszakban. Ez kiszűri az évszakos ciklust.

AZ ADAT ELŐJELE
A vraquery 69-es kódja a terepszint alatti MÉLYSÉG: a nagyobb szám mélyebb
vizet jelent. Ezt független forrással igazoltuk — az aszálymonitoring
vízhiánya (ahol a nagyobb szám egyértelműen szárazabb) 46 párosított
helyszínen együtt mozog vele, mindössze 6 helyen ellentétesen.

MÓDSZER
  - kutanként a mai szint és a tíz évvel ezelőtti azonos időszak (±15 nap)
    mediánja
  - a kettő különbsége cm-ben; országosan a különbségek MEDIANJA
  - a medián azért kell, mert az átlagot néhány szélsőérték elvinné
"""

import datetime as dt
import json
import pathlib
import statistics
import sys

import vizapi

PARAMS = pathlib.Path("params.json")
EVEK = 10
ABLAK = 15


def aug_szint(tsz, evekkel, most):
    """Egy naptári időszak medián szintje kutanként, cm-ben."""
    k1 = most - dt.timedelta(days=365 * evekkel + ABLAK)
    k2 = most - dt.timedelta(days=365 * evekkel - ABLAK) if evekkel else most
    ki = {}
    for i in range(0, len(tsz), 300):
        try:
            r = vizapi.idosor(tsz[i:i+300], 69, k1, k2)
        except Exception:
            continue
        for k, v in r.items():
            if v:
                ki[k] = statistics.median([e for _, e in v])
    return ki


def main():
    most = dt.datetime.now(dt.timezone.utc)
    a = vizapi.allomasok(12)
    tsz = [x["Tsz"] for x in a]
    nev = {x["Tsz"]: x["Nev"].strip() for x in a}

    sys.stdout.write(f"mai szint ({len(tsz)} állomás)…\n")
    mai = aug_szint(tsz, 0, most)
    sys.stdout.write(f"  {len(mai)} kút\n{EVEK} évvel ezelőtti szint…\n")
    regen = aug_szint(tsz, EVEK, most)
    sys.stdout.write(f"  {len(regen)} kút\n")

    kozos = [k for k in mai if k in regen]
    if len(kozos) < 50:
        raise SystemExit(f"Túl kevés összevethető kút ({len(kozos)}).")

    # pozitív = mélyült = a víz lejjebb van
    kul = {k: mai[k] - regen[k] for k in kozos}
    ertek = sorted(kul.values())
    med = statistics.median(ertek)

    melyult = sum(1 for v in ertek if v > 5)
    emelkedett = sum(1 for v in ertek if v < -5)

    # a leginkább érintett helyek
    rangsor = sorted(kul.items(), key=lambda z: -z[1])[:8]

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["talajviz"] = {
        "sullyedes_cm": round(med, 1),
        "evek": EVEK,
        "datum": str(dt.date.today()),
        "kut_db": len(kozos),
        "melyult": melyult,
        "emelkedett": emelkedett,
        "also_kvartilis": round(ertek[len(ertek)//4], 1),
        "felso_kvartilis": round(ertek[3*len(ertek)//4], 1),
        "leginkabb": [{"nev": nev.get(k, str(k)), "cm": round(v, 1)}
                      for k, v in rangsor],
        "provenance": "helyszini",
        "forras": (f"OVF nyílt adat-API, {len(kozos)} talajvízkút; a mai és a "
                   f"{EVEK} évvel ezelőtti azonos naptári időszak (±{ABLAK} nap) "
                   "medián szintjének különbsége"),
        "figyelmeztetes": ("A napi változás mediánja nulla: a talajvíz lassú rekesz, "
                           "egyetlen nap alig mond róla valamit. Ezért évtizedes "
                           "léptékben mérünk, azonos naptári időszakot összevetve — "
                           "így az évszakos ciklus kiesik. Az országos érték a "
                           "kutankénti különbségek mediánja."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.write(f"\n{len(kozos)} kút, medián süllyedés {med:+.0f} cm "
                     f"({med/100:+.2f} m) {EVEK} év alatt\n")
    sys.stdout.write(f"  mélyült {melyult}, emelkedett {emelkedett}\n")
    sys.stdout.write(f"  kvartilisek: {ertek[len(ertek)//4]:+.0f} … "
                     f"{ertek[3*len(ertek)//4]:+.0f} cm\n")
    sys.stdout.write("  leginkább: " +
                     ", ".join(f"{nev.get(k,'')} {v:+.0f}" for k, v in rangsor[:4]) + "\n")


if __name__ == "__main__":
    main()
