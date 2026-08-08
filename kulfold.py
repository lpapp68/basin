#!/usr/bin/env python3
"""
kulfold.py — a teljes Középső-Duna-medence doboz két fala, nyilvános forrásból.

Futtatás:  python kulfold.py

A DOBOZ
A medence hidrológiailag majdnem zárt: a Duna Dévénynél belép, a Vaskapunál kilép,
és a Tisza, a Dráva, a Száva meg a Morava vízgyűjtője teljes egészében belül marad.
A mérleghez ezért mindössze KÉT szelvény kell.

  belépő   Duna, Dévény (Devín)   — SHMÚ napi jelentés, táblázatos
  kilépő   Duna, Baziás (Baziaş)  — INHGA napi bulletin, prózában

Mindkettő nyilvános, regisztráció nélkül. Az adatkérő levelek ettől még kellenek:
a hivatalos, korrigált adatsorhoz és a felhasználási feltételek tisztázásához.

FIGYELEM
Mindkét forrás OPERATÍV adat: a SHMÚ kimondja, hogy korrekció nélküli
("Údaje majú operatívny charakter, neprešli korekciou"). Az INHGA hozama pedig
prózából származik, ezért törékeny — ha átfogalmazzák a mondatot, a minta elromlik.
Ezt a lap provenance-címkéje jelzi.

BAZIÁS HELYZETE
A Duna 1072. folyamkilométere, Romániába lépéskor — a Tisza, a Száva és a Velika
Morava torkolata UTÁN, a Vaskapu előtt. A doboz kifolyásának tehát jó közelítése.
"""

import datetime as dt
import json
import pathlib
import re
import urllib.request

SHMU = "https://www.shmu.sk/sk/?page=110"
INHGA = "https://www.hidro.ro/en/bulletin_type/buletin-hidrologic-zilnic/"
UA = "Mozilla/5.0 (compatible; equora-basin/2.2; +https://basin.equora.institute)"
PARAMS = pathlib.Path("params.json")

# A szlovák oldalról kiolvasott szelvények. A Dévény a doboz fala; a többi
# a Duna magyar szakasz előtti profilját adja, és ellenőrzésre való.
SK_SZELVENYEK = {
    "Devín - Dunaj":    ("Duna, Dévény", "fal_be"),
    "Medveďov - Dunaj": ("Duna, Medve", "profil"),
    "Komárno - Dunaj":  ("Duna, Komárom", "profil"),
    "Štúrovo - Dunaj":  ("Duna, Párkány", "profil"),
    "Salka - Ipeľ":     ("Ipoly, Ipolyszalka", "profil"),
}


