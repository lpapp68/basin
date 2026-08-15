#!/usr/bin/env python3
"""
era5_et.py — FÜGGETLEN párolgásbecslés az ERA5-Land reanalízisből.

MIÉRT
A mérlegben a műholdas (LSA SAF) párolgás és a maradéktag között tartósan
nagy az eltérés. Két gyanúsítottat már kizártunk méréssel:

  - a gyökérzóna (80 cm) napi készletfogyása 60–120 m³/s — a hiány 5–10%-a
  - a talajvíz emelkedik, nem süllyed, tehát nem forrás, hanem nyelő

Marad a harmadik: maga a műholdas becslés. Az LSA SAF a felszín sugárzási
mérlegéből számol, és ez ismerten FELÜLBECSÜLHET száraz, kiszáradt felszínen.
Ezt csak egy független becsléssel lehet ellenőrizni.

MIT AD AZ ERA5-LAND
Az ECMWF reanalízise: modell + asszimilált megfigyelés, 9 km-es rács,
órás felbontás. Teljesen más módszertan, mint a műholdas sugárzási mérleg —
épp ezért alkalmas keresztellenőrzésre.

  total_evaporation (m vízoszlop, NEGATÍV a felszínről elfelé)

FIGYELEM: öt-hat napos késéssel jön. Visszamenőleges összevetésre való,
nem napi működésre.

Futtatás:  python era5_et.py 2026-08-13
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

DOBOZ = [49.1, 16.0, 45.7, 22.9]        # É, Ny, D, K
GYORSITO = pathlib.Path("era5_et")


def letolt(nap: dt.date) -> str:
    GYORSITO.mkdir(exist_ok=True)
    ut = GYORSITO / f"et-{nap:%Y-%m-%d}.nc"
    if ut.exists():
        return str(ut)
    cdsapi.Client().retrieve("reanalysis-era5-land", {
        "variable": ["total_evaporation"],
        "year": f"{nap:%Y}", "month": f"{nap:%m}", "day": f"{nap:%d}",
        # Az ERA5 az akkumulált mennyiséget a nap végén adja: a 00:00-s
        # érték az ELŐZŐ nap összege, ezért a következő nap 00 óráját kérjük.
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": DOBOZ,
        "data_format": "netcdf",
    }, str(ut))
    return str(ut)


def napi_et(nap: dt.date) -> float:
    """Országos átlag, mm/nap. Pozitív érték = elpárolgott víz."""
    # A CDS huszágon ZIP-ben ad vissza, a kiterjesztéstől függetlenül.
    # A fájl első bájtjai arulják el, mi érkezett valójában.
    ut = letolt(nap)
    with open(ut, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":
        konyvtar = tempfile.mkdtemp()
        with zipfile.ZipFile(ut) as z:
            ncs = [n for n in z.namelist() if n.endswith(".nc")]
            utak = [z.extract(n, konyvtar) for n in ncs]
        d = (xr.open_mfdataset(utak, combine="by_coords") if len(utak) > 1
             else xr.open_dataset(utak[0]))
    else:
        d = xr.open_dataset(ut)
    valt = next(v for v in d.data_vars if v.lower() in ("e", "tp", "total_evaporation"))
    mezo = d[valt]

    # Az ERA5-Land akkumulál: a napi utolsó óra adja a teljes napi összeget.
    # A mennyiség méterben van és NEGATÍV (a felszínről elfelé mutat).
    ido = [c for c in ("valid_time", "time") if c in mezo.dims]
    if ido:
        mezo = mezo.isel({ido[0]: -1})

    atl, _, _ = maszk.sulyozott_atlag(mezo, "latitude", "longitude")
    return float(-atl) * 1000.0          # m -> mm, előjel megfordítva


def main():
    nap = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=7))
    ertek = napi_et(nap)

    T = 93030 * 1e6
    m3s = ertek / 1000 * T / 86400
    print(f"{nap}: ERA5-Land párolgás {ertek:.2f} mm/nap = {m3s:.0f} m³/s")

    # A params.json-be írjuk, hogy a lap harmadik becslésként mutathassa.
    # Ez a keresztellenőrzés: ha a két, teljesen eltérő módszertanú becslés
    # egyezik, akkor a párolgás nem a mérleg hibaforrása.
    p = json.loads(pathlib.Path("params.json").read_text(encoding="utf-8"))
    p["parolgas_era5_mm_nap"] = {
        "ertek": round(ertek, 2),
        "datum": str(nap),
        "provenance": "modellezett",
        "forras": ("ECMWF ERA5-Land reanalízis (total_evaporation), 9 km-es rács, "
                   "területsúlyozott átlag országhatár-maszkkal"),
        "figyelmeztetes": ("Reanalízis: modell asszimilált megfigyeléssel, nem közvetlen "
                           "mérés. Öt-hat napos késéssel érkezik, ezért visszamenőleges "
                           "keresztellenőrzésre való, nem napi működésre."),
    }
    pathlib.Path("params.json").write_text(
        json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    muh = p.get("parolgas_mm_nap") or {}
    if muh.get("datum") == str(nap):
        m = muh["ertek"]
        print(f"       LSA SAF műholdas   {m:.2f} mm/nap = {m/1000*T/86400:.0f} m³/s")
        print(f"       eltérés            {ertek - m:+.2f} mm/nap "
              f"({(ertek/m - 1)*100:+.0f}%)")


if __name__ == "__main__":
    main()
