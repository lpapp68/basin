#!/usr/bin/env python3
"""
grace.py — a 2. kártya idősora: mikor mennyit csökkent a vízkészlet.

Futtatás:  python grace.py

MIÉRT KELL
A 2. kártya eddig egyetlen számot mutatott ("−18,4 km³"). Az viszont nem mondja meg,
hogy folyamatos csökkenésről van-e szó, vagy egyetlen rossz évről — pedig a kettő
teljesen mást jelent. A GRACE és GRACE-FO 2002 óta ad havi vízkészlet-anomáliát,
ebből huszonnégy éves görbe rajzolható.

AMIT A GÖRBÉTŐL VÁRUNK
Nem a pillanatnyi hiányt. Azt, hogy egy-egy aszály után visszaáll-e a korábbi szint,
vagy lépcsőzetesen lejjebb marad. A második a komolyabb állítás, és csak idősoron látszik.

MIT MÉR A GRACE
A teljes vízkészlet-anomáliát (TWS): talajnedvesség, felszín alatti víz, felszíni víz,
hó és jég EGYÜTT, egy sokéves átlaghoz képest, vízoszlop-centiméterben.
Nem abszolút készlet — ANOMÁLIA. Ezért mutat a kártya hiányt, nem telítettséget.

KORLÁTOK, AMIKET A LAPNAK KI KELL ÍRNIA
  - felbontás ~300 km: Magyarország néhány rácscellányi, tehát a határ elmosódik
  - havi, 1–2 hónapos késéssel: élő panelre alkalmatlan, trendre jó
  - 2017 júniusa és 2018 májusa között RÉS van a GRACE és a GRACE-FO között

ELŐFELTÉTEL
  ~/.netrc:  machine urs.earthdata.nasa.gov login <FELHASZNÁLÓ> password <JELSZÓ>
  pip install earthaccess
  Az Earthdata profilban engedélyezni kell a PO.DAAC hozzáférést.
"""

import json
import pathlib
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import xarray as xr

import maszk

# A mascon rácsos termék. A verziószám időnként változik, ezért NEM írjuk be fixen:
# a keresés a rövid névre megy, és kiírja, mit talált.
ROVID_NEV = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
TARTALEK_NEVEK = [
    "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.1_V3",
    "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06_V2",
]
BBOX = (16.0, 45.7, 22.9, 49.1)      # Ny, D, K, É
LETOLTES = pathlib.Path("grace")
PARAMS = pathlib.Path("params.json")


def letolt():
    import earthaccess
    earthaccess.login(strategy="netrc")
    for nev in [ROVID_NEV] + TARTALEK_NEVEK:
        t = earthaccess.search_data(short_name=nev, bounding_box=BBOX, count=2000)
        if t:
            print(f"  adatkészlet: {nev} ({len(t)} szemcse)")
            LETOLTES.mkdir(exist_ok=True)
            return earthaccess.download(t, str(LETOLTES))
    raise RuntimeError("Nem találtam GRACE mascon adatkészletet. Nézd meg a PO.DAAC "
                       "keresőjében az aktuális short_name-et, és írd át a fájl tetején.")


def sorozat(utak):
    # A mascon termék egyetlen fájlban hozza a teljes idősort, ezért nem kell
    # open_mfdataset (és vele a dask). Több fájl esetén kézzel fűzzük össze.
    utak = sorted(utak)
    if len(utak) == 1:
        ds = xr.open_dataset(utak[0])
    else:
        ds = xr.concat([xr.open_dataset(u) for u in utak], dim="time").sortby("time")
    valto = next((v for v in ("lwe_thickness", "lwe_thickness_cri", "lwe")
                  if v in ds.data_vars), None)
    if valto is None:
        raise RuntimeError(f"Nem találom a vastagság-mezőt. Elérhető: {list(ds.data_vars)}")

    # A GRACE 0–360 fokos hosszúságon van; a maszk −180…180-at vár.
    if float(ds.lon.max()) > 180:
        ds = ds.assign_coords(lon=(((ds.lon + 180) % 360) - 180)).sortby("lon")

    da = ds[valto].sel(lat=slice(BBOX[1] - 1, BBOX[3] + 1),
                       lon=slice(BBOX[0] - 1, BBOX[2] + 1))
    lat, lon = da.lat.values, da.lon.values
    m = maszk.maszk(lat, lon)
    ter = maszk.cella_terulet_km2(lat, lon)
    suly = np.where(m, ter, 0.0)
    if suly.sum() == 0:
        raise RuntimeError("A maszk nem fed le egyetlen GRACE-cellát sem.")

    ki = []
    ertekek = da.values                       # (time, lat, lon)
    for i, t in enumerate(da.time.values):
        mezo = ertekek[i]
        jo = np.isfinite(mezo) & m
        if not jo.any():
            continue
        # cm vízoszlop → km³ a maszkolt területre
        cm = float(np.average(mezo[jo], weights=ter[jo]))
        km3 = cm / 100.0 * float(ter[m].sum()) * 1e6 / 1e9
        ki.append({"honap": str(np.datetime_as_string(t, unit="M")),
                   "cm": round(cm, 2), "km3": round(km3, 2)})
    return ki, float(ter[m].sum())


def main():
    utak = letolt()
    sor, terulet = sorozat(utak)
    if not sor:
        raise RuntimeError("Üres idősor.")

    elso, utolso = sor[0], sor[-1]
    # Tíz év alatti trend: a legutóbbi 120 hónapra illesztett egyenes meredeksége.
    utolso120 = sor[-120:]
    x = np.arange(len(utolso120), dtype=float)
    y = np.array([r["km3"] for r in utolso120])
    meredekseg = float(np.polyfit(x, y, 1)[0]) * 12.0    # km³/év

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["keszlet_idosor"] = {
        "provenance": "mert",
        "forras": "NASA/JPL GRACE és GRACE-FO mascon (PO.DAAC), országhatár-maszkkal",
        "egyseg": "km³ anomália a termék sokéves átlagához képest",
        "terulet_km2": round(terulet),
        "kezdet": elso["honap"], "veg": utolso["honap"],
        "pontok": len(sor),
        "trend_km3_ev": round(meredekseg, 2),
        "figyelmeztetes": ("ANOMÁLIA, nem abszolút készlet: a nulla a termék sokéves "
                           "átlagát jelenti, nem a teli medencét. Felbontás kb. 300 km, "
                           "havi, 1–2 hónapos késéssel. 2017 közepe és 2018 közepe között "
                           "adathiány a két műholdpár között."),
        "sorozat": sor,
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(sor)} havi pont: {elso['honap']} – {utolso['honap']}")
    print(f"  maszkolt terület: {terulet:,.0f} km²")
    print(f"  legutóbbi érték:  {utolso['km3']:+.1f} km³ ({utolso['cm']:+.1f} cm vízoszlop)")
    print(f"  tízéves trend:    {meredekseg:+.2f} km³/év")
    print("\nEzután: python fetch_data.py")


if __name__ == "__main__":
    main()
