#!/usr/bin/env python3
"""
vizapi.py — az OVF hivatalos nyílt adat-API-ja (data.vizugy.hu).

MIÉRT EZ, ÉS MIÉRT MOST
Eddig a vizugy.hu HTML-tábláit elemeztük: törékeny a mi oldalunkon, fölösleges
terhelés az övékén. Az OVF maga javasolta ezt a felületet — vagyis pontosan az
történt, amit az adatigénylő levél 2. pontjában kértünk.

FELÉPÍTÉS
  1. token   GET  data.vizugy.hu/AuthApi/auth/token       (nyilvános, jelszó nélkül)
  2. állomás GET  vmservice.vizugy.hu/vraquery/Vra/InternetVmo/{tipus}/false
  3. idősor  POST vmservice.vizugy.hu/vraquery/TS/TsShortList

Az Origin fejléc kötelező: a szolgáltatás enélkül 403-at ad.
A token nagyjából negyed óráig él, a lejáratot a JWT `exp` mezője mondja meg.

ÁLLOMÁSTÍPUSOK              ADATFAJTA-KÓDOK
  11  felszíni vízmérce       68  vízállás (cm)      299  talajnedvesség (%)
  12  hidrometeorológiai      87  vízhozam (m³/s)     69  talajvízállás (cm)
  13  felszín alatti          85  vízhő (°C)          70  rétegvízszint (m)
  14  egyéb                   71  csapadékösszeg      75  hóvastagság

AMIT EZ AD A KORÁBBIHOZ KÉPEST
  - negyedórás felbontás az órás helyett
  - az LKV a törzsadatból jön, nem adatlap-elemzésből
  - talajvíz és rétegvíz: eddig egyáltalán nem volt
"""

import datetime as dt
import json
import urllib.request

TOKEN_URL = "https://data.vizugy.hu/AuthApi/auth/token"
API = "https://vmservice.vizugy.hu/vraquery/"
FEJ = {"Origin": "https://data.vizugy.hu",
       "Referer": "https://data.vizugy.hu/",
       "User-Agent": "equora-basin/2.4 (+https://basin.equora.institute)"}

VIZALLAS, VIZHOZAM, VIZHO = 68, 87, 85
CSAPADEK, TALAJNEDV, TALAJVIZ, RETEGVIZ = 71, 299, 69, 70

_token = {"ertek": None, "lejar": None}


def token() -> str:
    """Gyorsítótárazott token. A JWT exp mezőjéből tudjuk, meddig él."""
    most = dt.datetime.now(dt.timezone.utc)
    if _token["ertek"] and _token["lejar"] and most < _token["lejar"]:
        return _token["ertek"]
    r = urllib.request.Request(TOKEN_URL, headers=FEJ)
    t = json.loads(urllib.request.urlopen(r, timeout=45).read())["access_token"]
    import base64
    resz = t.split(".")[1]
    resz += "=" * (-len(resz) % 4)
    exp = json.loads(base64.urlsafe_b64decode(resz))["exp"]
    _token["ertek"] = t
    # egy perc ráhagyás, hogy egy hosszabb kérés közben ne járjon le
    _token["lejar"] = dt.datetime.fromtimestamp(exp, dt.timezone.utc) - dt.timedelta(minutes=1)
    return t


def _hivas(ut: str, adat=None):
    fej = dict(FEJ, Authorization="Bearer " + token())
    test = None
    if adat is not None:
        fej["Content-Type"] = "application/json"
        test = json.dumps(adat).encode()
    r = urllib.request.Request(API + ut, data=test, headers=fej)
    return json.loads(urllib.request.urlopen(r, timeout=90).read())


def allomasok(tipus: int = 11) -> list:
    """Törzsadat: Tsz, Nev, Lat/Lon, LKV, Fkm, Mdr (mederfenék), üzemel-e."""
    return _hivas(f"Vra/InternetVmo/{tipus}/false")


def idosor(torzsszamok, kod: int, kezdet: dt.datetime, veg: dt.datetime) -> dict:
    """{törzsszám: [(idő, érték), ...]} — a válasz UTC-ben jön."""
    if isinstance(torzsszamok, int):
        torzsszamok = [torzsszamok]
    v = _hivas("TS/TsShortList", {
        "torzsszamList": list(torzsszamok),
        "adatFajtaKod": kod,
        "adatTipusKod": 100,
        "startTime": kezdet.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": veg.strftime("%Y-%m-%d %H:%M:%S"),
        "valueFilter": "Relativ",     # a vízállás a mérce nullpontjához képest
        "amKodFilter": [0],
    })
    ki = {}
    for sor in v or []:
        pontok = [(dt.datetime.fromisoformat(p["UTCTime"].replace("Z", "+00:00")),
                   p["Adat"]) for p in (sor.get("TsItemList") or []) if p.get("Adat") is not None]
        ki[sor["ItemId"]] = pontok
    return ki


def utolso(torzsszamok, kod: int, orak: int = 48) -> dict:
    """A legfrissebb érték mércénként: {törzsszám: (idő, érték)}."""
    most = dt.datetime.now(dt.timezone.utc)
    d = idosor(torzsszamok, kod, most - dt.timedelta(hours=orak), most + dt.timedelta(hours=2))
    return {k: v[-1] for k, v in d.items() if v}


if __name__ == "__main__":
    a = allomasok(11)
    print(f"felszíni vízmércék: {len(a)}")
    nevek = {"Nagybajcs", "Budapest", "Paks", "Mohács", "Szeged"}
    minta = {x["Nev"].strip(): x for x in a if x["Nev"].strip() in nevek}
    for n, x in minta.items():
        print(f"  {n:<12} Tsz {x['Tsz']:>6}  LKV {x.get('LKV')}  fkm {x.get('Fkm')}")
    tsz = [x["Tsz"] for x in minta.values()]
    for kod, cimke in ((VIZALLAS, "vízállás cm"), (VIZHOZAM, "vízhozam m³/s"), (VIZHO, "vízhő °C")):
        u = utolso(tsz, kod)
        print(f"\n{cimke}:")
        for n, x in minta.items():
            p = u.get(x["Tsz"])
            print(f"  {n:<12} {p[1] if p else '—'}   {p[0].strftime('%m-%d %H:%M') if p else ''}")
