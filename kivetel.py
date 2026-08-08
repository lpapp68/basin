#!/usr/bin/env python3
"""
kivetel.py — a vízkivétel napi értéke éves statisztikából, szezonális profillal.

Futtatás:  python kivetel.py [YYYY-MM-DD]

MIÉRT NEM ELÉG AZ ÉVES SZÁM
Az éves mennyiséget elosztani 31,5 millió másodperccel hamis eredményt ad. Az öntözés
kb. száz nap alatt történik, nem egyenletesen egész évben — az éves átlagból számolt
m³/s a nyári csúcsot többszörösen alábecsüli. A mérleg viszont NAPI, tehát havi profil kell.

MI MÉRT, ÉS MI FELTÉTELEZÉS
  MÉRT (hivatkozott statisztika): az éves mennyiségek.
  FELTÉTELEZÉS (az enyém): a havi eloszlás és a fogyasztó hányad.
Mindkettő itt, a fájl tetején szerkeszthető, és a params.json-be is bekerül,
hogy a lapon látszódjon, mi min alapul.

A FOGYASZTÓ HÁNYAD
Nem minden kivett víz vész el. Az ipari hűtővíz szinte teljesen visszatér, az
öntözővíz szinte egyáltalán nem. A mérlegbe csak a fogyasztó rész számít.
"""

import calendar
import datetime as dt
import json
import pathlib
import sys

PARAMS = pathlib.Path("params.json")

# ── Éves mennyiségek. Ezek hivatkozott statisztikák. ──────────────────────────
# profil: havi súlyok januártól decemberig, összegük 1.
# fogyaszto_hanyad: mennyi NEM tér vissza a rendszerbe (0 = teljesen visszatér).

TETELEK = [
    {
        "nev": "Mezőgazdasági öntözés",
        "eves_millio_m3": 154.0,
        "forras": "ÁSZ-jelentés a Nemzeti Vízstratégia végrehajtásáról, 2019–2023 átlag: "
                  "a mezőgazdasági vízhasználat 30%-a, 154 millió m³. A KSH kimondja, hogy "
                  "ebből kimaradnak az engedély nélküli vízkivételek, amelyeket "
                  "tanulmányok a bejelentett mennyiség duplájára becsülnek.",
        "profil": [0, 0, 0, 0.03, 0.12, 0.22, 0.28, 0.24, 0.09, 0.02, 0, 0],
        "profil_indok": "Tenyészidőszak, július–augusztusi csúccsal. FELTÉTELEZÉS.",
        "fogyaszto_hanyad": 0.90,
        "fogyaszto_indok": "A kijuttatott víz túlnyomó része elpárolog vagy a növény "
                           "elpárologtatja. FELTÉTELEZÉS.",
    },
    {
        "nev": "Halastavak",
        "eves_millio_m3": 356.0,
        "forras": "ÁSZ-jelentés, 2019–2023 átlag: a mezőgazdasági vízhasználat (510 millió m³) "
                  "kb. 70%-a. Ez bruttó szolgáltatott víz: egy része leeresztéskor visszatér a vízrendszerbe, más része talajvizet táplál.",
        "profil": [0, 0, 0.02, 0.08, 0.13, 0.16, 0.18, 0.17, 0.13, 0.08, 0.03, 0.02],
        "profil_indok": "Feltöltés tavasszal, párolgáspótlás nyáron. FELTÉTELEZÉS.",
        "fogyaszto_hanyad": 0.70,
        "fogyaszto_indok": "Szabad vízfelszín párolgása és elszivárgás. FELTÉTELEZÉS.",
    },
    {
        "nev": "Lakossági ivóvíz",
        "eves_m3_fo": 38.7,
        "lakossag": 9_500_000,
        "forras": "KSH: egy főre jutó éves lakossági közüzemi vízfogyasztás 38,7 m³ "
                  "(2022); 2024-ben kb. 105 liter/fő/nap.",
        "profil": [0.077, 0.072, 0.078, 0.081, 0.086, 0.090, 0.095, 0.094,
                   0.085, 0.081, 0.078, 0.083],
        "profil_indok": "Enyhe nyári csúcs a locsolás miatt. FELTÉTELEZÉS.",
        "fogyaszto_hanyad": 0.25,
        "fogyaszto_indok": "A nagy része csatornán, tisztítva visszatér; a nyári "
                           "locsolóvíz nem. FELTÉTELEZÉS.",
    },
    {
        "nev": "Ipar (erőművi hűtés nélkül)",
        "eves_millio_m3": 290.0,
        "forras": "SZÁRMAZTATOTT: a GKI szerinti 1 160 millió m³ teljes nettó "
                  "vízkivételből (erőművek nélkül) levonva a fenti tételeket. "
                  "ELLENŐRIZENDŐ a VGT3 ágazati bontásából.",
        "profil": [0.0833] * 12,
        "profil_indok": "Egyenletes éves eloszlás. FELTÉTELEZÉS.",
        "fogyaszto_hanyad": 0.15,
        "fogyaszto_indok": "Az átfolyó hűtés visszatér, a technológiai víz nem. "
                           "FELTÉTELEZÉS.",
    },
]