def hoz(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def szam(x):
    x = (x or "").replace("\u00a0", "").replace(",", ".").strip()
    try:
        return float(x)
    except ValueError:
        return None


def shmu() -> dict:
    """Táblázat: Stanica | H [cm] | dH | Q [m3/s] | Tvo | Tvz | Z ..."""
    t = hoz(SHMU)
    ki = {}
    for sor in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [re.sub(r"<[^>]+>", "", x).replace("\u00a0", " ").strip()
             for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", sor, re.S)]
        if len(c) < 5 or c[0] not in SK_SZELVENYEK:
            continue
        nev, szerep = SK_SZELVENYEK[c[0]]
        ki[c[0]] = {"nev": nev, "szerep": szerep, "forras_nev": c[0],
                    "vizallas_cm": szam(c[1]), "hozam_m3s": szam(c[3]),
                    "vizho_c": szam(c[4])}
    return ki


def inhga() -> dict:
    """A napi bulletin prózájából: a baziási hozam m3/s-ban, a dátummal együtt."""
    t = hoz(INHGA)
    tiszta = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    # "Debitul la intrarea în ţară (secţiunea Baziaş) a fost ... la valoarea de 1400 m3/s"
    m = re.search(r"sec[țţ]iunea\s+Bazia[șş].{0,120}?valoarea de\s*([\d\s.,]+)\s*m3/s",
                  tiszta, re.I)
    if not m:
        raise RuntimeError("A baziási hozam mintája nem talált. A bulletin szövege "
                           "valószínűleg megváltozott — a kulfold.py mintáját frissíteni kell.")
    hozam = float(m.group(1).replace(" ", "").replace(",", "."))

    # a hozzá tartozó időszak: "în intervalul 06.08.2026, ora 07.00 – 07.08.2026"
    d = re.search(r"intervalul\s+\d{2}\.\d{2}\.\d{4},\s*ora\s*[\d.]+\s*[–-]\s*"
                  r"(\d{2})\.(\d{2})\.(\d{4})", tiszta)
    datum = f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None

    # sokéves havi átlag ugyanabból a mondatból, ha ott van
    a = re.search(r"media multianual[ăa] a lunii \w+\s*\(?\s*([\d\s.,]+)\s*m3/s", tiszta, re.I)
    atlag = float(a.group(1).replace(" ", "").replace(",", ".")) if a else None

    return {"nev": "Duna, Baziás", "szerep": "fal_ki", "hozam_m3s": hozam,
            "datum": datum, "sokeves_atlag_m3s": atlag}


def main():
    sk = shmu()
    ro = inhga()

    be = next((v for v in sk.values() if v["szerep"] == "fal_be"), None)
    if be is None or be["hozam_m3s"] is None:
        raise RuntimeError("A dévényi hozam hiányzik a SHMÚ táblázatból.")

    hozzafolyas = ro["hozam_m3s"] - be["hozam_m3s"]

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["mdb_falak"] = {
        "lekerve": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "datum": ro.get("datum"),
        "belepo": {"nev": be["nev"], "hozam_m3s": be["hozam_m3s"],
                   "vizallas_cm": be["vizallas_cm"], "vizho_c": be["vizho_c"],
                   "forras": "SHMÚ napi jelentés (shmu.sk), operatív, korrekció nélküli adat"},
        "kilepo": {"nev": ro["nev"], "hozam_m3s": ro["hozam_m3s"],
                   "sokeves_atlag_m3s": ro.get("sokeves_atlag_m3s"),
                   "forras": "INHGA napi hidrológiai bulletin (hidro.ro), prózából kinyerve"},
        "kulonbseg_m3s": round(hozzafolyas, 1),
        "duna_profil": [v for v in sk.values() if v["szerep"] == "profil"],
        "provenance": "mert",
        "kulonbseg_ertelmezes": ("A két határszelvény AZONOS NAPI adatának különbsége. Ez NEM napi medence-hozzáfolyás: a Baziásnál ma kilépő víz nem az, amelyik ma lépett be Dévénynél — az átfolyási idő a Duna e szakaszán jellemzően egy-két hét, és közben a medencén belüli tározás is változik. A medence tényleges hozzájárulása hosszabb időszak átlagából vagy hidrológiai késleltetéssel becsülhető."),
        "figyelmeztetes": ("Operatív, korrekció nélküli adatok. A baziási hozam a bulletin "
                           "SZÖVEGÉBŐL származik, ezért a minta törékeny. Baziás a Tisza, a "
                           "Száva és a Velika Morava torkolata után van, a Vaskapu előtt — "
                           "a doboz kifolyásának jó közelítése."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"A doboz falai ({ro.get('datum') or 'dátum ismeretlen'}):")
    print(f"  belépő  {be['nev']:<22}{be['hozam_m3s']:>8.1f} m³/s"
          f"   ({be['vizallas_cm']:.0f} cm, {be['vizho_c']:.1f} °C)")
    print(f"  kilépő  {ro['nev']:<22}{ro['hozam_m3s']:>8.1f} m³/s")
    print(f"  a két szelvény különbsége:   {hozzafolyas:>8.1f} m³/s")
    if ro.get("sokeves_atlag_m3s"):
        arany = ro["hozam_m3s"] / ro["sokeves_atlag_m3s"] * 100
        print(f"  a kilépő hozam a sokéves havi átlag {arany:.0f}%-a "
              f"({ro['sokeves_atlag_m3s']:.0f} m³/s)")
    print("\n  Duna-profil a magyar szakasz előtt:")
    for v in sk.values():
        if v["szerep"] == "profil" and v["hozam_m3s"]:
            print(f"    {v['nev']:<22}{v['hozam_m3s']:>8.1f} m³/s")


if __name__ == "__main__":
    main()
