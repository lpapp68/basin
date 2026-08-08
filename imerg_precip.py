#!/usr/bin/env python3
"""
imerg_precip.py — napi csapadék néhány órás késéssel, az ERA5-Land 5 napja helyett.

Futtatás:  source ~/cds-env/bin/activate && python imerg_precip.py [YYYY-MM-DD]

Termék: GPM IMERG Early Precipitation L3, napi, 0.1 fok (GPM_3IMERGDE, V07).
Ez műholdas becslés, nem reanalízis — más hibaszerkezettel, mint az ERA5-Land.
Ezért a params.json-be beírja, MELYIKET használtuk; a kettőt nem keverjük.

ELŐFELTÉTELEK
  1. NASA Earthdata Login fiók:  https://urs.earthdata.nasa.gov
  2. ~/.netrc:
        machine urs.earthdata.nasa.gov login <FELHASZNÁLÓ> password <JELSZÓ>
     majd: chmod 600 ~/.netrc
  3. EZ A LÉPÉS KIMARAD A LEGTÖBB LEÍRÁSBÓL: az Earthdata profilodban
     (Applications -> Authorized Apps) engedélyezni kell a
     "NASA GESDISC DATA ARCHIVE" alkalmazást. Enélkül a letöltés
     némán átirányít egy bejelentkező oldalra, és HTML-t ment .nc4 néven.
  4. pip install earthaccess

Az earthaccess azért kell, hogy ne kelljen fájlnevet és verziószámot kitalálni
(a V07A/V07B utótag időről időre változik) — a keresés adja vissza az URL-t.
"""

import datetime as dt
import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import earthaccess
import numpy as np
import xarray as xr

import maszk

BBOX = {"lat_min": 45.7, "lat_max": 49.1, "lon_min": 16.0, "lon_max": 22.9}
TERMEK = "GPM_3IMERGDE"      # Early, napi. A Final (GPM_3IMERGDF) pontosabb, de hónapokat késik.
VERZIO = "07"
KESES_NAP = 1
PARAMS = pathlib.Path("params.json")
LETOLTES = pathlib.Path("imerg")


def kert_nap() -> dt.date:
    if len(sys.argv) > 1:
        return dt.date.fromisoformat(sys.argv[1])
    return dt.date.today() - dt.timedelta(days=KESES_NAP)


def letolt(nap: dt.date) -> str:
    earthaccess.login(strategy="netrc")
    talalat = earthaccess.search_data(
        short_name=TERMEK, version=VERZIO,
        temporal=(nap.isoformat(), nap.isoformat()),
        bounding_box=(BBOX["lon_min"], BBOX["lat_min"], BBOX["lon_max"], BBOX["lat_max"]),
    )
    if not talalat:
        raise RuntimeError(f"Nincs {TERMEK} találat {nap}-ra. Az Early termék néhány "
                           f"órás késéssel jön — próbáld a tegnapi nappal.")
    LETOLTES.mkdir(exist_ok=True)
    utak = earthaccess.download(talalat[:1], str(LETOLTES))
    return utak[0]


def terulet_atlag(path: str) -> float:
    ds = xr.open_dataset(path)
    nev = next((v for v in ("precipitation", "precipitationCal", "precip")
                if v in ds.data_vars), None)
    if nev is None:
        raise RuntimeError(f"Nem találom a csapadék változót. Elérhető: {list(ds.data_vars)}")
    da = ds[nev]
    if "time" in da.dims:
        da = da.isel(time=0)
    egyseg = da.attrs.get("units", "?")

    # Az IMERG rácsa lon-major, ezért névvel vágunk, nem tengelysorrenddel.
    lat = "lat" if "lat" in da.coords else "latitude"
    lon = "lon" if "lon" in da.coords else "longitude"
    da = da.where((da[lat] >= BBOX["lat_min"]) & (da[lat] <= BBOX["lat_max"]) &
                  (da[lon] >= BBOX["lon_min"]) & (da[lon] <= BBOX["lon_max"]), drop=True)

    # Az IMERG hiányzó cellái -9999.9-cel jönnek. Ha ez bekerül az átlagba,
    # csendben lehúzza — ezért a negatívokat kidobjuk, és megszámoljuk őket.
    hianyzo = int((da < 0).sum())
    da = da.where(da >= 0)
    cellak = int(da.notnull().sum())

    atlag, cellak_maszk, terulet = maszk.sulyozott_atlag(da, lat, lon)
    print(f"  maszk: {cellak_maszk} cella, {terulet:,.0f} km²")
    print(f"  {nev} ({egyseg}) a téglalapban: {cellak} cella"
          + (f", {hianyzo} hiányzó kidobva" if hianyzo else ""))
    print(f"  medián {float(da.median()):.2f} · max {float(da.max()):.2f} · "
          f"1 mm felett {float((da > 1).mean()) * 100:.0f}%")
    # A napi termék egysége mm/nap — ha mm/óra jönne, itt derül ki a nagyságrendből.
    if (da.attrs.get("units") or "").lower().startswith("mm/h"):
        atlag *= 24.0
    return atlag


def beir(mm: float, nap: dt.date) -> None:
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["csapadek_mm_nap"] = {
        "ertek": round(mm, 2),
        "provenance": "muholdas",
        "forras": f"GPM IMERG Early napi ({TERMEK} V{VERZIO}), {nap.isoformat()}, "
                  f"területsúlyozott átlag országhatár-maszkkal",
        "kor_ora": (dt.date.today() - nap).days * 24,
        "datum": nap.isoformat(),
        "figyelmeztetes": "Műholdas becslés, nem reanalízis. Az Early futás gyors, de "
                          "kevésbé pontos, mint az ERA5-Land vagy az IMERG Final. "
                          "Országhatár-maszkkal súlyozva.",
        "hivatkozas": "GPM IMERG, NASA GES DISC",
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    nap = kert_nap()
    f = letolt(nap)
    mm = terulet_atlag(f)
    beir(mm, nap)
    print(f"{nap}: {mm:.2f} mm/nap csapadék (IMERG Early) — beírva a params.json-be")
    print("Ezután: python lsasaf_et.py " + nap.isoformat() + " && python fetch_data.py")
