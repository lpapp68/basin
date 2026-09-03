#!/usr/bin/env python3
"""
basin.equora.institute — v2 adatgyűjtő

VÁLTOZÁS a v1-hez képest:
Az OVF mércénkénti órás idősora NEM csak vízállást ad, hanem VÍZHOZAMOT (m3/s) és
VÍZHŐFOKOT is. A v1-ben tévesen azt írtam, hogy a hozam nem publikus és GloFAS kell
hozzá — nem kell. A mérleg folyó-tagjai innentől mérések, nem modell.

Paks csomópont: minket a víz érdekel. A blokkteljesítmény csak azért szerepel, mert
ez mondja meg, mennyi hűtővizet vesznek ki — semmi más energiaadatot nem tárolunk.

Forrás:
  OVF Országos Vízjelző Szolgálat, vizugy.hu — vízállás, vízhozam, vízhő (órás)
  holadelej.hu /api/data (CC BY 4.0) — paksi blokkteljesítmény, kizárólag üzemállapotnak
"""

import datetime as dt
import json
import os
import time
import ssl
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

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
        "falak": "11 belépő + 3 kilépő magyar mérce, órás vízhozammal. Nyitott falak: a Hernád, a Kraszna, a Fekete-Körös, a Berettyó, és a határon átnyúló felszín alatti vízáramlás - ezek a maradéktagban jelennek meg",
        "megjegyzes": "Nem a medence, hanem a medence magyar szelete. Ezt tudjuk MA mérni.",
    },
    "mdb": {
        "nev": "Középső-Duna-medence",
        "terulet_km2": 445900,
        "terulet_szamitas": "Vaskapu I. vízgyűjtője 577 250 km² mínusz a Duna dévényi vízgyűjtője ~131 350 km²",
        "terulet_provenance": "helyorzo",
        "allapot": "falak bekötve, a doboz még nem aktív",
        "falak": "A falai megvannak: a Duna Dévénynél lép be (SHMÚ) és Baziásnál lép ki (INHGA), "
                 "a Tisza, a Száva és a Morava torkolata után. Mindkét adat nyilvános, napi frissítéssel. "
                 "A Tisza, a Dráva, a Száva és a Morava vízgyűjtője teljes egészében a dobozon belül van.",
        "megjegyzes": "A váltáshoz két dolog hiányzik: a csapadék és a párolgás maszkja "
                      "vízgyűjtő-poligonra cserélendő, és a mérleg üteme napira lassul.",
    },
}
AKTIV_DOBOZ = "hu"
BOX = DOBOZOK[AKTIV_DOBOZ]

