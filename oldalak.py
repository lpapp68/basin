#!/usr/bin/env python3
"""oldalak.py — a hierarchikus lap előállítása a publikálási mappába (2026-11-25).

A lap két rétegű:
  • a főoldal (fooldal.html → /index.html) a kizoomolt nézet laikusoknak: egy kiemelt
    megfigyelés, négy kártya, egy helykereső;
  • az aloldalak (/folyok, /talaj, …) a részletek.

Az aloldalak forrása továbbra is EGYETLEN fájl, a teljes index.html. Minden aloldal ennek a
másolata: a teljes logika lefut, a lap csak a saját szakaszait mutatja. Így a rajzoló kód
egy helyen él, a tesztlap.js ugyanazt ellenőrzi, és két aloldal nem tud szétcsúszni.

Futtatás:  python3 oldalak.py _publish
"""
import pathlib
import re
import sys

FORRAS = pathlib.Path(__file__).with_name("index.html")
FOOLDAL = pathlib.Path(__file__).with_name("fooldal.html")

# Oldal → (cím, bevezető, megjelenő elemek). A „mutat” lista CSS-szelektorokat tartalmaz:
# a .wrap közvetlen gyermekei (szakaszok) és a fejléc gyermekei közül csak ezek látszanak.
# A „rejt” a megjelenő szakaszokon belül tüntet el elemet.
OLDALAK = {
    "folyok": dict(
        cim="A folyók",
        lead="A folyók vize gyorsan mozog: ami ma Dévénynél belép, egy hét múlva Mohácsnál jár. "
             "Itt a 22 főmérce mai állása látszik, egy kereső mind az 507 mércéhez, és a hatnapos előrejelzés.",
        mutat=["#mercek-sec", "#elore-sec"],
        rejt=["#rovid"]),
    "talaj": dict(
        cim="A talaj",
        lead="A talajban hetekig marad a víz, és itt dől el, mit ér a lehullott eső. Az aszály itt zajlik. "
             "Lejjebb a talajvíz: az évtizedek alatt pótlódó, lassú rekesz.",
        mutat=["header", "#talaj-sec"],
        fej=["#stressz"],
        rejt=["#dobozjel"]),
    "beszivargas": dict(
        cim="Hová jut az eső?",
        lead="Az eső a felszínen még csak bevétel. A mérőállomások hat mélységben, óránként mérik a talaj "
             "nedvességét: ebből látszik, milyen mélyre jutott le a víz, és mennyi maradt belőle a talajban.",
        mutat=["#beszivargas-sec"]),
    "keszlet": dict(
        cim="Az ország vízkészlete",
        lead="Két műhold havonta megméri, mennyivel több vagy kevesebb víz van az országban a sokéves átlagnál: "
             "a folyókban, a talajban és a mélyben együtt. A görbe 2002 óta mutatja a változást.",
        mutat=["#panel-sec", "#valt-sec"],
        rejt=["#panel-sec>.sz", "#panel-sec .jelmagy", "#p-pulzus", "#p-hovalett", "#p-kivetel"]),
    "merleg": dict(
        cim="A napi vízmérleg",
        lead="Szakmai nézet. Mennyi víz érkezik naponta esőből és a folyókon, mennyi párolog el és folyik ki, "
             "és mekkora az a rész, amit a mérőrendszer még nem tud elszámolni. Minden szám mellett ott a bizonytalansága.",
        mutat=["header", "#mdb-sec", "#panel-sec", "#mintazat-sec"],
        fej=[".fejracs"],
        rejt=["#p-egyenleg"]),
    "mi-lenne-ha": dict(
        cim="Mi lenne, ha…?",
        lead="Két kérdés a Duna vizéről. Mikor korlátozhatja a folyó a paksi erőművet? "
             "És mennyi öntözővizet lehetne kivenni a Dunából, kinek a rovására?",
        mutat=["#paks-sec", "#ontozo-sec"]),
    "modszertan": dict(
        cim="Módszertan és források",
        lead="Minden adat nyilvános forrásból jön. Itt olvasható, honnan, milyen felbontásban, "
             "és mit nem fog még be a modell.",
        mutat=["#forras-sec", ".alairas"]),
    "reszvetel": dict(
        cim="Közös kutatás",
        lead="Egy kiválasztott terület — vízgyűjtő, tó vagy öntözött térség — vizsgálata a lap adataiból, "
             "a helyiek méréseivel és kérdéseivel kiegészítve.",
        mutat=["#kutatas-sec"]),
}

NAV = [("folyok", "Folyók"), ("talaj", "Talaj"), ("beszivargas", "Az eső útja"),
       ("keszlet", "Vízkészlet"), ("mi-lenne-ha", "Mi lenne, ha…?"),
       ("merleg", "Vízmérleg (szakmai)"), ("modszertan", "Módszertan")]

# Melyik horgony melyik oldalon él — a lapon belüli hivatkozások ehhez igazodnak.
HORGONY = {"talaj-sec": "talaj", "stressz": "talaj", "beszivargas-sec": "beszivargas",
           "valt-sec": "keszlet", "p-egyenleg": "keszlet", "elore-sec": "folyok",
           "mercek-sec": "folyok", "kutatas-sec": "reszvetel", "forras-sec": "modszertan",
           "paks-sec": "mi-lenne-ha", "ontozo-sec": "mi-lenne-ha", "mdb-sec": "merleg",
           "mintazat-sec": "merleg", "panel-sec": "merleg", "p-pulzus": "merleg",
           "p-hovalett": "merleg", "p-kivetel": "merleg"}

