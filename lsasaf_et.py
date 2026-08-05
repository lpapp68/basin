#!/usr/bin/env python3
"""
lsasaf_et.py — napi területi átlag tényleges párolgás a mérleg dobozára.

Futtatás:  source ~/cds-env/bin/activate && python lsasaf_et.py [YYYY-MM-DD]

Forrás: EUMETSAT LSA SAF, MDMETv3 (DMETv3, LSA-312.3), MSG, NETCDF.
A NetCDF-változat már szabályos 0,05 fokos lat/lon rácson van — a fájlnévben lévő
"MSG-Disk" ellenére. Nem kell átvetítés.

Hitelesítés a ~/.netrc-ből:
    machine datalsasaf.lsasvcs.ipma.pt login <FELHASZNÁLÓ> password <JELSZÓ>

MINŐSÉGSZŰRÉS — ez a lényegi rész:
A napi ET fél órás résekből áll össze. Ahol sok rés hiányzik (felhő, korongperem),
ott a napi összeg ALULBECSÜL, és ezt semmi nem jelzi az ET mezőben. Ezért a
missing_values_percent fölött kidobjuk a cellát, és kiírjuk, mennyit dobtunk.
"""

import datetime as dt
import json
import netrc
import pathlib
import sys
import urllib.request

import numpy as np
import xarray as xr

GEP = "datalsasaf.lsasvcs.ipma.pt"
URL = ("https://" + GEP + "/PRODUCTS/MSG/MDMETv3/NETCDF/{d:%Y}/{d:%m}/{d:%d}/"
       "NETCDF4_LSASAF_MSG_DMETv3_MSG-Disk_{d:%Y%m%d}0000.nc")

BBOX = {"lat_min": 45.7, "lat_max": 49.1, "lon_min": 16.0, "lon_max": 22.9}
KESES_NAP = 1                 # az LSA SAF napi terméke másnap hajnalra kész
MAX_HIANY_SZAZALEK = 20.0     # e fölött a cellát eldobjuk
MIN_LEFEDETTSEG = 0.70        # ha ennél kevesebb cella marad, nem írunk be semmit
PARAMS = pathlib.Path("params.json")


def kert_nap() -> dt.date:
    if len(sys.argv) > 1:
        return dt.date.fromisoformat(sys.argv[1])
    return dt.date.today() - dt.timedelta(days=KESES_NAP)


def letolt(nap: dt.date) -> str:
    url = URL.format(d=nap)
    nev = url.rsplit("/", 1)[1]
    if pathlib.Path(nev).exists():
        return nev
    user, _, jelszo = netrc.netrc().authenticators(GEP)
    kezelo = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    kezelo.add_password(None, "https://" + GEP + "/", user, jelszo)
    nyito = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(kezelo))
    with nyito.open(url, timeout=120) as r, open(nev, "wb") as f:
        f.write(r.read())
    return nev


def terulet_atlag(path: str):
    ds = xr.open_dataset(path)
    et = ds["ET"]
    hiany = ds["missing_values_percent"]
    if "time" in et.dims:
        et, hiany = et.isel(time=0), hiany.isel(time=0)

    # A lat lehet csökkenő sorrendű, ezért maszkkal vágunk, nem slice-szal.
    m = ((ds.lat >= BBOX["lat_min"]) & (ds.lat <= BBOX["lat_max"]))
    n = ((ds.lon >= BBOX["lon_min"]) & (ds.lon <= BBOX["lon_max"]))
    et, hiany = et.where(m & n, drop=True), hiany.where(m & n, drop=True)

    cellak_ossz = int(et.notnull().sum())
    jo = et.where(hiany <= MAX_HIANY_SZAZALEK)
    cellak_jo = int(jo.notnull().sum())
    lefedettseg = cellak_jo / cellak_ossz if cellak_ossz else 0.0

    suly = np.cos(np.deg2rad(jo["lat"])).broadcast_like(jo).where(jo.notnull())
    atlag = float(jo.weighted(suly.fillna(0)).mean(skipna=True).values)
    return atlag, lefedettseg, cellak_ossz, cellak_jo


def beir(mm: float, nap: dt.date, lefedettseg: float) -> None:
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["parolgas_mm_nap"] = {
        "ertek": round(mm, 2),
        "provenance": "mert",
        "forras": (f"EUMETSAT LSA SAF DMETv3 (MSG), {nap.isoformat()}, "
                   f"koszinusz-súlyozott átlag, minőségszűrve "
                   f"(missing_values_percent ≤ {MAX_HIANY_SZAZALEK:.0f}%)"),
        "kor_ora": (dt.date.today() - nap).days * 24,
        "datum": nap.isoformat(),
        "lefedettseg": round(lefedettseg, 3),
        "figyelmeztetes": ("Téglalap-átlag, nem vízgyűjtőre maszkolt. "
                           "A minőségszűrés miatt a felhős cellák kimaradnak — "
                           "erősen felhős napon a maradék minta torzíthat."),
        "hivatkozas": ("Data provided by the EUMETSAT Satellite Application Facility "
                       "on Land Surface Analysis (LSA SAF; Trigo et al., 2011), CC BY 4.0"),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    nap = kert_nap()
    f = letolt(nap)
    mm, lefedettseg, ossz, jo = terulet_atlag(f)
    print(f"{nap}: {mm:.2f} mm/nap párolgás")
    print(f"  cellák: {jo} / {ossz} használható ({lefedettseg:.0%})")
    if lefedettseg < MIN_LEFEDETTSEG:
        print(f"  NEM ÍRTAM BE: a lefedettség {MIN_LEFEDETTSEG:.0%} alatt van. "
              f"Erősen felhős nap — próbáld egy másik dátummal.")
        sys.exit(2)
    beir(mm, nap, lefedettseg)
    print("  beírva a params.json-be. Ezután: python3 fetch_data.py")
