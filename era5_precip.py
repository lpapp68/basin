#!/usr/bin/env python3
"""
era5_precip.py — napi területi átlag csapadék a mérleg dobozára.

Futtatás:  source ~/cds-env/bin/activate && python era5_precip.py [YYYY-MM-DD]

Mit csinál:
  1. lekéri az ERA5-Land total_precipitation mezőt a HELYES időpontra
  2. koszinusz-súlyozott területi átlagot számol
  3. beírja a params.json csapadek_mm_nap tételébe, provenance="mert"

AKKUMULÁCIÓ — ez a legfontosabb sor az egész fájlban:
  Az ERA5-Land csapadéka a nap 00 UTC-jétől halmozódik, és a 00:00-s érték az ELŐZŐ
  nap teljes összege. Ezért az N. nap csapadékát az N+1. nap 00:00-s mezőjéből vesszük,
  nem a 24 óra összegéből. A 24 óra összeadása a valóság sokszorosát adná.
"""

import datetime as dt
import json
import pathlib
import sys
import tempfile
import zipfile

import cdsapi
import numpy as np
import xarray as xr

import maszk

# A doboz befoglaló téglalapja: É, Ny, D, K
BBOX = [49.1, 16.0, 45.7, 22.9]
KESES_NAP = 6          # az ERA5-Land kb. 5 napot késik; 6 biztonságos
NC = "era5land_precip.nc"
PARAMS = pathlib.Path("params.json")


def kert_nap() -> dt.date:
    if len(sys.argv) > 1:
        return dt.date.fromisoformat(sys.argv[1])
    return dt.date.today() - dt.timedelta(days=KESES_NAP)


def letolt(nap: dt.date) -> None:
    """Az N. nap összegét az N+1. nap 00:00-s mezője hordozza."""
    kov = nap + dt.timedelta(days=1)
    cdsapi.Client().retrieve("reanalysis-era5-land", {
        "variable": ["total_precipitation"],
        "year": f"{kov:%Y}", "month": f"{kov:%m}", "day": [f"{kov:%d}"],
        "time": ["00:00"],
        "area": BBOX,
        "data_format": "netcdf",
    }, NC)


def megnyit(path: str) -> xr.Dataset:
    """A CDS a 'netcdf' kérésre is adhat ZIP-et, benne a tényleges .nc-vel.
       A kiterjesztés nem árulja el — a fájl első bájtjai igen."""
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":
        konyvtar = tempfile.mkdtemp()
        with zipfile.ZipFile(path) as z:
            ncs = [n for n in z.namelist() if n.endswith(".nc")]
            if not ncs:
                raise RuntimeError(f"A ZIP nem tartalmaz .nc fájlt: {z.namelist()}")
            print(f"  (ZIP-et kaptunk, kibontva: {', '.join(ncs)})")
            utak = [z.extract(n, konyvtar) for n in ncs]
        return xr.open_mfdataset(utak, combine="by_coords") if len(utak) > 1 \
            else xr.open_dataset(utak[0])
    if magic[:4] == b"GRIB":
        raise RuntimeError("GRIB-et kaptunk netCDF helyett — a kérésben "
                           "data_format: netcdf legyen, és telepítsd: pip install cfgrib")
    return xr.open_dataset(path)


def terulet_atlag(path: str) -> float:
    """mm/nap, koszinusz-súlyozott átlag. Az ERA5 tp mértékegysége MÉTER."""
    ds = megnyit(path)
    valto = "tp" if "tp" in ds else list(ds.data_vars)[0]
    print(f"  változó: {valto}, dimenziók: {dict(ds[valto].sizes)}")
    da = ds[valto]
    for d in ("valid_time", "time", "number", "expver"):
        if d in da.dims:
            da = da.isel({d: 0})
    lat_nev = "latitude" if "latitude" in da.coords else "lat"
    lon_nev = "longitude" if "longitude" in da.coords else "lon"
    atlag_m, cellak, terulet = maszk.sulyozott_atlag(da, lat_nev, lon_nev)
    print(f"  maszk: {cellak} cella, {terulet:,.0f} km²")
    return atlag_m * 1000.0


def beir(mm: float, nap: dt.date) -> None:
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    # Kölön mező: három forrás van a csapadékra (OMSZ földi, IMERG
    # műholdas, ERA5 reanalízis), és mindehőrom külön értékes.
    p["csapadek_era5_mm_nap"] = {
        "ertek": round(mm, 2),
        "provenance": "muholdas",
        "forras": f"ERA5-Land total_precipitation, {nap.isoformat()}, "
                  f"területsúlyozott átlag országhatár-maszkkal (Copernicus, CC-BY)",
        "kor_ora": (dt.date.today() - nap).days * 24,
        "datum": nap.isoformat(),
        "figyelmeztetes": "Országhatár-maszkkal súlyozva. A doboz jelenleg Magyarország, "
                          "nem a teljes vízgyűjtő.",
    }
    p["_ervenyes"] = nap.isoformat()
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    nap = kert_nap()
    letolt(nap)
    mm = terulet_atlag(NC)
    beir(mm, nap)
    print(f"{nap}: {mm:.2f} mm/nap területi átlag — beírva a params.json-be")
    print("Ezután futtasd: python3 fetch_data.py")
