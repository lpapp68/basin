"""
A 69-es kód előjelének eldöntése FÜGGETLEN forrással.

Az aszálymonitoring 127 állomása vízhiányt ad (mm) — ott a nagyobb szám
egyértelműen SZÁRAZABB talajt jelent. Ha a két adatsor ugyanazon a helyen
együtt mozog, akkor a 69-es kódnál is a nagyobb szám = mélyebb víz.

Módszer: területi párosítás koordináta alapján (20 km-en belül), majd a
két idősor kapcsolatának vizsgálata több éven át.
"""
import datetime as dt, math, statistics, sys
import vizapi, aszaly_api

most = dt.datetime.now(dt.timezone.utc)

# aszalyallomasok koordinataval
asz = aszaly_api.allomasok()
def eov_wgs(x, y):
    lat = 47.1 + (x - 200000) / 111320.0
    lon = 19.05 + (y - 650000) / (111320.0 * math.cos(math.radians(47.1)))
    return lat, lon
asz_h = {}
for s in asz:
    try:
        lat, lon = eov_wgs(float(s["eovx"]), float(s["eovy"]))
        asz_h[s["statid"]] = (lat, lon, s["name"].strip())
    except Exception:
        pass

# talajvizkutak
kut = vizapi.allomasok(12)
kut_h = {x["Tsz"]: (x["Lat"], x["Lon"], x["Nev"].strip()) for x in kut
         if x.get("Lat") and x.get("Lon")}

# parositas: minden aszalyallomashoz a legkozelebbi kut 20 km-en belul
paros = []
for sid, (la, lo, nv) in asz_h.items():
    legjobb, tav = None, 1e9
    for tsz, (la2, lo2, nv2) in kut_h.items():
        d = math.hypot((la-la2)*111, (lo-lo2)*75)
        if d < tav: legjobb, tav = tsz, d
    if tav < 20:
        paros.append((sid, legjobb, round(tav,1), nv, kut_h[legjobb][2]))

sys.stdout.write(f"parositva: {len(paros)} allomas-kut par (20 km-en belul)\n")
for p in paros[:6]:
    sys.stdout.write(f"   {p[3][:18]:<20} <-> {p[4][:18]:<20} {p[2]} km\n")
