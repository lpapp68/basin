#!/usr/bin/env python3
"""
kutak.py — a felszín alatti víz észlelőhálózatának jegyzéke, INSPIRE-ből.

Futtatás:  python kutak.py

MIÉRT KELL
A vizugy.hu talajvíz-modulja térképes: kútonként MŰKÖDIK az idősor-lekérdezés
(mapData=KutIdosor), de nincs olyan lista, amiből a kutak azonosítói kinyerhetők —
ellentétben a folyómércékkel, ahol van VizmerceLista oldal.

A megoldás nem a weboldal, hanem az INSPIRE-szolgáltatás. Az irányelv kötelezi a
tagállamokat a környezeti térinformatikai adatok gépi közzétételére, és az OVF
geoportálja ezt teljesíti is — csak a honlapról nem vezet oda út.

  https://geoportal.vizugy.hu/arcgis/rest/services/INSPIRE/Inspire/MapServer/0
  réteg: hyMonitoringSiteP — 4 911 észlelőhely, névvel, azonosítóval, koordinátával

FIGYELEM
A geoportál TLS-konfigurációja régi; egyes hálózatokról (proxy mögül) elutasítja a
kapcsolatot. Ha 503-at kapsz, próbáld másik hálózatról.

KIMENET
  kutak.json — a teljes jegyzék
  kutak_hatsag.json — a Duna–Tisza közi hátságra szűrt részhalmaz

AMI EZUTÁN JÖN
A jegyzék önmagában még nem elég: a KutIdosor végpont GUID-ot vár (AllomasVOA),
a jegyzék viszont INSPIRE-azonosítót (thematicId) ad. A kettő összekötése az OVF
adatigénylés tárgya — a törzsszám lehet a közös kulcs.
"""

import json
import pathlib
import time
import urllib.parse
import urllib.request

SZOLGALTATAS = ("https://geoportal.vizugy.hu/arcgis/rest/services/"
                "INSPIRE/Inspire/MapServer/0/query")
LAPMERET = 1000            # a szolgáltatás maxRecordCount értéke
MEZOK = "thematicId,nameText,localId,mediaWater,opActBegin,opActEnd"

# A Duna–Tisza közi hátság durva befoglaló téglalapja. Nem pontos lehatárolás:
# a hátság valódi határa domborzati, ez csak előszűrés a panelhez.
HATSAG = {"lat_min": 46.1, "lat_max": 47.3, "lon_min": 19.0, "lon_max": 20.2}


def kerdez(offset: int) -> dict:
    adat = urllib.parse.urlencode({
        "where": "1=1",
        "outFields": MEZOK,
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": offset,
        "resultRecordCount": LAPMERET,
        "f": "pjson",
    }).encode()
    req = urllib.request.Request(SZOLGALTATAS, data=adat,
                                 headers={"User-Agent": "equora-basin/2.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    kutak, offset = [], 0
    while True:
        d = kerdez(offset)
        if "error" in d:
            raise RuntimeError(f"A szolgáltatás hibát adott: {d['error']}")
        jegyek = d.get("features", [])
        if not jegyek:
            break
        for f in jegyek:
            a, g = f["attributes"], f.get("geometry") or {}
            kutak.append({
                "azonosito": a.get("thematicId"),
                "nev": a.get("nameText"),
                "local_id": a.get("localId"),
                "viz": a.get("mediaWater"),
                "mukodes_kezd": a.get("opActBegin"),
                "mukodes_veg": a.get("opActEnd"),
                "lon": g.get("x"), "lat": g.get("y"),
            })
        print(f"  {len(kutak)} észlelőhely…")
        if len(jegyek) < LAPMERET:
            break
        offset += LAPMERET
        time.sleep(0.5)

    pathlib.Path("kutak.json").write_text(
        json.dumps(kutak, ensure_ascii=False, indent=1), encoding="utf-8")

    hatsag = [k for k in kutak
              if k["lat"] and HATSAG["lat_min"] <= k["lat"] <= HATSAG["lat_max"]
              and HATSAG["lon_min"] <= k["lon"] <= HATSAG["lon_max"]]
    pathlib.Path("kutak_hatsag.json").write_text(
        json.dumps(hatsag, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nkutak.json: {len(kutak)} észlelőhely")
    print(f"kutak_hatsag.json: {len(hatsag)} a Duna–Tisza közi hátság téglalapjában")
    if kutak:
        print("\npélda:")
        for k in kutak[:3]:
            print(f"  {k['azonosito']}  {k['nev']}  ({k['lat']:.4f}, {k['lon']:.4f})")


if __name__ == "__main__":
    main()
