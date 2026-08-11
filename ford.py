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
        if hu in x:
            x = x.replace(hu, en)
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
    x = re.sub(r'(src|href)="(data\.js|data\.json|logo\.png|logo\.svg)"',
               r'\1="../\2"', x)
    x = x.replace('fetch("data.json")', 'fetch("../data.json")')

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


if __name__ == "__main__":
    main()
