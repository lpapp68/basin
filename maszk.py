#!/usr/bin/env python3
"""
maszk.py — a doboz valódi alakja, a téglalap helyett.

Eddig a csapadékot és a párolgást egy [45.7–49.1 É, 16.0–22.9 K] TÉGLALAPRA
átlagoltuk. Abban benne van Szlovákia déli sávja, Ausztria keleti pereme,
a Vajdaság és Erdély nyugati széle — összesen a téglalap területének kb. harmada
olyan terület, ami nincs a dobozban.

Ez a modul kivágja a valódi határvonalat, és területarányosan súlyoz.
Nincs geopandas, nincs shapely: sugárvetéses pont-a-poligonban, numpy-ban.

Használat:
    import maszk
    atlag = maszk.sulyozott_atlag(da, "lat", "lon")     # mm/nap

A maszk gridenként egyszer számolódik és fájlba kerül (maszk_cache/), mert
0,05 fokos rácson néhány másodperc, és minden nap ugyanaz.
"""

import hashlib
import json
import pathlib
import urllib.request

import numpy as np

FORRAS = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          "master/geojson/ne_10m_admin_0_countries.geojson")
HATAR = pathlib.Path("hatar.geojson")
CACHE = pathlib.Path("maszk_cache")
FOLD_SUGAR_KM = 6371.0088

# Melyik ország(ok) alkotják a dobozt. A 'mdb' dobozhoz ezt a listát kell bővíteni,
# vagy vízgyűjtő-poligonra váltani (HydroSHEDS/HydroBASINS).
ORSZAGOK = ["Hungary"]


def _letolt_hatar() -> dict:
    if not HATAR.exists():
        print("  határvonal letöltése (Natural Earth, ~13 MB, egyszeri)...")
        with urllib.request.urlopen(FORRAS, timeout=180) as r:
            HATAR.write_bytes(r.read())
    return json.loads(HATAR.read_text(encoding="utf-8"))


def _gyuruk(orszagok=None) -> list[tuple[np.ndarray, bool]]:
    """(gyűrű, lyuk-e) párok listája a kért országokra."""
    orszagok = orszagok or ORSZAGOK
    d = _letolt_hatar()
    ki = []
    for f in d["features"]:
        nev = f["properties"].get("NAME") or f["properties"].get("ADMIN")
        if nev not in orszagok:
            continue
        g = f["geometry"]
        darabok = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for darab in darabok:
            for i, gyuru in enumerate(darab):
                ki.append((np.asarray(gyuru, dtype=float), i > 0))
    if not ki:
        raise RuntimeError(f"Nem találom a határvonalat: {orszagok}")
    return ki


def _pont_a_poligonban(x: np.ndarray, y: np.ndarray, gyuru: np.ndarray) -> np.ndarray:
    """Sugárvetés. x, y lapos tömbök; gyuru Nx2 (lon, lat)."""
    px, py = gyuru[:, 0], gyuru[:, 1]
    qx, qy = np.roll(px, -1), np.roll(py, -1)
    benn = np.zeros(x.shape, dtype=bool)
    for x1, y1, x2, y2 in zip(px, py, qx, qy):
        if y1 == y2:
            continue
        atmetsz = (y1 > y) != (y2 > y)
        # Csak ott osztunk, ahol a szakasz átmetszi a vízszintest.
        with np.errstate(invalid="ignore", divide="ignore"):
            hatar_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        benn ^= atmetsz & (x < hatar_x)
    return benn


def maszk(lat: np.ndarray, lon: np.ndarray, orszagok=None) -> np.ndarray:
    """2D bool maszk (lat × lon). Gyorsítótárazva, mert rácsonként állandó."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    kulcs = hashlib.sha1(
        (lat.tobytes() + lon.tobytes() + ",".join(orszagok or ORSZAGOK).encode())
    ).hexdigest()[:16]
    CACHE.mkdir(exist_ok=True)
    utvonal = CACHE / f"{kulcs}.npy"
    if utvonal.exists():
        return np.load(utvonal)

    LON, LAT = np.meshgrid(lon, lat)
    x, y = LON.ravel(), LAT.ravel()
    benn = np.zeros(x.shape, dtype=bool)
    for gyuru, lyuk in _gyuruk(orszagok):
        b = _pont_a_poligonban(x, y, gyuru)
        benn = benn & ~b if lyuk else benn | b
    m = benn.reshape(LAT.shape)
    np.save(utvonal, m)
    return m


def cella_terulet_km2(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Cellánkénti valódi terület. Ez a helyes súly — nem a puszta cos(lat)."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    dlat = abs(float(lat[1] - lat[0]))
    dlon = abs(float(lon[1] - lon[0]))
    # Gömbi öv magassága: R^2 * dlon * (sin(lat+dlat/2) - sin(lat-dlat/2))
    sav = (FOLD_SUGAR_KM ** 2 * np.deg2rad(dlon)
           * (np.sin(np.deg2rad(lat + dlat / 2)) - np.sin(np.deg2rad(lat - dlat / 2))))
    return np.abs(np.repeat(sav[:, None], len(lon), axis=1))


def sulyozott_atlag(da, lat_nev="lat", lon_nev="lon", orszagok=None):
    """Területsúlyozott átlag a maszkolt cellákon.
       Visszaad: (átlag, cellák száma, lefedett terület km²)."""
    lat, lon = da[lat_nev].values, da[lon_nev].values
    m = maszk(lat, lon, orszagok)
    ter = cella_terulet_km2(lat, lon)

    ertek = da.values
    while ertek.ndim > 2:
        ertek = ertek[0]
    # A tömb tengelysorrendje lehet (lat, lon) vagy (lon, lat) — a formából dől el.
    if ertek.shape != m.shape and ertek.T.shape == m.shape:
        ertek = ertek.T

    jo = m & np.isfinite(ertek)
    if not jo.any():
        raise RuntimeError("A maszk egyetlen cellát sem fed le — rossz rács vagy ország.")
    suly = ter[jo]
    return (float(np.average(ertek[jo], weights=suly)),
            int(jo.sum()), float(suly.sum()))


if __name__ == "__main__":
    # Önteszt: a maszkolt terület adja-e vissza az ország valódi területét.
    for lepes in (0.1, 0.05):
        lat = np.arange(45.5, 49.2, lepes)
        lon = np.arange(15.9, 23.0, lepes)
        m = maszk(lat, lon)
        t = cella_terulet_km2(lat, lon)
        teglalap = t.sum()
        maszkolt = t[m].sum()
        print(f"{lepes}° rács: maszkolt {maszkolt:,.0f} km² "
              f"(hivatalos 93 030) · téglalap {teglalap:,.0f} km² "
              f"· a téglalap {maszkolt / teglalap:.0%}-a")
