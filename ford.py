#!/usr/bin/env python3
"""
ford.py — az angol változat előállítása a magyar forrásból.

Futtatás:  python ford.py

MIÉRT ÍGY
Két kézzel karbantartott HTML két hét alatt szétcsúszik: a magyar oldalon
naponta javítunk, és az angol lemarad. Ezért EGY forrás van (index.html), és
ebből generáljuk az en/index.html-t egy fordítási tábla alapján.

A tábla a ford.json: magyar → angol párok. A csere a leghosszabb sztringgel
kezdődik, hogy a rövidebb ne harapjon bele egy hosszabb közepébe.

HA HIÁNYZIK EGY FORDÍTÁS
A script kiírja, és a magyar szöveg marad a helyén. Így egy új mondat sosem
tünteti el csendben az angol lapot — látszik, mi van hátra.

SEO
Mindkét lap megkapja a maga canonical URL-jét és a kölcsönös hreflang-et,
tehát a Google két külön, egyenrangú változatnak látja őket, nem duplikátumnak.
"""

import json
import pathlib
import re
import sys

FORRAS = pathlib.Path("index.html")
TABLA = pathlib.Path("ford.json")
CEL = pathlib.Path("en/index.html")


def main():
    x = FORRAS.read_text(encoding="utf-8")
    tabla = json.loads(TABLA.read_text(encoding="utf-8"))

    # A leghosszabbal kezdünk: különben egy rövid darab beleharapna egy
    # hosszabb mondatba, és félig lefordított szöveg keletkezne.
    parok = sorted(((hu, en) for hu, en in tabla.items() if en),
                   key=lambda p: -len(p[0]))

    talalt, hianyzik = 0, []
    for hu, en in parok:
        # Szóhatáron cserélünk: enélkül egy rövid kulcs ("a talaj") belemar
        # egy hosszabb mondatba, és félig magyar szöveget hagy maga után.
        # A \b nem működik ékezetes betűkkel, ezért a szomszédos karaktert
        # nézzük: betű vagy ékezet esetén NEM cserélünk.
        # A szóhatár csak akkor kell, ha a kulcs betűvel kezdődik ÉS végződik:
        # egy HTML-részlet ("<a class=...>") esetén a \b-szerű feltétel sosem
        # teljesülne, és a csere csendben elmaradna.
        betuvel = (hu[0].isalpha() and hu[-1].isalpha())
        if betuvel:
            minta = re.compile(
                r"(?<![A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])" + re.escape(hu) +
                r"(?![A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])")
            x2, db = minta.subn(lambda m: en, x)
        else:
            db = x.count(hu)
            x2 = x.replace(hu, en)
        if db:
            x = x2
            talalt += 1
        else:
            hianyzik.append(hu)

    # ── nyelvi jelölés és SEO ────────────────────────────────────────────
    x = x.replace('<html lang="hu">', '<html lang="en">', 1)
    x = x.replace('<link rel="canonical" href="https://basin.equora.institute/">',
                  '<link rel="canonical" href="https://basin.equora.institute/en/">\n'
                  '<link rel="alternate" hreflang="hu" href="https://basin.equora.institute/">\n'
                  '<link rel="alternate" hreflang="en" href="https://basin.equora.institute/en/">\n'
                  '<link rel="alternate" hreflang="x-default" href="https://basin.equora.institute/">', 1)
    x = x.replace('content="hu_HU"', 'content="en_GB"')
    x = x.replace('"inLanguage": "hu"', '"inLanguage": "en"')
    x = x.replace('"url": "https://basin.equora.institute/"',
                  '"url": "https://basin.equora.institute/en/"')

    # A gyökérhez képest eggyel lejjebb vagyunk: az abszolút útvonalak maradnak,
    # a relatívakat viszont fel kell emelni.
    # A logó a gyökérből jön, az adat viszont az en/ mappából: az angol
    # data.json a lefordított mezőket tartalmazza.
    x = re.sub(r'(src|href)="(logo\.png|logo\.svg|favicon[^"]*|apple[^"]*)"',
               r'\1="../\2"', x)
    

    # magyar dátum- és számformátum → nemzetközi
    x = x.replace('toLocaleString("hu-HU"', 'toLocaleString("en-GB"')
    x = x.replace('new Intl.NumberFormat("hu-HU"', 'new Intl.NumberFormat("en-GB"')

    CEL.parent.mkdir(exist_ok=True)
    CEL.write_text(x, encoding="utf-8")

    print(f"en/index.html kész — {talalt} fordítás alkalmazva")
    if hianyzik:
        print(f"\n{len(hianyzik)} tábla-bejegyzés nem talált a forrásban "
              f"(elavult vagy elgépelt):")
        for h in hianyzik[:10]:
            print("   ", h[:70])

    # Mi maradt fordítatlanul? A magyar ékezetes szó jó jelzés.
    torzs = re.sub(r"<script.*?</script>|<style.*?</style>", "", x, flags=re.S)
    maradt = set(re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]*[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]"
                            r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]*", torzs))
    maradt = {m for m in maradt if len(m) > 3}
    if maradt:
        print(f"\nA HTML-törzsben még {len(maradt)} magyar szó maradt, például:")
        print("   ", ", ".join(sorted(maradt)[:14]))

    adat(tabla)




def adat(tabla):
    """A data.json angol párja: az en/ lap ezt olvassa.

    A lap szövegeinek jó része nem a HTML-ben áll, hanem a data.json-ból jön —
    mércenevek, forrásmegjelölések, jegyzetek. Ezeket ugyanazzal a táblával
    fordítjuk, hogy egy helyen legyen minden.
    """
    import json
    forras = pathlib.Path("data.json")
    if not forras.exists():
        print("data.json hiányzik — az angol adat kimarad")
        return
    parok = sorted(((hu, en) for hu, en in tabla.items() if en),
                   key=lambda x: -len(x[0]))
    szamlalo = {"csere": 0, "erintetlen": []}

    def jar(o):
        if isinstance(o, dict):
            return {k: jar(v) for k, v in o.items()}
        if isinstance(o, list):
            return [jar(v) for v in o]
        if isinstance(o, str):
            eredeti = o
            for hu, en in parok:
                if hu[0].isalpha() and hu[-1].isalpha():
                    minta = re.compile(
                        r"(?<![A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])" + re.escape(hu) +
                        r"(?![A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])")
                    o = minta.sub(lambda m: en, o)
                else:
                    o = o.replace(hu, en)
            if o != eredeti:
                szamlalo["csere"] += 1
            elif re.search(r"[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]", o) and len(o) > 8:
                szamlalo["erintetlen"].append(o)
            return o
        return o

    d = jar(json.loads(forras.read_text(encoding="utf-8")))
    pathlib.Path("en").mkdir(exist_ok=True)
    pathlib.Path("en/data.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    # A lap a data.js-t tölti be (a data.json a letölthető változat).
    # Mindkettőnek elő kell állnia az en/ mappában.
    js = pathlib.Path("data.js")
    if js.exists():
        eleje = js.read_text(encoding="utf-8").split("=", 1)[0]
        pathlib.Path("en/data.js").write_text(
            eleje + "= " + json.dumps(d, ensure_ascii=False) + ";", encoding="utf-8")

    print(f"en/data.json + en/data.js — {szamlalo['csere']} mező fordítva")
    if szamlalo["erintetlen"]:
        print(f"  {len(szamlalo['erintetlen'])} mező maradt magyarul, például:")
        for e in szamlalo["erintetlen"][:6]:
            print("   ", e[:66])

if __name__ == "__main__":
    main()