def kert_nap() -> dt.date:
    if len(sys.argv) > 1:
        return dt.date.fromisoformat(sys.argv[1])
    return dt.date.today() - dt.timedelta(days=1)


def main():
    nap = kert_nap()
    ho = nap.month
    napok = calendar.monthrange(nap.year, ho)[1]
    mp = napok * 86400.0

    ki, ossz, ossz_fogy = [], 0.0, 0.0
    for t in TETELEK:
        eves_m3 = (t["eves_millio_m3"] * 1e6 if "eves_millio_m3" in t
                   else t["eves_m3_fo"] * t["lakossag"])
        m3s = eves_m3 * t["profil"][ho - 1] / mp
        fogy = m3s * t["fogyaszto_hanyad"]
        ossz += m3s
        ossz_fogy += fogy
        ki.append({
            "nev": t["nev"],
            "ertek": round(m3s, 1),
            "fogyaszto_m3s": round(fogy, 1),
            "fogyaszto": t["fogyaszto_hanyad"] >= 0.5,
            "fogyaszto_hanyad": t["fogyaszto_hanyad"],
            "eves_millio_m3": round(eves_m3 / 1e6, 1),
            "provenance": "modellezett",
            "megjegyzes": (f"Éves {eves_m3/1e6:.0f} millió m³, ebből "
                           f"{t['profil'][ho-1]*100:.0f}% esik erre a hónapra; "
                           f"a kivett vízből {t['fogyaszto_hanyad']*100:.0f}% nem tér vissza közvetlenül a magyar vízrendszerbe a vizsgált időszakon belül. "
                           f"{t['forras']}"),
        })

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["kivetel_m3s"] = ki
    p["kivetel_modell"] = {
        "datum": nap.isoformat(),
        "honap": ho,
        "osszes_m3s": round(ossz, 1),
        "fogyaszto_m3s": round(ossz_fogy, 1),
        "provenance": "modellezett",
        "modszer": ("Éves statisztikai mennyiség × havi profil ÷ a hónap másodpercei, "
                    "majd fogyasztó hányaddal szorozva."),
        "figyelmeztetes": ("Az éves mennyiségek hivatkozott statisztikák, a HAVI ELOSZLÁS "
                           "és a FOGYASZTÓ HÁNYAD viszont feltételezés. A pontos adatot a "
                           "vízkészletjárulék-bevallások és a VGT3 ágazati bontása adná — "
                           "ezek az OVF-nél kérhetők."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{nap}  ({ho}. hónap, {napok} nap)")
    for k in ki:
        print(f"  {k['nev']:<30}{k['ertek']:>7.1f} m3/s   ebbol fogyaszto {k['fogyaszto_m3s']:>6.1f}")
    print(f"  {'OSSZESEN':<30}{ossz:>7.1f} m3/s   ebbol fogyaszto {ossz_fogy:>6.1f}")


if __name__ == "__main__":
    main()
