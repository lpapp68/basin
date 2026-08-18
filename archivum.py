#!/usr/bin/env python3
"""
archivum.py — saját idősor építése, mostantól.

A probléma, amit megold: a folyók hozama óras, a csapadék és a párolgás napokkal
korábbi. Amíg nincs saját archívumunk, a mérleg mindig kevert idejű. Ha viszont
minden futáskor eltároljuk az aznapi hozamokat, akkor amikor a lassabb tagok
utolérnek, VISSZAMENŐLEG összeáll az egyetlen napra vonatkozó mérleg.

A második haszna: a 2. panel kumulált egyenlege ma helyőrző. Saját napi sorozat
nélkül sosem lesz belőle mérés.

Két fájl:
  archiv/oras.csv  — minden futás egy sor (nyers)
  archiv/napi.csv  — naponta egy sor, az óras sorok átlagából (ebből dolgozunk)

A napi.csv-t mindig újraszámoljuk az oras.csv-ből, ezért idempotens: kétszer
futtatva sem duplázódik semmi.
"""

import csv
import datetime as dt
import pathlib
import statistics
from collections import defaultdict

ARCHIV = pathlib.Path("archiv")
ORAS = ARCHIV / "oras.csv"
NAPI = ARCHIV / "napi.csv"

ORAS_FEJLEC = ["rogzitve", "eszleles", "q_be", "q_ki", "paks_cm", "paks_q", "paks_c"]
NAPI_FEJLEC = ["nap", "mintak", "q_be", "q_ki", "paks_cm", "paks_q", "paks_c",
               "csapadek_mm", "parolgas_mm", "csapadek_datum", "parolgas_datum"]


def _nap(eszleles: str) -> str:
    """Az OVF időbélyege '2026.08.05. 14:00' alakú. Ebből a napot vágjuk ki."""
    # Egy-egy mércesor időbélyeg nélkül érkezhet; ilyenkor a sor kimarad
    # az összegzésből, ahelyett hogy az egész napi archívumot elrontaná.
    darabok = (eszleles or "").strip().split()
    if not darabok:
        return None
    t = darabok[0].rstrip(".")
    try:
        return dt.datetime.strptime(t, "%Y.%m.%d").date().isoformat()
    except ValueError:
        return dt.date.today().isoformat()


def rogzit(out: dict) -> None:
    """Egy sor az aktuális futásból. Csak MÉRT tételeket tárolunk."""
    ARCHIV.mkdir(exist_ok=True)
    paks = out.get("paks") or {}
    sor = {
        "rogzitve": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "eszleles": out["orak"]["oras"]["utolso"],
        "q_be": out["merleg_m3s"]["hozam_be"]["ertek"],
        "q_ki": out["merleg_m3s"]["hozam_ki"]["ertek"],
        "paks_cm": paks.get("vizallas_cm"),
        "paks_q": paks.get("hozam_m3s"),
        "paks_c": paks.get("vizho_c"),
    }
    uj = not ORAS.exists()
    with ORAS.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ORAS_FEJLEC)
        if uj:
            w.writeheader()
        w.writerow(sor)


def napi_osszegzes(params: dict) -> list[dict]:
    """Az oras.csv-ből napi átlagok. A légköri tagok a params.json-ből jönnek,
       a saját dátumukkal — így később látszik, melyik nap melyik forrásból teljes."""
    if not ORAS.exists():
        return []
    csoport = defaultdict(list)
    with ORAS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nap = _nap(r.get("eszleles"))
            if nap:
                csoport[nap].append(r)

    def atl(sorok, kulcs):
        ertekek = [float(s[kulcs]) for s in sorok if s.get(kulcs) not in (None, "")]
        return round(statistics.fmean(ertekek), 1) if ertekek else None

    # Az OMSZ foldi merese az elsodleges forras; az IMERG Early csak tartalek.
    # A muhold nyaron rendszeresen felulbecsul (lasd fetch_data.py).
    _o = params.get("csapadek_omsz_mm_nap") or {}
    _i = params.get("csapadek_mm_nap") or {}
    csap = _o if (_o.get("ertek") is not None and _o.get("datum") == _i.get("datum")) else _i
    par = params.get("parolgas_mm_nap", {})

    napok = []
    for nap in sorted(csoport):
        s = csoport[nap]
        napok.append({
            "nap": nap, "mintak": len(s),
            "q_be": atl(s, "q_be"), "q_ki": atl(s, "q_ki"),
            "paks_cm": atl(s, "paks_cm"), "paks_q": atl(s, "paks_q"),
            "paks_c": atl(s, "paks_c"),
            # A légköri tag csak akkor tartozik ehhez a naphoz, ha a dátuma egyezik.
            "csapadek_mm": csap.get("ertek") if csap.get("datum") == nap else None,
            "parolgas_mm": par.get("ertek") if par.get("datum") == nap else None,
            "csapadek_datum": csap.get("datum"), "parolgas_datum": par.get("datum"),
        })

    ARCHIV.mkdir(exist_ok=True)
    with NAPI.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NAPI_FEJLEC)
        w.writeheader()
        w.writerows(napok)
    return napok


def kumulalt(napok: list[dict], terulet_km2: float) -> dict | None:
    """Kumulált készletváltozás km3-ben, CSAK a teljes napokból.
       Teljes = van hozam, csapadék és párolgás is ugyanarra a napra."""
    teljes = [n for n in napok
              if None not in (n["q_be"], n["q_ki"], n["csapadek_mm"], n["parolgas_mm"])]
    if not teljes:
        return {"allapot": "gyűjtés alatt", "teljes_napok": 0,
                "osszes_nap": len(napok),
                "megjegyzes": "Saját idősor épül. Amíg nincs teljes nap, "
                              "a 2. panel a GRACE-alapú helyőrzőt mutatja."}
    m2 = terulet_km2 * 1e6
    km3 = 0.0
    for n in teljes:
        mm_netto = n["csapadek_mm"] - n["parolgas_mm"]
        # FIGYELEM: a q_ki ELŐJELESEN tárolódik (negatív), a v2.1 konvenciója szerint.
        # Ezért összeadás, nem kivonás.
        folyo_m3 = (n["q_be"] + n["q_ki"]) * 86400.0
        km3 += (mm_netto / 1000.0 * m2 + folyo_m3) / 1e9
    return {
        "allapot": "mérés", "teljes_napok": len(teljes), "osszes_nap": len(napok),
        "kezdet": teljes[0]["nap"], "veg": teljes[-1]["nap"],
        "kumulalt_km3": round(km3, 3),
        "provenance": "mert",
        "forras": "saját napi archívum (archiv/napi.csv)",
    }
