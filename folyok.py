#!/usr/bin/env python3
"""
folyok.py — folyóvonalak a térképhez, a Natural Earth 10m adatbázisából.

A terkep.json bővítése: az országhatár és az aszályállomások mellé a nagyobb
folyók vonala is bekerül, ugyanabban a vetületben. A lap ezeken animált
áramlást rajzol, amelynek SEBESSÉGE a mért vízhozamból származik — a mozgás
tehát adatot hordoz, nem díszít.

Futtatás:  python folyok.py
"""

import json, math, pathlib, urllib.request

NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
      "master/geojson/ne_10m_rivers_lake_centerlines.geojson")
DOBOZ = (16.0, 45.7, 22.9, 49.1)          # Ny, D, K, É
GYORSITO = pathlib.Path("ne_rivers.geojson")


def betolt():
    if GYORSITO.exists():
        return json.loads(GYORSITO.read_text(encoding="utf-8"))
    req = urllib.request.Request(NE, headers={"User-Agent": "equora-basin/2.3"})
    nyers = urllib.request.urlopen(req, timeout=180).read().decode("utf-8")
    GYORSITO.write_text(nyers, encoding="utf-8")
    return json.loads(nyers)


def belul(p):
    return DOBOZ[0] <= p[0] <= DOBOZ[2] and DOBOZ[1] <= p[1] <= DOBOZ[3]


def vonalak(geom):
    t = geom.get("type")
    if t == "LineString":
        return [geom["coordinates"]]
    if t == "MultiLineString":
        return geom["coordinates"]
    return []


def dp(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    def tav(p):
        dx, dy = b[0]-a[0], b[1]-a[1]
        if dx == dy == 0:
            return math.hypot(p[0]-a[0], p[1]-a[1])
        t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx+dy*dy)))
        return math.hypot(p[0]-(a[0]+t*dx), p[1]-(a[1]+t*dy))
    i, d = max(((i, tav(p)) for i, p in enumerate(pts[1:-1], 1)), key=lambda z: z[1])
    return (dp(pts[:i+1], tol)[:-1] + dp(pts[i:], tol)) if d > tol else [a, b]


def main():
    tk = json.loads(pathlib.Path("terkep.json").read_text(encoding="utf-8"))
    # a vetítés visszafejtése a meglévő térképből: a magyar határ bbox-ából
    gj = json.loads(pathlib.Path("hatar.geojson").read_text(encoding="utf-8"))
    hu = next(f for f in gj["features"]
              if f["properties"].get("ADM0_A3") == "HUN")
    g = hu["geometry"]
    gy = ([g["coordinates"][0]] if g["type"] == "Polygon"
          else [p[0] for p in g["coordinates"]])
    fo = max(gy, key=len)
    xs = [p[0] for p in fo]; ys = [p[1] for p in fo]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    kozep = math.radians((y0+y1)/2)
    sx = 1000/(x1-x0)
    vet = lambda lo, la: (round((lo-x0)*sx, 1), round((y1-la)*sx/math.cos(kozep), 1))

    d = betolt()
    ki = []
    for f in d["features"]:
        pr = f.get("properties", {})
        nev = pr.get("name") or pr.get("name_en") or ""
        sr = pr.get("scalerank") or 99
        for v in vonalak(f.get("geometry") or {}):
            benn = [p for p in v if belul(p)]
            if len(benn) < 4:
                continue
            # csak a jelentősebb vízfolyások, hogy a térkép olvasható maradjon
            if sr > 7 and not nev:
                continue
            e = dp(benn, 0.008)
            if len(e) < 3:
                continue
            d_attr = "M" + "L".join(f"{a},{b}" for a, b in (vet(*p) for p in e))
            ki.append({"nev": nev, "rang": sr, "path": d_attr, "pontok": len(e)})

    ki.sort(key=lambda r: (r["rang"], -r["pontok"]))
    ki = ki[:24]
    tk["folyok"] = ki
    pathlib.Path("terkep.json").write_text(
        json.dumps(tk, ensure_ascii=False), encoding="utf-8")

    print(f"{len(ki)} folyószakasz a dobozban:")
    for r in ki[:14]:
        print(f"  {r['nev'] or '(névtelen)':<22} rang {r['rang']}, {r['pontok']} pont")
    print("össz. path-hossz:", sum(len(r["path"]) for r in ki), "karakter")


if __name__ == "__main__":
    main()
