#!/usr/bin/env python3
"""
ontozoviz.py — a Duna napi hozama és a paksi vízhő 1991-től, az „Öntözővíz a
Dunából” szekcióhoz.

Futtatás:
  python ontozoviz.py [YYYY-MM-DD]   # az utolsó napok frissítése az OVF API-ból + duna.json
  python ontozoviz.py --json         # csak a duna.json újraírása a gyorsítótárból (hálózat nélkül)
  python ontozoviz.py --teljes       # a teljes 1991-től induló idősor újraletöltése (~10 perc)

MIRE KELL
A szekció azt teszteli, hogy egy elképzelt mezőföldi szivattyútelep mikor és
kinek a rovására vehet vizet a Dunából. Ehhez 35 év napi adata kell, nem a
mostani pillanatkép: a kérdés az, hogy a kisvizes, meleg napok milyen gyakran
esnek egybe az öntözés csúcsával, és mennyi víz marad a küszöb fölött a
tavaszi áradásokban.

MI MÉRT, ÉS MI SZÁMÍTOTT
  MÉRT   Dunaújváros (OVF 547) napi vízhozama: a negyedórás/órás vízhozam napi
         átlaga. A vízhozam a vízállásból, kalibrált vízhozamgörbével számított
         érték — a lap jelölésével „helyszíni adatból számított”.
  MÉRT   Paks (OVF 549) vízhője. KÉT ÉRZÉKELŐ, eltérő módszerrel:
           85 — a reggeli (7 órai) felszíni észlelés, 1991-től folyamatos,
                de 2026-ban nem érkezik;
           89 — a mederfenéki szonda, 2002-től, nagy gyakorisággal; ennek a
                napi átlagát használjuk ott, ahol a 85 hiányzik.
         A 2002–2025 közös napjain a kettő átlagos eltérése 0,01 °C, nyáron
         −0,09 °C; a 23 °C fölötti napokon viszont a 89-es napi átlag átlagosan
         0,4 °C-kal alacsonyabb (a reggeli egyetlen észlelés a meleg napokon
         jellemzően a csúcs közelében jár). A pótolt napok ezért a meleg
         napokat inkább ALULBECSÜLIK. A duna.json napra pontosan jelöli, hol
         melyik érzékelő adata áll.

A naptári nap CET szerint (UTC+1, nyári időszámítás nélkül) — így egy nap
mindig 24 óra, és a napi átlag nem tolódik az óraátállításnál.

A KIMENETEK
  archiv/duna_napi.csv — gyorsítótár, a bot commitolja (git add archiv)
  duna.json            — a lap ebből számol; generált, nincs a repóban
"""

import csv
import datetime as dt
import json
import pathlib
import sys
from collections import defaultdict

import vizapi

GYORS = pathlib.Path("archiv/duna_napi.csv")
KI = pathlib.Path("duna.json")
MEZOK = ["nap", "dunaujvaros_q", "budapest_q", "paks_q", "paks_c", "paks_c_forras"]
KEZDO = dt.date(1991, 1, 1)

DUNAUJVAROS, BUDAPEST, PAKS = 547, 1026, 549
HOZAM, VIZHO_FELSZIN, VIZHO_FENEK = 87, 85, 89
CET = dt.timedelta(hours=1)


def beolvas() -> dict:
    sorok = {}
    if GYORS.exists():
        with GYORS.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sorok[r["nap"]] = {k: r.get(k, "") for k in MEZOK}
    return sorok


def kiir(sorok: dict) -> None:
    GYORS.parent.mkdir(exist_ok=True)
    ideig = GYORS.with_suffix(".uj")
    with ideig.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MEZOK)
        w.writeheader()
        for n in sorted(sorok):
            w.writerow(sorok[n])
    ideig.replace(GYORS)


def _napi_atlag(pontok) -> dict:
    gy = defaultdict(list)
    for ido, ertek in pontok:
        gy[(ido + CET).date().isoformat()].append(ertek)
    return {n: sum(v) / len(v) for n, v in gy.items()}


