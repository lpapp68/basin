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

JAVÍTÁS, 2026-10-05 — két hiba, mindkettő a napi mérleget érintette:

1. Visszacsatolás. A rogzit() a mérleg hozamát írta az órás sorba, a mérleg pedig,
   mióta a legutóbbi teljes napból számol, épp ebből az archívumból veszi a hozamot.
   A kör bezárult: a kilépő hozam hetekig ugyanaz az érték maradt, a belépő naponta
   a Hernád-taggal kúszott felfelé. Mostantól a rogzit() a mércék pillanatnyi
   összegét írja (pillanatkep_m3s, Hernád nélkül — azt a mérleg adja hozzá).
   A hozamot csak a javítás utáni sorokból átlagoljuk: a szennyeződés kezdete a
   mostani archívumból bizonytalan. A régi sorok a helyükön maradnak; az első
   helyes rögzítés idejét az archiv/.hozam-javitas jelzőfájl őrzi.

2. Elvesző légköri tagok. A napi.csv minden futáskor újraíródott, a csapadékot és
   a párolgást pedig csak arra a napra töltöttük ki, amelyikre a params.json éppen
   adatot hozott — a korábbi napokét az újraírás letörölte, a teljes napok száma
   egyen ragadt. Mostantól a korábban tárolt értékek megmaradnak.
"""

import csv
import datetime as dt
import pathlib
import statistics
from collections import defaultdict

ARCHIV = pathlib.Path("archiv")
ORAS = ARCHIV / "oras.csv"
NAPI = ARCHIV / "napi.csv"
# Az első helyes, mércékből vett hozamrögzítés ideje. A korábbi sorok hozama
# kimarad a napi átlagból (visszacsatolás, lásd fent); a Paks-adatuk marad.
JAVITAS = ARCHIV / ".hozam-javitas"

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


def _javitas_kezdete():
    """Az első helyes hozamrögzítés ideje (ISO, UTC), vagy None."""
    try:
        return JAVITAS.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def rogzit(out: dict) -> None:
    """Egy sor az aktuális futásból. Csak MÉRT tételeket tárolunk.

    A hozam a mércék pillanatnyi összege. A merleg_m3s hozama ebből az
    archívumból számolt napi átlag: azt visszaírva az archívum a saját
    kimenetét táplálná vissza.
    """
    ARCHIV.mkdir(exist_ok=True)
    paks = out.get("paks") or {}
    most = out.get("pillanatkep_m3s") or {}
    q_ki = most.get("hozam_ki")
    rogzitve = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if not JAVITAS.exists():
        JAVITAS.write_text(rogzitve + "\n", encoding="utf-8")
    sor = {
        "rogzitve": rogzitve,
        "eszleles": out["orak"]["oras"]["utolso"],
        "q_be": most.get("hozam_be"),
        # A v2.1 előjel-konvenciója: a távozó hozam negatív.
        "q_ki": -abs(q_ki) if q_ki is not None else None,
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

    # A korábban tárolt légköri tagok: a napi.csv újraírásakor megmaradnak.
    korabbi = {}
    if NAPI.exists():
        with NAPI.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                korabbi[r.get("nap")] = r

    def tarolt(nap, kulcs):
        v = (korabbi.get(nap) or {}).get(kulcs)
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    javitas = _javitas_kezdete()

    def tiszta(sorok):
        """A hozamátlaghoz csak a javítás utáni sorok számítanak."""
        if javitas is None:
            return []
        return [s for s in sorok if (s.get("rogzitve") or "") >= javitas]

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
        q = tiszta(s)
        napok.append({
            "nap": nap, "mintak": len(q),
            "q_be": atl(q, "q_be"), "q_ki": atl(q, "q_ki"),
            "paks_cm": atl(s, "paks_cm"), "paks_q": atl(s, "paks_q"),
            "paks_c": atl(s, "paks_c"),
            # A légköri tag ahhoz a naphoz tartozik, amelyikre a forrás dátuma szól;
            # a többi nap korábban tárolt értéke megmarad.
            "csapadek_mm": csap.get("ertek") if csap.get("datum") == nap else tarolt(nap, "csapadek_mm"),
            "parolgas_mm": par.get("ertek") if par.get("datum") == nap else tarolt(nap, "parolgas_mm"),
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
