#!/usr/bin/env python3
"""
ontozesigeny.py — mennyi öntözővíz KELLENE, szemben azzal, amennyit ténylegesen kivesznek.

Futtatás:  python ontozesigeny.py [YYYY-MM-DD]

A GONDOLAT
A 4. panel eddig azt mutatta, mennyi vizet vesznek ki. Az viszont Magyarországon kevés,
mert a szántóterületnek csak töredéke öntözött. Az érdekes szám az, mennyi kellene ahhoz,
hogy a növényzet vízhiány nélkül fejlődjön — és a kettő különbsége maga a mondanivaló:
a magyar mezőgazdaság csapadékfüggő, a hiányt nem öntözéssel pótolja, hanem terméskieséssel.

A SZÁMÍTÁS
    ETc      = Kc × ET_ref            a növényállomány vízigénye
    hiány    = max(0, ETc − ET_act)   amennyi ehhez még hiányzik
    m³/s     = hiány × szántóterület

  ET_ref : LSA SAF METREF — referencia-párolgás (fűfelszín, korlátlan vízellátással)
  ET_act : LSA SAF DMETv3 — tényleges párolgás, amit a műhold mér
  Kc     : növénykoefficiens. Nem egy szám: tól-ig tartományt számolunk vele.

AMIT EZ NEM MOND MEG
Ez nem agronómiai javaslat és nem öntözési terv. A műholdas ET_act vegyes felszínborításra
vonatkozik, nem tábla szintű növényállományra; a Kc egy táblázatos érték, nem a te földed.
Nagyságrendi számítás — arra jó, hogy a vízkivétel és a vízigény közti szakadékot mutassa.
"""

import datetime as dt
import json
import netrc
import pathlib
import sys
import urllib.request

import numpy as np
import xarray as xr

import maszk

GEP = "datalsasaf.lsasvcs.ipma.pt"
URL_REF = ("https://" + GEP + "/PRODUCTS/MSG/METREF/NETCDF/{d:%Y}/{d:%m}/{d:%d}/"
           "NETCDF4_LSASAF_MSG_METREF_MSG-Disk_{d:%Y%m%d}0000.nc")
URL_ACT = ("https://" + GEP + "/PRODUCTS/MSG/MDMETv3/NETCDF/{d:%Y}/{d:%m}/{d:%d}/"
           "NETCDF4_LSASAF_MSG_DMETv3_MSG-Disk_{d:%Y%m%d}0000.nc")

BBOX = {"lat_min": 45.7, "lat_max": 49.1, "lon_min": 16.0, "lon_max": 22.9}
KESES_NAP = 1
PARAMS = pathlib.Path("params.json")


def kert_nap() -> dt.date:
    if len(sys.argv) > 1:
        return dt.date.fromisoformat(sys.argv[1])
    return dt.date.today() - dt.timedelta(days=KESES_NAP)


def letolt(url: str) -> str:
    nev = url.rsplit("/", 1)[1]
    if pathlib.Path(nev).exists():
        return nev
    user, _, jelszo = netrc.netrc().authenticators(GEP)
    kez = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    kez.add_password(None, "https://" + GEP + "/", user, jelszo)
    nyito = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(kez))
    with nyito.open(url, timeout=180) as r, open(nev, "wb") as f:
        f.write(r.read())
    return nev


def mezo(path: str, nev_jelolt: tuple) -> xr.DataArray:
    ds = xr.open_dataset(path)
    nev = next((v for v in nev_jelolt if v in ds.data_vars), None)
    if nev is None:
        raise RuntimeError(f"Nem találom a mezőt {nev_jelolt} — elérhető: {list(ds.data_vars)}")
    da = ds[nev]
    if "time" in da.dims:
        da = da.isel(time=0)
    m = (ds.lat >= BBOX["lat_min"]) & (ds.lat <= BBOX["lat_max"])
    n = (ds.lon >= BBOX["lon_min"]) & (ds.lon <= BBOX["lon_max"])
    return da.where(m & n, drop=True).where(lambda x: x >= 0)


def main():
    nap = kert_nap()
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    cfg = p.get("ontozesigeny_beallitas") or {}
    szanto_ha = cfg.get("szanto_ha", 4_300_000)
    kc_min = cfg.get("kc_min", 0.8)
    kc_max = cfg.get("kc_max", 1.2)

    ref = mezo(letolt(URL_REF.format(d=nap)), ("METREF", "ETref", "ET"))
    act = mezo(letolt(URL_ACT.format(d=nap)), ("ET",))

    ref_mm, cellak, ter = maszk.sulyozott_atlag(ref, "lat", "lon")
    act_mm, _, _ = maszk.sulyozott_atlag(act, "lat", "lon")

    szanto_m2 = szanto_ha * 10_000.0
    def m3s(mm):
        return mm / 1000.0 * szanto_m2 / 86400.0

    ki = {}
    for cimke, kc in (("also", kc_min), ("kozep", (kc_min + kc_max) / 2), ("felso", kc_max)):
        hiany_mm = max(0.0, kc * ref_mm - act_mm)
        ki[cimke] = {"kc": kc, "hiany_mm_nap": round(hiany_mm, 2),
                     "m3s": round(m3s(hiany_mm))}

    # Vízstressz-index: mennyire tud a felszín párologtatni ahhoz képest, amennyit tudna.
    stressz = act_mm / ref_mm if ref_mm else None

    p["ontozesigeny"] = {
        "datum": nap.isoformat(),
        "et_ref_mm": round(ref_mm, 2),
        "et_act_mm": round(act_mm, 2),
        "vizstressz": round(stressz, 3) if stressz else None,
        "szanto_ha": szanto_ha,
        "tartomany": ki,
        "provenance": "modellezett",
        "forras": (f"LSA SAF METREF és DMETv3, {nap.isoformat()}, országhatár-maszkkal; "
                   f"Kc {kc_min}–{kc_max}; szántóterület {szanto_ha:,} ha"),
        "figyelmeztetes": ("Nagyságrendi számítás, nem öntözési terv. A műholdas tényleges "
                           "párolgás vegyes felszínborításra vonatkozik, nem tábla szintű "
                           "növényállományra. A szántóterület helyőrző, KSH-adattal cserélendő."),
    }
    p.setdefault("ontozesigeny_beallitas", {
        "szanto_ha": szanto_ha, "kc_min": kc_min, "kc_max": kc_max,
        "megjegyzes": "Kc: FAO-56 táblázatos növénykoefficiens tartománya a nyári "
                      "főnövényekre (kukorica, napraforgó, lucerna) a tenyészidőszakban.",
    })
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{nap}  ({cellak} cella, {ter:,.0f} km²)")
    print(f"  referencia-párolgás  ET_ref = {ref_mm:.2f} mm/nap")
    print(f"  tényleges párolgás   ET_act = {act_mm:.2f} mm/nap")
    print(f"  vízstressz-index     ET_act/ET_ref = {stressz:.2f}"
          + ("   ← 0,5 alatt súlyos vízhiány" if stressz and stressz < 0.5 else ""))
    print(f"  öntözésigény {szanto_ha:,} ha szántóra:")
    for cimke in ("also", "kozep", "felso"):
        k = ki[cimke]
        print(f"    Kc={k['kc']:.1f}  {k['hiany_mm_nap']:>5.2f} mm/nap  =  {k['m3s']:>6,} m³/s")


if __name__ == "__main__":
    main()