def letolt(kezd: dt.date, veg: dt.date, sorok: dict) -> int:
    """Félévenkénti darabokban kér: egy kérés így néhány ezer pont marad."""
    friss = 0
    darab_kezd = dt.datetime.combine(kezd, dt.time()) - CET
    vege = dt.datetime.combine(veg + dt.timedelta(days=1), dt.time()) - CET
    while darab_kezd < vege:
        darab_veg = min(vege, darab_kezd + dt.timedelta(days=183))
        kerdes = [((DUNAUJVAROS, BUDAPEST, PAKS), HOZAM),
                  ((PAKS,), VIZHO_FELSZIN), ((PAKS,), VIZHO_FENEK)]
        eredmeny = {}
        for tsz, kod in kerdes:
            for probalkozas in range(3):
                try:
                    eredmeny[kod] = vizapi.idosor(list(tsz), kod, darab_kezd, darab_veg)
                    break
                except Exception as e:
                    if probalkozas == 2:
                        raise RuntimeError(f"OVF API, adatfajta {kod}: {e}")
        q = {t: _napi_atlag(p) for t, p in eredmeny[HOZAM].items()}
        t85 = _napi_atlag(eredmeny[VIZHO_FELSZIN].get(PAKS, []))
        t89 = _napi_atlag(eredmeny[VIZHO_FENEK].get(PAKS, []))
        napok = set().union(*[set(v) for v in q.values()], t85, t89)
        for n in napok:
            if not (kezd.isoformat() <= n <= veg.isoformat()):
                continue
            s = sorok.setdefault(n, {k: "" for k in MEZOK})
            s["nap"] = n
            for tsz, mezo in ((DUNAUJVAROS, "dunaujvaros_q"), (BUDAPEST, "budapest_q"), (PAKS, "paks_q")):
                v = q.get(tsz, {}).get(n)
                if v is not None:
                    s[mezo] = f"{v:.1f}"
            if n in t85:
                s["paks_c"], s["paks_c_forras"] = f"{t85[n]:.1f}", "85"
            elif n in t89:
                s["paks_c"], s["paks_c_forras"] = f"{t89[n]:.1f}", "89"
            friss += 1
        darab_kezd = darab_veg
    return friss


def json_ir(sorok: dict) -> None:
    """Napi tömbök a KEZDO naptól. A null hiányzó napot jelent, nem nullát."""
    if not sorok:
        return
    utolso = max(dt.date.fromisoformat(n) for n in sorok)
    napok = (utolso - KEZDO).days + 1
    q, t, t89_szakaszok = [], [], []
    for i in range(napok):
        n = (KEZDO + dt.timedelta(days=i)).isoformat()
        s = sorok.get(n) or {}
        qv = s.get("dunaujvaros_q")
        tv = s.get("paks_c")
        q.append(round(float(qv)) if qv else None)
        t.append(round(float(tv), 1) if tv else None)
        if s.get("paks_c_forras") == "89":
            if t89_szakaszok and t89_szakaszok[-1][1] == i - 1:
                t89_szakaszok[-1][1] = i
            else:
                t89_szakaszok.append([i, i])
    ki = {
        "v": 1,
        "generalva": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "kezdo": KEZDO.isoformat(),
        "utolso": utolso.isoformat(),
        "q_allomas": "Duna, Dunaújváros (OVF törzsszám 547), fkm 1580,6",
        "t_allomas": "Duna, Paks (OVF törzsszám 549), fkm 1531,3",
        "forras": "OVF nyílt adat-API (data.vizugy.hu): vízhozam (87), vízhő (85 felszíni reggeli "
                  "észlelés; ahol hiányzik, 89 mederfenéki szonda napi átlaga)",
        "q": q,
        "t": t,
        "t89": [[(KEZDO + dt.timedelta(days=a)).isoformat(), (KEZDO + dt.timedelta(days=b)).isoformat()]
                for a, b in t89_szakaszok],
    }
    nyers = json.dumps(ki, ensure_ascii=False, separators=(",", ":"))
    json.loads(nyers)
    ideig = KI.with_suffix(".uj")
    ideig.write_text(nyers, encoding="utf-8")
    ideig.replace(KI)
    print(f"duna.json: {napok} nap ({KEZDO} – {utolso}), {len(nyers)//1024} kB")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    sorok = beolvas()
    if arg == "--json":
        json_ir(sorok)
        return
    ma = dt.date.today()
    if arg == "--teljes" or not sorok:
        kezd = KEZDO
    else:
        # Az utolsó tíz napot újrakérjük: a friss napok átlaga a késve érkező
        # mintákkal még változik, és az OVF utólag is javít.
        kezd = dt.date.fromisoformat(max(sorok)) - dt.timedelta(days=10)
    veg = dt.date.fromisoformat(arg) if arg[:2] == "20" else ma
    veg = max(veg, ma)
    db = letolt(kezd, veg, sorok)
    kiir(sorok)
    print(f"{kezd} – {veg}: {db} napi sor frissítve, összesen {len(sorok)}")
    json_ir(sorok)


if __name__ == "__main__":
    main()
