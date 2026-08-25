#!/usr/bin/env python3
"""
shmu.py — a Hernád (Hornád) határszelvényének vízhozama az SHMÚ napi tábláiból.

MIÉRT
A Hernád a mérleg egyik NYITOTT FALA: Szlovákiából érkezik, a Sajóba torkollik,
és a magyar Sajópüspöki mérce a torkolat FÖLÖTT van — vagyis a Hernád hozama
sehol nem szerepel a bejövő oldalon. Ez a mérleg le nem zárt tagjának egyik
ismert forrása.

Az utolsó szlovák szelvény Ždaňa, közvetlenül a határ előtt.

TÖRÉKENYSÉG
Az adat HTML-táblából jön, nem API-ból. Ha az SHMÚ átalakítja az oldalt, a
beolvasás csendben rossz számot adhatna — ez rosszabb, mint ha semmit nem adna.
Ezért minden futáskor ellenőrizzük a tábla SZERKEZETÉT: a fejléc oszlopneveit,
az oszlopok számát és az állomás meglétét. Bármelyik eltér: nem adunk értéket,
és hibát jelzünk, ami a lapra és a GitHub Actions naplójába is kikerül.

A HTML MÉRETÉT nem figyeljük: az óránként változik, mert az adat változik.

Futtatás:  python shmu.py
"""

import json
import pathlib
import re
import sys
import urllib.request

URL = "https://www.shmu.sk/sk/?page=110"
FEJ = {"User-Agent": "equora-basin/2.6 (+https://basin.equora.institute)"}
PARAMS = pathlib.Path("params.json")
SZAMLALO = pathlib.Path("archiv/.shmu-hibak")

# Ennyi egymást követő sikertelen futás után a modul megbuktatja a workflow-t,
# hogy a GitHub értesítést küldjön. Egy-két hiba normális (az SHMÚ időnként
# nem válaszol); három egymás után már tartós baj.
TURESHATAR = 3

# A tábla elvárt szerkezete. Ha ez változik, az oldal átalakult.
VART_FEJLEC = ["Stanica - tok", "H", "∆H", "Q", "Tvo", "Tvz", "Z", "QM,N", "P", "L"]
ALLOMAS = "Ždaňa - Hornád"


def _szoveg(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


def beolvas():
    """(hozam m3/s, vizallas cm, vizho C) vagy kivétel, ha a szerkezet változott."""
    nyers = urllib.request.urlopen(
        urllib.request.Request(URL, headers=FEJ), timeout=45).read().decode("utf-8", "replace")

    sorok = re.findall(r"<tr[^>]*>(.*?)</tr>", nyers, re.S)
    if len(sorok) < 20:
        raise ValueError(f"Az SHMÚ tábla {len(sorok)} sort ad, várt legalább 20 — "
                         "az oldal szerkezete megváltozhatott.")

    # 1. A fejléc ellenőrzése
    fejlec = None
    for s in sorok[:4]:
        c = [_szoveg(x) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", s, re.S)]
        c = [x for x in c if x]
        if len(c) >= 8 and c[0].startswith("Stanica"):
            fejlec = c
            break
    if fejlec is None:
        raise ValueError("Az SHMÚ táblában nincs felismerhető fejléc "
                         "('Stanica - tok' kezdetű sor) — az oldal átalakult.")
    for i, vart in enumerate(VART_FEJLEC):
        if i >= len(fejlec) or fejlec[i] != vart:
            kapott = fejlec[i] if i < len(fejlec) else "(hiányzik)"
            raise ValueError(f"Az SHMÚ tábla {i+1}. oszlopa '{kapott}', "
                             f"várt '{vart}' — az oszlopsorrend megváltozott.")

    # 2. Az állomás keresése
    for s in sorok:
        c = [_szoveg(x) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", s, re.S)]
        c = [x for x in c if x]
        if not c or c[0] != ALLOMAS:
            continue
        if len(c) < 5:
            raise ValueError(f"A(z) {ALLOMAS} sor csak {len(c)} cellát ad, várt 5+.")
        try:
            vizallas = float(c[1].replace(",", "."))
            hozam = float(c[3].replace(",", "."))
            vizho = float(c[4].replace(",", ".")) if c[4] not in ("-", "//") else None
        except ValueError:
            raise ValueError(f"A(z) {ALLOMAS} sor számai nem olvashatók: {c[:5]}")
        # Fizikai ésszerűség: a Hernád határszelvénye 0,5 és 500 m³/s között jár.
        if not 0.1 <= hozam <= 500:
            raise ValueError(f"A(z) {ALLOMAS} hozama {hozam} m³/s — "
                             "a várt 0,1–500 tartományon kívül.")
        return hozam, vizallas, vizho

    raise ValueError(f"A(z) {ALLOMAS} állomás nincs a táblában — "
                     "megszűnt vagy átnevezték.")


def main():
    try:
        hozam, vizallas, vizho = beolvas()
    except Exception as e:
        sys.stderr.write(f"SHMÚ Hernád: {e}\n")
        p = json.loads(PARAMS.read_text(encoding="utf-8"))
        p["hernad_hatarszelveny"] = {
            "ertek": None,
            "hiba": str(e),
            "provenance": "hianyzik",
            "forras": "SHMÚ napi hidrológiai jelentés, Ždaňa – Hornád",
        }
        PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

        # A sorozatos hibák számlálása. Egy-két kimaradás nem baj, de ha az
        # oldal tartósan más, arról tudni kell — a 2-es kilépőkód megbuktatja
        # a workflow-t, és a GitHub értesítést küld.
        try:
            db = int(SZAMLALO.read_text(encoding="utf-8").strip()) if SZAMLALO.exists() else 0
        except ValueError:
            db = 0
        db += 1
        SZAMLALO.parent.mkdir(parents=True, exist_ok=True)
        SZAMLALO.write_text(str(db), encoding="utf-8")
        if db >= TURESHATAR:
            sys.stderr.write(
                f"\nA Hernád-szelvény {db} egymást követő futáson át nem olvasható.\n"
                f"Ez tartós hiba: az SHMÚ oldala ({URL}) valószínűleg átalakult.\n"
                "A modul szerkezet-ellenőrzése pontosan megmondja, mi tér el.\n")
            raise SystemExit(2)
        sys.stderr.write(f"({db}. sikertelen futás, {TURESHATAR}-nál jelzünk)\n")
        raise SystemExit(1)

    # Sikeres beolvasás: a hibaszámláló nullázódik.
    SZAMLALO.unlink(missing_ok=True)

    sys.stdout.write(f"Hernád (Ždaňa, SK): {hozam} m³/s · {vizallas} cm")
    sys.stdout.write(f" · {vizho} °C\n" if vizho is not None else "\n")

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["hernad_hatarszelveny"] = {
        "ertek": hozam,
        "vizallas_cm": vizallas,
        "vizho_c": vizho,
        "provenance": "helyszini",
        "forras": ("SHMÚ (Szlovák Hidrometeorológiai Intézet) napi hidrológiai "
                   "jelentés, Ždaňa – Hornád, az utolsó szlovák szelvény a határ előtt"),
        "megjegyzes": ("A Hernád a Sajóba torkollik, a magyar Sajópüspöki mérce "
                       "a torkolat fölött van — enélkül ez a hozam kimaradna "
                       "a bejövő oldalról."),
        "figyelmeztetes": ("HTML-táblából olvasva, nem API-ból. A modul minden "
                           "futáskor ellenőrzi a tábla szerkezetét; eltérés esetén "
                           "nem ad értéket."),
        "hivatkozas": URL,
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