# nev, VOA, folyo, szerep, jegyzet, torzsszam
# A VOA a regi HTML-felulet azonositoja; a torzsszam az OVF hivatalos
# API-jae (data.vizugy.hu). A VOA-t tartaleknak megtartjuk.
MERCEK = [
    # ── Duna ────────────────────────────────────────────────────────────
    ("Nagybajcs",     "16495FDB-97AB-11D4-BB62-00508BA24287", "Duna",  "belepo",  "Ausztria / Szlovákia felől", 3),
    ("Komárom",       "16495FDD-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "", 5),
    ("Budapest",      "16496059-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "", 1026),
    ("Dunaújváros",   "164960A9-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "", 547),
    ("Paks",          "16496188-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "hűtővízkivétel", 549),
    ("Baja",          "164960C2-97AB-11D4-BB62-00508BA24287", "Duna",  "atfolyo", "", 1344),
    ("Mohács",        "16496283-97AB-11D4-BB62-00508BA24287", "Duna",  "kilepo",  "a doboz fő kifolyása", 831),
    # ── Duna bal parti mellékfolyói ─────────────────────────────────────
    ("Ipolytarnóc",   "16496066-97AB-11D4-BB62-00508BA24287", "Ipoly", "belepo",  "Szlovákia felől", 1040),
    # ── Dráva ───────────────────────────────────────────────────────────
    ("Őrtilos",       "16496285-97AB-11D4-BB62-00508BA24287", "Dráva", "belepo",  "Horvátország felől, a Mura után", 833),
    ("Barcs",         "16496287-97AB-11D4-BB62-00508BA24287", "Dráva", "atfolyo", "", 835),
    ("Drávaszabolcs", "16496288-97AB-11D4-BB62-00508BA24287", "Dráva", "kilepo",  "a Dráva a dobozon kívül torkollik a Dunába", 836),
    # ── Rába ────────────────────────────────────────────────────────────
    ("Szentgotthárd", "164962E8-97AB-11D4-BB62-00508BA24287", "Rába",  "belepo",  "Ausztria felől", 342),
    # ── Tisza és mellékfolyói ───────────────────────────────────────────
    ("Tiszabecs",     "16496327-97AB-11D4-BB62-00508BA24287", "Tisza", "belepo",  "Ukrajna felől", None),
    ("Záhony",        "1649632B-97AB-11D4-BB62-00508BA24287", "Tisza", "atfolyo", "", 1518),
    ("Szolnok",       "73F7E1F4-985C-11D4-BB62-00508BA24287", "Tisza", "atfolyo", "", 2046),
    ("Szeged",        "73F7E264-985C-11D4-BB62-00508BA24287", "Tisza", "kilepo",  "kilépés közeli, nem a határszelvény", 2275),
    ("Csenger",       "1649632F-97AB-11D4-BB62-00508BA24287", "Szamos", "belepo", "Románia felől", 1523),
    ("Felsőberecki",  "16496498-97AB-11D4-BB62-00508BA24287", "Bodrog", "belepo", "Szlovákia / Ukrajna felől", 1724),
    ("Sajópüspöki",   "1649649A-97AB-11D4-BB62-00508BA24287", "Sajó",  "belepo",  "Szlovákia felől", 1726),
    ("Makó",          "73F7E266-985C-11D4-BB62-00508BA24287", "Maros", "belepo",  "Románia felől", 2278),
    ("Körösszakál",   "73F7E29A-985C-11D4-BB62-00508BA24287", "Sebes-Körös", "belepo", "Románia felől", 2736),
    ("Gyula",         "73F7E2A5-985C-11D4-BB62-00508BA24287", "Fehér-Körös", "belepo", "Románia felől", 2747),
]

# Amit a doboz falai NEM fognak be. Ezek a hiányok a maradéktagban jelennek meg.
# Nyitott fal = a doboz HATÁRÁN átlépő víz, amit nem mérünk. A belső vízfolyások
# nem tartoznak ide: azok a kontrolltérfogaton belül mozgatják a vizet, tehát a
# mérleget nem nyitják meg.
NYITOTT_FALAK = [
    "Hernád (Szlovákia felől) — nincs bekötve",
    "Kraszna, Fekete-Körös, Berettyó (Románia felől) — nincs bekötve",
    "Határon átnyúló felszín alatti vízáramlás — egyáltalán nem mérjük",
    "Mura külön szelvényben — az őrtilosi hozam már tartalmazza",
]
BELSO_MEGJEGYZES = ("Belső vízfolyások (Sió, Zagyva, Kettős-Körös és a többi): ezeket "
                    "külön nem bontjuk, mert a magyarországi kontrolltérfogaton belül "
                    "mozgatják a vizet — a mérleget nem nyitják meg.")

# Hőterhelési korlát: a melegvíz-csatorna torkolatától 500 m-re a Duna nem lehet
# 30 C-nál melegebb. Ez a vízoldali második fal a vízszint mellett.
HOKORLAT_C = 30.0




# ── SSL-kontextus ────────────────────────────────────────────────────────
# Néhány OVF-mérce (Tiszabecs) hiányos tanúsítványláncot ad: a köztes
# tanúsítvány nincs a válaszban, ezért a rendszer gyökérkészletével nem
# hitelesíthető. A certifi naprakész készlete a legtöbb ilyen esetet megoldja.
def _ssl_kontextus():
    """A rendszer tanúsítványkészletét használjuk, nem a certifi-ét.

    A www.vizugy.hu tanúsítványát a Microsec e-Szignó (magyar hitelesítő)
    adta ki. Ez benne van a rendszer készletében — macOS-en és a Linux
    ca-certificates csomagban is —, a certifi Mozilla-alapú készletében
    viszont nincs. A certifi tehát itt rosszabb volt az alapértelmezésnél.

    A GitHub Actions Ubuntu-futója tartalmazza a Microsec gyökeret, ezért
    ott is működik."""
    ctx = ssl.create_default_context()
    # A macOS-Python nem a rendszer keychainjét használja, hanem a saját
    # OpenSSL-készletét — abban a Microsec gyökér nincs benne. A repóban
    # tartott láncot ezért külön hozzáadjuk. Linuxon (a bot futója) a
    # rendszerkészlet már tartalmazza, de az extra betöltés ott sem árt.
    lanc = pathlib.Path(__file__).parent / "tanusitvanyok" / "vizugy-lanc.pem"
    if lanc.exists():
        try:
            ctx.load_verify_locations(cafile=str(lanc))
        except Exception:
            pass
    return ctx


SSL_CTX = _ssl_kontextus()

def _visszalepes():
    """A napi ág visszalépését jelzi. A GitHub Actions naplója ezt nem mutatja:
    minden lépés sikeres, mert egy hiányzó termék nem állítja meg a futást.
    A frissit.sh viszont fájlba írja, melyik napot kértük és meddig jutottunk."""
    f = pathlib.Path("archiv/napi-diagnosztika.txt")
    if not f.exists():
        return []
    adat = dict(
        sor.split("=", 1) for sor in f.read_text(encoding="utf-8").splitlines()
        if "=" in sor and not sor.startswith("---"))
    if adat.get("visszalepes", "").strip() != "igen":
        return []
    # A visszalépés önmagában NEM hiba: az OMSZ napi állománya két nap
    # késéssel készül el, tehát a legfrissebb nap rendszerint hiányzik.
    # Csak akkor jelezzük, ha kettőnél többet léptünk vissza.
    try:
        k = dt.date.fromisoformat(adat.get("kert_nap", "").strip())
        f = dt.date.fromisoformat(adat.get("feldolgozott_nap", "").strip())
    except ValueError:
        return []
    if (k - f).days <= 2:
        return []
    return [f"A napi frissítés {k} helyett {f}-ig jutott, {(k-f).days} napot "
            "visszalépve. Az OMSZ napi állománya rendszerint két nap késéssel "
            "készül el; ennél többet lépni vissza már elakadásra utal."]

def get(url: str, timeout=35) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return r.read().decode("utf-8", errors="replace")


def sz(s):
    s = (s or "").replace("\u00a0", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None



# ── Az OVF hivatalos API-ja ─────────────────────────────────────────────
# Az OVF maga javasolta ezt a felületet a HTML-elemzés helyett. Előnye a
# negyedórás felbontás, a törzsadatból jövő LKV, és hogy nem terheljük
# fölöslegesen a weboldalukat. A régi parse_allomas() tartalékként megmarad:
# ha az API elérhetetlen, arra esünk vissza.
try:
    import vizapi
    VAN_API = True
except Exception as _e:
    VAN_API = False
    print(f"  vizapi nem elérhető ({_e}) — marad a HTML-elemzés")


def api_merce(torzsszam: int, orak: int = 30):
    """Egy mérce metaadata és idősora az API-ból, a parse_allomas formájában."""
    most = dt.datetime.now(dt.timezone.utc)
    kezd = most - dt.timedelta(hours=orak)
    veg = most + dt.timedelta(hours=2)

    sorozat = {}
    # 85: vizho a vizfelszin kozeleben, 89: a mederfeneknel. Mindkettot
    # kerjuk: a lap a mederfeneket reszesiti elonyben, az a hutoviz-srelevans.
    for kod, mezo in ((vizapi.VIZALLAS, "cm"), (vizapi.VIZHOZAM, "q"),
                      (vizapi.VIZHO, "t_felszin"), (89, "t_fenek")):
        try:
            d = vizapi.idosor(torzsszam, kod, kezd, veg).get(torzsszam) or []
        except Exception:
            d = []
        for ido, ertek in d:
            # helyi időben tároljuk, hogy a lap formátuma változatlan maradjon
            kulcs = ido.astimezone().strftime("%Y.%m.%d. %H:%M")
            sorozat.setdefault(kulcs, {"t": kulcs})[mezo] = ertek

    sorok = sorted(sorozat.values(), key=lambda x: x["t"])
    for r in sorok:
        r.setdefault("cm", None); r.setdefault("q", None)
        r.setdefault("t_felszin", None); r.setdefault("t_fenek", None)
    return sorok


def api_torzsadat():
    """{törzsszám: {LKV, nullpont, fkm}} — egyszer kérjük le mind az 1193 mércét."""
    ki = {}
    for x in vizapi.allomasok(11):
        ki[x["Tsz"]] = {
            "lkv_cm": x.get("LKV"),
            "nullpont_mBf": x.get("Mdr"),
            "fkm": x.get("Fkm"),
            "nev_forras": x["Nev"].strip(),
        }
    return ki


def parse_allomas(html: str):
    """Metaadat + órás idősor egy mérce adatlapjáról."""
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
    # A szolgáltató Cloudflare mögött van, és a bot-védelme időnként megfog
    # egy kérést (403). Ez átmeneti: a második próbálkozás rendszerint átmegy.
    utolso = None
    for probalkozas in range(2):
        try:
            d = json.loads(get(DELEJ, timeout=25))
            mw = d.get("paksUnits", {}).get("sum")
            if mw is None:
                mw = d.get("plants", {}).get("paks")
            return {"mw": round(float(mw), 1),
                    "forras": "holadelej.hu /api/data (CC BY 4.0)", "hiba": None}
        except Exception as e:
            utolso = e
            if probalkozas == 0:
                time.sleep(2)
    return {"mw": None, "forras": "holadelej.hu /api/data (CC BY 4.0)",
            "hiba": f"{utolso} (két próbálkozás után)"}


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
        "forras": (f"A blokkteljesítmény {dec_hu(mw)} MW a "
                   f"{dec_hu(h['nevleges_mw'])} MW-os névlegesből. {h['forras']}"),
    }


# A lapon mindenhol magyar tizedesvessző szerepel; a forrásszövegekben is.
def dec_hu(v, tizedes=1):
    if v is None:
        return "—"
    return f"{v:,.{tizedes}f}".replace(",", " ").replace(".", ",")

def meta_of(d):
    # A dátum is átmegy: a napi tagok egy konkrét napra vonatkoznak, és ez
    # a tételsoron is látszik, különben a néző mainak olvassa őket.
    return {"provenance": d["provenance"], "forras": d["forras"],
            "kor_ora": d.get("kor_ora"), "datum": d.get("datum")}




def seo_datumok(most_iso: str):
    """A sitemap lastmod és a JSON-LD dateModified frissítése.

    Enélkül befagy a dátum, és a keresők elavultnak látják a lapot, pedig
    óránként frissül. A sitemap teljes egészében újraíródik — egyetlen URL,
    nincs mit megőrizni benne.
    """
    nap = most_iso[:10]
    pathlib.Path("sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n    <loc>https://basin.equora.institute/</loc>\n'
        f'    <lastmod>{nap}</lastmod>\n'
        '    <changefreq>hourly</changefreq>\n'
        '    <priority>1.0</priority>\n  </url>\n</urlset>\n',
        encoding="utf-8")

    # A JSON-LD dateModified: a helyőrzőt vagy a korábbi értéket cseréljük.
    ut = pathlib.Path("index.html")
    h = ut.read_text(encoding="utf-8")
    import re as _re
    uj_h = _re.sub(r'"dateModified": "[^"]*"',
                   f'"dateModified": "{most_iso}"', h, count=1)
    if uj_h != h:
        ut.write_text(uj_h, encoding="utf-8")

def main():
    p = json.load(open("params.json", encoding="utf-8"))
    mercek, hibak = [], []

    # A törzsadatot (LKV, nullpont, folyamkilométer) egyszer kérjük le mind az
    # 1193 mércére, nem mércénként — így egyetlen hívás elég hozzá.
    torzs = {}
    if VAN_API:
        try:
            torzs = api_torzsadat()
        except Exception as e:
            hibak.append(f"API törzsadat sikertelen ({e}) — marad a HTML-elemzés")

    for nev, voa, folyo, szerep, jegyzet, tsz in MERCEK:
        meta, sorok = {}, []
        # Elsődlegesen az OVF hivatalos API-ja. Ha az elérhetetlen, vagy a
        # mércének nincs törzsszáma, a régi HTML-elemzés ugrik be tartaléknak.
        if VAN_API and tsz and tsz in torzs:
            try:
                sorok = api_merce(tsz)
                meta = dict(torzs[tsz], torzsszam=str(tsz))
            except Exception as e:
                hibak.append(f"{nev}: API-lekérés sikertelen ({e}) — HTML-tartalék")
                sorok = []
        if not sorok:
            try:
                meta, sorok = parse_allomas(get(ALLOMAS.format(voa=voa)))
            except Exception as e:
                hibak.append(f"{nev}: lekérés sikertelen ({e})")
                continue
        if meta.get("nev_forras") and nev.lower() not in meta["nev_forras"].lower():
            hibak.append(f"{nev}: a forrás „{meta['nev_forras']}” nevet mutat — azonosító ellenőrizendő")
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

    # A csapadék ELSŐDLEGES forrása az OMSZ földi mérőhálózata; az IMERG Early
    # csak tartalék és keresztellenőrzés. Indok: 2026-08-17-re a műhold 3,92 mm-t
    # adott, a 269 földi állomás 1,43-at — a különbség a mérleg maradéktagját
    # 4186-ról 775 m³/s-ra vitte le.
    _omsz = p.get("csapadek_omsz_mm_nap") or {}
    _imerg = p.get("csapadek_mm_nap") or {}
    # Az OMSZ csak akkor nyer, ha ugyanarra a napra vonatkozik, mint az IMERG:
    # kölönben régi földi adat kerülne friss hozam mellé.
    CSAP = (_omsz if (_omsz.get("ertek") is not None
                      and _omsz.get("datum") == _imerg.get("datum"))
            else _imerg)
    P = mmps(CSAP["ertek"])
    ET = mmps(p["parolgas_mm_nap"]["ertek"])

    # Egy mérleg tagjai nem jöhetnek különböző napokról. Ha mégis, ki kell mondani.
    d_csap = CSAP.get("datum")
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

    kivetel = [dict(k) for k in p["kivetel_m3s"]]   # az osztályt a kivetel.py adja
    kivetel.append({
        "nev": "Paks hűtővíz", "ertek": paks_hv["ertek"], "fogyaszto": False,
        "fogyaszto_m3s": 0.0, "fogyaszto_hanyad": 0.0,
        "provenance": paks_hv["provenance"],
        "megjegyzes": f"{paks_hv['allapot'].capitalize()} — a hűtővíz felmelegítve "
                       f"visszatér a Dunába. {paks_hv['forras']}",
    })
    # MINDEN tétel fogyasztó RÉSZE számít, nem a bruttó kivétele, és nem csak
    # azoké, amelyek 50% fölött fogyasztók.
    fogyaszto = sum(k.get("fogyaszto_m3s") or 0 for k in kivetel)
    # Előjel-konvenció: ami a dobozba kerül, POZITÍV; ami elhagyja, NEGATÍV.
    # Az öt tag így összeadva adja ki a készletváltozást.
    # ── A mérleg egyetlen naphoz tartozik ────────────────────────────────
    # Az öt tag különböző sebességű forrásból jön: a hozam órás, a csapadék és a
    # párolgás napi. Ezek összeadása csak akkor értelmes, ha MIND UGYANARRA A NAPRA
    # vonatkozik — a tegnapi eső egy része ma is a mederben van, tehát a tegnapi
    # csapadékot a mai hozammal összevetni fizikailag hibás.
    #
    # Ezért a mérleget a legutóbbi teljes napból számoljuk: az archívum napi sora
    # tartalmazza az aznapi órás minták átlagát és az aznapi légköri tagokat.
    # Az órás adat ettől függetlenül látszik a mércesorban és a paksi csomópontban.
    Q_be_most, Q_ki_most = Q_be, Q_ki
    merleg_nap = None
    try:
        _napok = archivum.napi_osszegzes(p)
        for _r in reversed(_napok):
            if all(_r.get(k) is not None for k in ("q_be", "q_ki", "csapadek_mm", "parolgas_mm")):
                merleg_nap = _r
                break
    except Exception as e:
        hibak.append(f"Napi mérleg: {e}")

    if merleg_nap:
        _T = BOX["terulet_km2"] * 1e6
        _mm = lambda v: v / 1000 * _T / 86400          # mm/nap → m³/s
        P     = _mm(merleg_nap["csapadek_mm"])
        ET    = _mm(merleg_nap["parolgas_mm"])
        Q_be  = merleg_nap["q_be"]
        Q_ki  = abs(merleg_nap["q_ki"])
        merleg_datum = merleg_nap["nap"]
    else:
        merleg_datum = None

    # A Hernád határszelvénye (Ždaňa, SHMÚ): eddig hiányzó bejövő tag. A magyar
    # Sajópüspöki mérce a Hernád torkolata FÖLÖTT van, ezért ez a víz sehol nem
    # szerepelt a mérlegben — a le nem zárt tag egyik ismert forrása volt.
    _hernad = p.get("hernad_hatarszelveny") or {}
    _hernad_q = _hernad.get("ertek") if isinstance(_hernad.get("ertek"), (int, float)) else 0
    Q_be = Q_be + _hernad_q

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
            "oras": {"cimke": "vízállás · hozam · vízhő",
                 "forras": "OVF nyílt adat-API (data.vizugy.hu), negyedórás felbontás",
                     # A mércék nem egyszerre frissülnek az OVF-nél: a legtöbb óránként,
                     # néhány csak hat- vagy tizenét óránként. A fejléc a LEGFRISSEBBet
                     # mutatja, és kiírja, hány mérce tart ott — így a késő mércék
                     # láthatóak maradnak.
                     "utolso": (max((m.get("utolso_ido") or "") for m in mercek) or None),
                     # Negyedórás rácson a mércék időbélyege szinte sosem esik egybe, ezért
                     # nem az azonos bélyegűeket számoljuk, hanem azt, hány mérce frissült
                     # az elmúlt órában — ez mutatja meg, él-e a gyűjtés.
                     "mercek_friss": sum(
                         1 for m in mercek
                         if (m.get("utolso_ido") or "") >= (
                             datetime.now() - timedelta(hours=1)
                         ).strftime("%Y.%m.%d. %H:%M")),
                     "mercek_osszes": len(mercek),
                     # A "20/22 mérce frissült" olvasója joggal kérdezi, melyik
                     # kettő hiányzik. Enélkül a szám bizalmatlanságot kelt; a
                     # névsorral viszont a késés maga is átlátható adat.
                     "mercek_keso": [
                         m["nev"] for m in mercek
                         if (m.get("utolso_ido") or "") < (
                             datetime.now() - timedelta(hours=1)
                         ).strftime("%Y.%m.%d. %H:%M")]},
            "napi": {"cimke": "csapadék · párolgás",
                     "forras": (f"csapadék {d_csap or '?'} · párolgás {d_par or '?'}"
                                if d_csap != d_par else p["_forrasok"]["napi"]),
                     "utolso": merleg_napja},
            "havi": {"cimke": "készletváltozás","forras": ((p.get("keszlet_idosor") or {}).get("forras") or p["_forrasok"]["havi"]),"utolso": ((p.get("keszlet_idosor") or {}).get("veg") or p.get("_ervenyes_havi"))},
        },
        "mercek": mercek,
        "paks": paks_csomopont,
        "mm_nap": {"csapadek": mm(be_P), "hozam_be": mm(be_Q), "parolgas": mm(ki_ET),
                   "hozam_ki": mm(ki_Q), "keszletvaltozas": mm(dS)},
        "elojel": ("Ami a dobozba kerül: pozitív, ami elhagyja: negatív. Az öt tag összege a ""készletváltozás — ez NEM megfigyelt országos készletcsökkenés, hanem MARADÉKTAG, ""amelyben a fenti tagok minden hibája összegyűlik. A tagok időléptéke eltér: órás, ""napi és havi adat kerül egyetlen egyenletbe."),
        "merleg_datum": merleg_datum,
        "pillanatkep_m3s": {"hozam_be": round(Q_be_most), "hozam_ki": round(Q_ki_most)},
        "merleg_m3s": {
            "csapadek": {"ertek": round(be_P), **meta_of(CSAP)},
            # A műholdas becslés külön is megmarad: az eltérés maga is adat.
            "csapadek_muhold": ({"ertek": round(mmps(p["csapadek_mm_nap"]["ertek"])),
                                 **meta_of(p["csapadek_mm_nap"])}
                                if p.get("csapadek_mm_nap") else None),
            "hozam_be": {"ertek": round(be_Q), "provenance": "szarmaztatott",
                         "kor_ora": 24, "datum": merleg_datum,
                         "forras": "OVF vízhozam napi átlaga az órás mintákból: " + ", ".join(m["nev"] for m in be)},
            "parolgas": {"ertek": round(ki_ET), **meta_of(p["parolgas_mm_nap"])},
            "hozam_ki": {"ertek": round(ki_Q), "provenance": "szarmaztatott",
                         "kor_ora": 24, "datum": merleg_datum,
                         "forras": "OVF vízhozam napi átlaga az órás mintákból: " + ", ".join(m["nev"] for m in ki)},
            "keszletvaltozas": {"ertek": round(dS), "provenance": "modellezett",
                                "kor_ora": 24, "datum": merleg_datum,
                                "forras": "maradéktag a fenti tételekből"},
        },
        "hova_lett_m3s": {
            "parolgas_muhold": {"ertek": round(ET), **meta_of(p["parolgas_mm_nap"])},
            # Harmadik, FÜGGETLEN becslés: az ECMWF ERA5-Land reanalízise.
            # Teljesen más módszertan, mint a műholdas sugárzási mérleg — ezért
            # alkalmas keresztellenőrzésre. Öt-hat napos késéssel érkezik.
            "parolgas_era5": ({"ertek": round(p["parolgas_era5_mm_nap"]["ertek"]
                                          / 1000 * BOX["terulet_km2"] * 1e6 / 86400),
                               **meta_of(p["parolgas_era5_mm_nap"])}
                              if p.get("parolgas_era5_mm_nap") else None),
            "parolgas_maradek": {"ertek": round(ET_maradek), "provenance": "modellezett",
                                 "kor_ora": None,
                                 "forras": "P + Q_be − Q_ki − ΔS − fogyasztó kivétel"},
            "elteres": {"ertek": round(ET_maradek - ET), "provenance": "modellezett",
                        "kor_ora": None, "forras": "a két becslés különbsége"},
        },
        "kivetel_m3s": kivetel,
        "egyenleg": p["egyenleg"],
        "keszlet_idosor": p.get("keszlet_idosor"),
        "mdb_falak": p.get("mdb_falak"),
        "talaj_vizhiany": p.get("talaj_vizhiany"),
        # A talajvíz évtizedes süllyedése - a harmadik rekesz, amiről eddig
        # csak beszéltünk. Most 487 kút mérése áll mögötte.
        "talajviz": p.get("talajviz"),
        "terkep": (json.loads(pathlib.Path("terkep.json").read_text(encoding="utf-8"))
                   if pathlib.Path("terkep.json").exists() else None),
        # A referencia-párolgás elsődleges forrása a földi mérőhálózat; a
        # műholdas METREF keresztellenőrzésként marad. Az OMSZ csak akkor nyer,
        # ha ugyanarra a napra vonatkozik, mint a műholdas becslés.
        # Az OVSZ vízállás-előrejelzése. Nem a mérleg része: cm-ben van,
        # a mérleghez m³/s kellene. Külön panelben jelenik meg.
        "elorejelzes": p.get("elorejelzes"),
        "ontozesigeny": (lambda o, f: (
            {**o, "et_ref_mm": f["ertek"], "et_ref_forras": f["forras"],
             "et_ref_provenance": "helyszini",
             "et_ref_muhold_mm": o.get("et_ref_mm")}
            if o and f and f.get("datum") == o.get("datum") else o)
        )(p.get("ontozesigeny"), p.get("et_ref_omsz_mm_nap")),
        "kivetel_modell": p.get("kivetel_modell"),
        "figyelmeztetes": p["_figyelmeztetes"],
        "nyitott_falak": NYITOTT_FALAK,
        "belso_megjegyzes": BELSO_MEGJEGYZES,
        # Ha a mérleg napja két napnál régebbi, azt kimondjuk. Enélkül a lap
        # csendben mutat elavult adatot: minden lépés "sikeres", a hibalista
        # üres, a mérleg viszont napokig áll. Ez már kétszer megtörtént.
        "hibak": ([
            f"A mérleg napja ({merleg_datum}) {(datetime.now().date() - datetime.strptime(merleg_datum, '%Y-%m-%d').date()).days} napja nem frissült — "
            "a napi adatforrások valamelyike elakadt."
        ] if merleg_datum and (datetime.now().date()
             - datetime.strptime(merleg_datum, "%Y-%m-%d").date()).days > 2 else []) + hibak + [
            # A frissit.sh napi lépéseinek hibái: enélkül az Actionsben csend van,
            # és csak napokkal később derül ki, hogy egy adatforrás megállt.
            # A napi-diagnosztika.txt mellette azt is megőrzi, melyik nap kellett
            # volna és meddig jutottunk — ez a visszalépés néma esetét fogja meg.
            sor.strip() for sor in
            (pathlib.Path("archiv/futas-hibak.txt").read_text(encoding="utf-8").splitlines()
             if pathlib.Path("archiv/futas-hibak.txt").exists() else [])
            if sor.strip()
        ] + _visszalepes(),
    }

    # Saját idősor: minden futás rögzül, a napi sorozat újraszámolódik.
    try:
        archivum.rogzit(out)
        napok = archivum.napi_osszegzes(p)
        out["archivum"] = archivum.kumulalt(napok, BOX["terulet_km2"])
        out["archivum"]["napok"] = napok[-30:]
    except Exception as e:
        out["hibak"].append(f"Archívum: {e}")

    # Atomi írás: a lap ötpercenként újratölti a data.json-t, ezért egy
    # megszakadt írás csonka fájlt adna neki. Ideiglenesbe írunk, ellenőrizzük,
    # majd egyetlen os.replace() cseréli le — az a fájlrendszer szintjén atomi.
    _nyers = json.dumps(out, ensure_ascii=False, indent=2)
    json.loads(_nyers)          # ha ez elhasal, nem írunk ki semmit
    for _cel, _tartalom in (("data.json", _nyers),
                            ("data.js", "window.BASIN_DATA = " + _nyers + ";\n")):
        _ideig = _cel + ".uj"
        with open(_ideig, "w", encoding="utf-8") as f:
            f.write(_tartalom)
            f.flush()
            os.fsync(f.fileno())
        os.replace(_ideig, _cel)

    hoz = [m["nev"] for m in mercek if m["hozam_m3s"] is not None]
    rek = [m["nev"] for m in mercek if m["rekord_alatt"]]
    # A sitemap és a JSON-LD dátumai a generálással egyidőben frissülnek:
    # befagyott dátumnal a keresők elavultnak látják a lapot.
    seo_datumok(out.get("generalva") or "")
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
