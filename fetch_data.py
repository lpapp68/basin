#!/usr/bin/env python3
"""
basin.equora.institute — v2 adatgyűjtő

VÁLTOZÁS a v1-hez képest:
Az OVF mércénkénti óras idősora NEM csak vízállást ad, hanem VÍZHOZAMOT (m3/s) és
VÍZHŐFOKOT is. A v1-ben tévesen azt írtam, hogy a hozam nem publikus és GloFAS kell
hozzá — nem kell. A mérleg folyó-tagjai innentől mérések, nem modell.

Paks csomópont: minket a víz érdekel. A blokkteljesítmény csak azért szerepel, mert
ez mondja meg, mennyi hűtővizet vesznek ki — semmi más energiaadatot nem tárolunk.

Forrás:
  OVF Országos Vízjelző Szolgálat, vizugy.hu — vízállás, vízhozam, vízhő (óras)
  holadelej.hu /api/data (CC BY 4.0) — paksi blokkteljesítmény, kizárólag üzemállapotnak
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

import archivum

UA = "Mozilla/5.0 (compatible; equora-basin/2.0; +https://basin.equora.institute)"
ALLOMAS = "https://www.vizugy.hu/?mapModule=OpGrafikon&AllomasVOA={voa}&mapData=OrasIdosor"
DELEJ = "https://holadelej.hu/api/data"

# Két doboz. Az AKTÍV az, amelyikhez ma mért falaink vannak.
DOBOZOK = {
    "hu": {
        "nev": "Magyarország",
        "terulet_km2": 93030,
        "allapot": "aktív",
        "falak": "11 belépő + 3 kilépő magyar mérce, mind mért óras vízhozammal",
        "megjegyzes": "Nem a medence, hanem a medence magyar szelete. Ezt tudjuk MA mérni.",
    },
    "mdb": {
        "nev": "Középső-Duna-medence",
        "terulet_km2": 445900,
        "terulet_szamitas": "Vaskapu I. vízgyűjtője 577 250 km² mínusz a Duna dévényi vízgyűjtője ~131 350 km²",
        "terulet_provenance": "helyorzo",
        "allapot": "tervezett",
        "falak": "KÉT szelvény elég: Duna Dévénynél (be) és Duna a Vaskapunál / Orsovánál (ki). "
                 "A Tisza, a Dráva, a Száva és a Morava vízgyűjtője teljes egészében a dobozon BELÜL van.",
        "megjegyzes": "Ehhez szlovák (SHMÚ) és román (INHGA) hozamadat kell — lásd SETUP.md.",
    },
}
AKTIV_DOBOZ = "hu"
BOX = DOBOZOK[AKTIV_DOBOZ]

# nev, VOA, folyo, szerep, jegyzet
MERCEK = [
    # ── Duna ────────────────────────────────────────────────────────────
    ("Nagybajcs",     "16495FDB-97AB-11D4-BB62-00508BA24287", "Duna",  "belepo",  "Ausztria / Szlovákia felől"),
    ("Komárom",       "16495FDD-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", ""),
    ("Budapest",      "16496059-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", ""),
    ("Dunaújváros",   "164960A9-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", ""),
    ("Paks",          "16496188-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "hűtővízkivétel"),
    ("Baja",          "164960C2-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", ""),
    ("Mohács",        "16496283-97AB-11D4-BB62-00508BA24287", "Duna",  "kilepo",  "a doboz fő kifolyása"),
    # ── Duna bal parti mellékfolyói ─────────────────────────────────────
    ("Ipolytarnóc",   "16496066-97AB-11D4-BB62-00508BA24287", "Ipoly", "belepo",  "Szlovákia felől"),
    # ── Dráva ───────────────────────────────────────────────────────────
    ("Őrtilos",       "16496285-97AB-11D4-BB62-00508BA24287", "Dráva", "belepo",  "Horvátország felől, a Mura után"),
    ("Barcs",         "16496287-97AB-11D4-BB62-00508BA24287", "Dráva", "atfolyo", ""),
    ("Drávaszabolcs", "16496288-97AB-11D4-BB62-00508BA24287", "Dráva", "kilepo",  "a Dráva a dobozon kívül torkollik a Dunába"),
    # ── Rába ────────────────────────────────────────────────────────────
    ("Szentgotthárd", "164962E8-97AB-11D4-BB62-00508BA24287", "Rába",  "belepo",  "Ausztria felől"),
    # ── Tisza és mellékfolyói ───────────────────────────────────────────
    ("Tiszabecs",     "16496327-97AB-11D4-BB62-00508BA24287", "Tisza", "belepo",  "Ukrajna felől"),
    ("Záhony",        "1649632B-97AB-11D4-BB62-00508BA24287", "Tisza", "atfolyo", ""),
    ("Szolnok",       "73F7E1F4-985C-11D4-BB62-00508BA24287", "Tisza", "atfolyo", ""),
    ("Szeged",        "73F7E264-985C-11D4-BB62-00508BA24287", "Tisza", "kilepo",  "kilépés közeli, nem a határszelvény"),
    ("Csenger",       "1649632F-97AB-11D4-BB62-00508BA24287", "Szamos", "belepo", "Románia felől"),
    ("Felsőberecki",  "16496498-97AB-11D4-BB62-00508BA24287", "Bodrog", "belepo", "Szlovákia / Ukrajna felől"),
    ("Sajópüspöki",   "1649649A-97AB-11D4-BB62-00508BA24287", "Sajó",  "belepo",  "Szlovákia felől"),
    ("Makó",          "73F7E266-985C-11D4-BB62-00508BA24287", "Maros", "belepo",  "Románia felől"),
    ("Körösszakál",   "73F7E29A-985C-11D4-BB62-00508BA24287", "Sebes-Körös", "belepo", "Románia felől"),
    ("Gyula",         "73F7E2A5-985C-11D4-BB62-00508BA24287", "Fehér-Körös", "belepo", "Románia felől"),
]

# Amit a doboz falai NEM fognak be. Ezek a hiányok a maradéktagban jelennek meg.
NYITOTT_FALAK = [
    "Hernád (Szlovákia felől) — nincs bekötve",
    "Kraszna, Fekete-Körös, Berettyó (Románia felől) — nincs bekötve",
    "Mura külön szelvényben — az őrtilosi hozam már tartalmazza",
    "Belső hozzáfolyás (Sió, Zagyva, Kettős-Körös stb.) — nem mérjük külön",
]

# Hőterhelési korlát: a melegvíz-csatorna torkolatától 500 m-re a Duna nem lehet
# 30 C-nál melegebb. Ez a vízoldali második fal a vízszint mellett.
HOKORLAT_C = 30.0


def get(url: str, timeout=35) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def sz(s):
    s = (s or "").replace("\u00a0", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_allomas(html: str):
    """Metaadat + óras idősor egy mérce adatlapjáról."""
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    meta = {}
    m = re.search(r"Vízmérce név:\s*(.{0,40}?)\s+Törzsszám:\s*(\d+)", plain)
    if m:
        meta["nev_forras"], meta["torzsszam"] = m.group(1).strip(), m.group(2)
    for kulcs, minta in [
        ("nullpont_mBf", r"Vízmérce nullpont:\s*(-?[\d.]+)"),
        ("lkv_cm",       r"Legkisebb vízállás \(LKV\):\s*(-?\d+)"),
        ("lnv_cm",       r"Legnagyobb vízállás \(LNV\):\s*(-?\d+)"),
        ("keszultseg_i", r"I\. készültségi szint:\s*(-?\d+)"),
    ]:
        mm = re.search(minta, plain)
        if mm:
            meta[kulcs] = sz(mm.group(1))

    sorok = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        c = [re.sub(r"<[^>]+>", "", x).replace("\u00a0", "").strip()
             for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if len(c) >= 5 and re.match(r"\d{4}\.\d{2}\.\d{2}\.", c[0]):
            sorok.append({"t": c[0], "cm": sz(c[1]), "q": sz(c[2]),
                          "t_felszin": sz(c[3]), "t_fenek": sz(c[4])})
    sorok.sort(key=lambda x: x["t"])
    return meta, sorok


def utolso(sorok, mezo):
    for s in reversed(sorok):
        if s.get(mezo) is not None:
            return s[mezo], s["t"]
    return None, None


def paks_uzem():
    """Csak az üzemallapot, hogy a hűtővízkivétel ne konstans legyen.
       Semmilyen egyéb energiaadatot nem veszünk át."""
    try:
        d = json.loads(get(DELEJ, timeout=25))
        mw = d.get("paksUnits", {}).get("sum")
        if mw is None:
            mw = d.get("plants", {}).get("paks")
        return {"mw": round(float(mw), 1), "forras": "holadelej.hu /api/data (CC BY 4.0)", "hiba": None}
    except Exception as e:
        return {"mw": None, "forras": "holadelej.hu /api/data (CC BY 4.0)", "hiba": str(e)}


def hutoviz(mw, p):
    """A hűtővízkivétel a hőteljesítménnyel skálázódik.
       Névleges üzemben ~100 m3/s; leállított blokkok fenntartó hűtése ~100 m3/perc."""
    h = p["paks_hutoviz"]
    if mw is None:
        return {"ertek": None, "allapot": "ismeretlen", "provenance": "helyorzo",
                "forras": "a blokkteljesítmény nem elérhető"}
    arany = max(0.0, min(1.0, mw / h["nevleges_mw"]))
    termeles = h["nevleges_m3s"] * arany
    fenntarto = h["fenntarto_m3perc"] / 60.0
    return {
        "ertek": round(termeles + fenntarto, 1),
        "termelesi_resz": round(termeles, 1),
        "fenntarto_resz": round(fenntarto, 2),
        "arany": round(arany, 3),
        "mw": mw,
        "allapot": "termel" if arany > 0.02 else "leállítva, fenntartó hűtés",
        "provenance": "modellezett",
        "forras": f"{mw} MW / {h['nevleges_mw']} MW arányában — {h['forras']}",
    }


def meta_of(d):
    return {"provenance": d["provenance"], "forras": d["forras"], "kor_ora": d.get("kor_ora")}


def main():
    p = json.load(open("params.json", encoding="utf-8"))
    mercek, hibak = [], []

    for nev, voa, folyo, szerep, jegyzet in MERCEK:
        try:
            meta, sorok = parse_allomas(get(ALLOMAS.format(voa=voa)))
        except Exception as e:
            hibak.append(f"{nev}: lekérés sikertelen ({e})")
            continue
        if meta.get("nev_forras") and nev.lower() not in meta["nev_forras"].lower():
            hibak.append(f"{nev}: az adatlap „{meta['nev_forras']}” nevet mutat — VOA ellenőrizendő")
        cm, t_cm = utolso(sorok, "cm")
        q, t_q = utolso(sorok, "q")
        tv, _ = utolso(sorok, "t_fenek")
        if tv is None:
            tv, _ = utolso(sorok, "t_felszin")
        lkv, lnv = meta.get("lkv_cm"), meta.get("lnv_cm")
        mercek.append({
            "nev": nev, "folyo": folyo, "szerep": szerep, "jegyzet": jegyzet,
            "torzsszam": meta.get("torzsszam"), "nullpont_mBf": meta.get("nullpont_mBf"),
            "utolso_cm": cm, "utolso_ido": t_cm,
            "hozam_m3s": q, "hozam_ido": t_q, "vizho_c": tv,
            "lkv_cm": lkv, "lnv_cm": lnv,
            "lkv_folott_cm": (cm - lkv) if (cm is not None and lkv is not None) else None,
            "rekord_alatt": (cm is not None and lkv is not None and cm < lkv),
            "savon": round((cm - lkv) / (lnv - lkv), 4)
                     if None not in (cm, lkv, lnv) and lnv > lkv else None,
            "sorozat_cm": [s["cm"] for s in sorok[-48:]],
            "valtozas_24h_cm": (sorok[-1]["cm"] - sorok[-25]["cm"])
                               if len(sorok) >= 25 and sorok[-1]["cm"] is not None
                               and sorok[-25]["cm"] is not None else None,
            "provenance": "mert",
        })

    if not mercek:
        print("HIBA: egyetlen mércét sem sikerült beolvasni.", file=sys.stderr)
        sys.exit(1)

    terulet_m2 = BOX["terulet_km2"] * 1e6
    nap = 86400.0
    def mmps(mm_):  return mm_ / 1000.0 * terulet_m2 / nap
    def mm(m3s):    return round(m3s * nap / terulet_m2 * 1000.0, 2)

    be = [m for m in mercek if m["szerep"] == "belepo" and m["hozam_m3s"] is not None]
    ki = [m for m in mercek if m["szerep"] == "kilepo" and m["hozam_m3s"] is not None]
    Q_be = sum(m["hozam_m3s"] for m in be)
    Q_ki = sum(m["hozam_m3s"] for m in ki)

    P = mmps(p["csapadek_mm_nap"]["ertek"])
    ET = mmps(p["parolgas_mm_nap"]["ertek"])

    # Egy mérleg tagjai nem jöhetnek különböző napokról. Ha mégis, ki kell mondani.
    d_csap = p["csapadek_mm_nap"].get("datum")
    d_par = p["parolgas_mm_nap"].get("datum")
    if d_csap and d_par and d_csap != d_par:
        hibak.append(f"DÁTUMELTÉRÉS: a csapadék {d_csap}-i, a párolgás {d_par}-i. "
                     f"A mérleg így nem egyetlen napra vonatkozik. "
                     f"Futtasd mindkettőt ugyanarra a dátumra.")
    merleg_napja = d_csap or d_par or p.get("_ervenyes")

    uzem = paks_uzem()
    if uzem["hiba"]:
        hibak.append(f"Paks üzemállapot: {uzem['hiba']}")
    paks_hv = hutoviz(uzem["mw"], p)

    kivetel = [dict(k, provenance="helyorzo") for k in p["kivetel_m3s"]]
    kivetel.append({
        "nev": "Paks hűtővíz", "ertek": paks_hv["ertek"], "fogyaszto": False,
        "provenance": paks_hv["provenance"],
        "megjegyzes": f"{paks_hv['allapot']} — felmelegítve visszatér. {paks_hv['forras']}",
    })
    fogyaszto = sum(k["ertek"] for k in kivetel if k["fogyaszto"] and k["ertek"])
    # Előjel-konvenció: ami a dobozba kerül, POZITÍV; ami elhagyja, NEGATÍV.
    # Az öt tag így összeadva adja ki a készletváltozást.
    be_P, be_Q = P, Q_be
    ki_ET, ki_Q, ki_fogy = -ET, -Q_ki, -fogyaszto
    dS = be_P + be_Q + ki_ET + ki_Q + ki_fogy
    ET_maradek = P + Q_be - Q_ki - p["keszletvaltozas_m3s"]["ertek"] - fogyaszto

    paks = next((m for m in mercek if m["nev"] == "Paks"), None)
    paks_csomopont = None
    if paks:
        paks_csomopont = {
            "vizallas_cm": paks["utolso_cm"], "lkv_cm": paks["lkv_cm"],
            "lkv_alatt_cm": -paks["lkv_folott_cm"] if paks["lkv_folott_cm"] is not None else None,
            "hozam_m3s": paks["hozam_m3s"], "vizho_c": paks["vizho_c"],
            "hokorlat_c": HOKORLAT_C,
            "hokorlat_tartalek_c": round(HOKORLAT_C - paks["vizho_c"], 1) if paks["vizho_c"] is not None else None,
            "hutoviz": paks_hv,
            "hutoviz_a_folyo_szazalekaban": round(paks_hv["ertek"] / paks["hozam_m3s"] * 100, 2)
                if paks_hv["ertek"] and paks["hozam_m3s"] else None,
            "ido": paks["utolso_ido"],
        }

    out = {
        "generalva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "doboz": BOX, "dobozok": DOBOZOK, "aktiv_doboz": AKTIV_DOBOZ,
        "orak": {
            "oras": {"cimke": "vízállás · hozam · vízhő", "forras": "OVF / vizugy.hu",
                     "utolso": mercek[0]["utolso_ido"]},
            "napi": {"cimke": "csapadék · párolgás",
                     "forras": (f"csapadék {d_csap or '?'} · párolgás {d_par or '?'}"
                                if d_csap != d_par else p["_forrasok"]["napi"]),
                     "utolso": merleg_napja},
            "havi": {"cimke": "készletváltozás", "forras": p["_forrasok"]["havi"],
                     "utolso": p["_ervenyes_havi"]},
        },
        "mercek": mercek,
        "paks": paks_csomopont,
        "mm_nap": {"csapadek": mm(be_P), "hozam_be": mm(be_Q), "parolgas": mm(ki_ET),
                   "hozam_ki": mm(ki_Q), "keszletvaltozas": mm(dS)},
        "elojel": "Ami a dobozba kerül: pozitív. Ami elhagyja: negatív. Az öt tag összege a készletváltozás.",
        "merleg_m3s": {
            "csapadek": {"ertek": round(be_P), **meta_of(p["csapadek_mm_nap"])},
            "hozam_be": {"ertek": round(be_Q), "provenance": "mert", "kor_ora": 1,
                         "forras": "OVF óras vízhozam: " + ", ".join(m["nev"] for m in be)},
            "parolgas": {"ertek": round(ki_ET), **meta_of(p["parolgas_mm_nap"])},
            "hozam_ki": {"ertek": round(ki_Q), "provenance": "mert", "kor_ora": 1,
                         "forras": "OVF óras vízhozam: " + ", ".join(m["nev"] for m in ki)},
            "keszletvaltozas": {"ertek": round(dS), "provenance": "modellezett", "kor_ora": None,
                                "forras": "maradéktag a fenti tételekből"},
        },
        "hova_lett_m3s": {
            "parolgas_muhold": {"ertek": round(ET), **meta_of(p["parolgas_mm_nap"])},
            "parolgas_maradek": {"ertek": round(ET_maradek), "provenance": "modellezett",
                                 "kor_ora": None,
                                 "forras": "P + Q_be − Q_ki − ΔS − fogyasztó kivétel"},
            "elteres": {"ertek": round(ET_maradek - ET), "provenance": "modellezett",
                        "kor_ora": None, "forras": "a két becslés különbsége"},
        },
        "kivetel_m3s": kivetel,
        "egyenleg": p["egyenleg"],
        "figyelmeztetes": p["_figyelmeztetes"],
        "nyitott_falak": NYITOTT_FALAK,
        "hibak": hibak,
    }

    # Saját idősor: minden futás rögzül, a napi sorozat újraszámolódik.
    try:
        archivum.rogzit(out)
        napok = archivum.napi_osszegzes(p)
        out["archivum"] = archivum.kumulalt(napok, BOX["terulet_km2"])
        out["archivum"]["napok"] = napok[-30:]
    except Exception as e:
        hibak.append(f"Archívum: {e}")

    json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.BASIN_DATA = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    hoz = [m["nev"] for m in mercek if m["hozam_m3s"] is not None]
    rek = [m["nev"] for m in mercek if m["rekord_alatt"]]
    print(f"kész — {len(mercek)} mérce, ebből {len(hoz)} ad vízhozamot")
    print(f"  Q_be={Q_be:.0f}  Q_ki={Q_ki:.0f} m³/s (mért)")
    if paks_csomopont:
        pc = paks_csomopont
        print(f"  Paks: {pc['vizallas_cm']} cm ({pc['lkv_alatt_cm']} cm az LKV alatt), "
              f"{pc['hozam_m3s']} m³/s, {pc['vizho_c']} °C "
              f"(tartalék {pc['hokorlat_tartalek_c']} °C), "
              f"hűtővíz {paks_hv['ertek']} m³/s — {paks_hv['allapot']}")
    if rek:
        print(f"  LKV alatt: {', '.join(rek)}")
    a = out.get("archivum") or {}
    if a.get("allapot") == "mert":
        print(f"  archívum: {a['teljes_napok']} teljes nap "
              f"({a['kezdet']} – {a['veg']}), kumulált {a['kumulalt_km3']:+.3f} km³")
    elif a:
        print(f"  archívum: {a.get('osszes_nap', 0)} nap rögzítve, "
              f"teljes nap még nincs — {a.get('megjegyzes','')}")
    for h in hibak:
        print(f"  FIGYELEM: {h}", file=sys.stderr)


if __name__ == "__main__":
    main()