STILUS = """
/* Aloldal (oldalak.py): a teljes lap logikája fut, csak ennek az oldalnak a szakaszai látszanak. */
.wrap>:is(section,header,.alairas):not(%(mutat)s){display:none}
%(fej)s
%(rejt)s
.alfej{padding:22px 0 18px;border-bottom:2px solid var(--tinta)}
.alfej .vissza{font-family:var(--mono);font-size:12px;letter-spacing:.06em;color:var(--viz);text-decoration:none}
.alfej .vissza:hover{text-decoration:underline}
.alfej h1{margin:.35em 0 .15em}
.alfej .alcim-l{max-width:70ch;color:var(--halvany);font-size:16px;margin:0}
.alnav{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:16px;padding-top:10px;border-top:1px solid var(--vonal);
  font-size:13.5px}
.alnav a{color:var(--halvany);text-decoration:none}
.alnav a:hover{color:var(--viz);text-decoration:underline}
.alnav a[aria-current]{color:var(--tinta);font-weight:600}
.alfej+section .sz,.alfej+header+section .sz{margin-top:30px}
%(laikus)s
.allab{margin-top:40px;padding-top:12px;border-top:1px solid var(--vonal);font-size:13px;color:var(--halvany)}
.allab a{color:var(--halvany)}
"""
# A laikus aloldalakon a szakmai sáv (#warn) és a módszertani lábjegyzet (#lab) helyett egy rövid lábléc áll.
SZAKMAI = {"merleg", "modszertan"}
ALLAB = ('<div class="allab">Kutatási felület · EQUORA Institute · <a href="/modszertan">Módszertan és források</a> · '
         '<a href="/data.json">nyers adat</a> · <a href="/impresszum">Impresszum</a> · <a href="/adatkezeles">Adatkezelés</a></div>')


def aloldal(src: str, nev: str, o: dict) -> str:
    mutat = ",".join(o["mutat"])
    fej = ""
    if o.get("fej"):
        fej = ("header{padding:0;border:0}header>:not(" + ",".join(o["fej"]) + "){display:none}"
               + ".fejracs{margin-top:18px}.stressz{margin-top:22px}")
    rejt = (",".join(o["rejt"]) + "{display:none}") if o.get("rejt") else ""
    if nev == "keszlet":
        rejt += "#panel-sec .racs{grid-template-columns:1fr}"
    laikus = "" if nev in SZAKMAI else "#warn,#lab{display:none}"
    css = STILUS % {"mutat": mutat, "fej": fej, "rejt": rejt, "laikus": laikus}

    akt = ' aria-current="page"'
    nav = "".join(f'<a href="/{k}"{akt if k == nev else ""}>{c}</a>' for k, c in NAV)
    fejlec = (f'<div class="alfej"><a class="vissza" href="/">← Mennyi víz van Magyarországon, és hol?</a>'
              f'<h1>{o["cim"]}</h1><p class="alcim-l">{o["lead"]}</p>'
              f'<nav class="alnav" aria-label="Aloldalak">{nav}</nav></div>')

    out = src
    out = out.replace("</style>", css + "</style>", 1)
    out, n = re.subn(r'(<div class="wrap">\s*)', lambda m: m.group(1) + fejlec + "\n", out, count=1)
    if n != 1:
        raise SystemExit(f"oldalak.py: a .wrap nyitótagja hiányzik ({nev})")
    out = re.sub(r"<title>.*?</title>", f"<title>{o['cim']} — Mennyi víz van Magyarországon? — EQUORA Institute</title>", out, count=1, flags=re.S)
    out = out.replace('href="https://basin.equora.institute/"', f'href="https://basin.equora.institute/{nev}"')
    out = out.replace('content="https://basin.equora.institute/"', f'content="https://basin.equora.institute/{nev}"')
    out = out.replace('<body>', f'<body data-nezet="{nev}">', 1)
    if nev not in SZAKMAI:
        out, n = re.subn(r'(<footer id="lab"></footer>)', lambda m: m.group(1) + ALLAB, out, count=1)
        if n != 1:
            raise SystemExit("oldalak.py: a lábléc (#lab) hiányzik")
    # Hivatkozások más oldal szakaszára.
    ide = {h for h, lap in HORGONY.items() if lap == nev}

    def athelyez(m):
        h = m.group(1)
        if h in ide or h not in HORGONY:
            return m.group(0)
        return f'href="/{HORGONY[h]}#{h}"'
    out = re.sub(r'href="#([\w-]+)"', athelyez, out)
    return out


def main():
    cel = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_publish")
    cel.mkdir(exist_ok=True)
    src = FORRAS.read_text(encoding="utf-8")
    for kell in ('id="mercek-sec"', 'id="panel-sec"', 'id="talaj-sec"', 'id="beszivargas-sec"',
                 'id="forras-sec"', 'id="kutatas-sec"', 'id="paks-sec"', 'id="valt-sec"'):
        if kell not in src:
            raise SystemExit(f"oldalak.py: az index.html-ből hiányzik: {kell}")
    for nev, o in OLDALAK.items():
        (cel / f"{nev}.html").write_text(aloldal(src, nev, o), encoding="utf-8")
    (cel / "index.html").write_text(FOOLDAL.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  oldalak: főoldal + {len(OLDALAK)} aloldal → {cel}/")


if __name__ == "__main__":
    main()
