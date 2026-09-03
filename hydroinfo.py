#!/usr/bin/env python3
"""
hydroinfo.py — vízállás-előrejelzés az OVF Országos Vízjelző Szolgálatától.

MIÉRT
A lap minden száma eddig a múltról szólt. Az extrapolációt szándékosan
elutasítottuk: a GRACE anomália, a hidrológiai rendszer visszacsatol, és egy
egyenes vonal meghosszabbítása félrevezetne.

Ez viszont más: az OVSZ hivatalos, modellezett előrejelzése, saját
bizonytalansági sávval. Nem a mi becslésünk.

MIT AD
Hatóránként egy pont, vízállás cm-ben, hozzá egy `conf` mező — a
bizonytalanság, ami az idővel nő (Budapesten +6 órára ±0,6 cm, +18 órára
±1,7). A sáv maga is adat: megmutatja, meddig megbízható az előrejelzés.

MIT NEM AD
Vízhozamot. Az előrejelzés cm-ben van; a mérleghez m³/s kellene, és a
vízhozamgörbe nincs a nyilvános adatban. Ezért ez a modul NEM ír a mérlegbe,
csak külön panelbe: a változás iránya és üteme önmagában is információ.

HOZZÁFÉRÉS
Egyedi token, amit az OVF Adattári Osztálya ad. A HYDROINFO_TOKEN környezeti
változóból olvassuk — soha nem kerül a repóba.

  https://hydroinfo.hu/WSCSS/ovszws/api.php?token=…&view=getfc&statid=…&varid=4

Futtatás:  HYDROINFO_TOKEN=… python hydroinfo.py
"""

import datetime as dt
import json
import os
import pathlib
import ssl
import sys
import urllib.parse
import urllib.request

API = "https://hydroinfo.hu/WSCSS/ovszws/api.php"
FEJ = {"User-Agent": "equora-basin/2.6 (+https://basin.equora.institute)"}
PARAMS = pathlib.Path("params.json")
VARID_VIZALLAS = 4


def _ssl_kontextus():
    """A hydroinfo.hu tanúsítványát a Microsec e-Szignó adta ki — ez a magyar
    hitelesítő nincs benne sem a certifi Mozilla-készletében, sem a
    macOS-Python OpenSSL-készletében. A repóban tartott láncot adjuk hozzá."""
    ctx = ssl.create_default_context()
    lanc = pathlib.Path(__file__).parent / "tanusitvanyok" / "vizugy-lanc.pem"
    if lanc.exists():
        try:
            ctx.load_verify_locations(cafile=str(lanc))
        except Exception:
            pass
    return ctx


SSL_CTX = _ssl_kontextus()

# A megjelenített szelvények. A Duna két vége adja a fő átfolyást, a többi
# a mérleg NYITOTT FALAIT jelzi előre — azokat a folyókat, amelyek hozama
# ma a maradéktagban jelenik meg.
SZELVENYEK = [
    (6,   "Budapest",        "Duna",         "a főváros szelvénye"),
    (128, "Mohács",          "Duna",         "az ország alsó kapuja"),
    (125, "Szolnok",         "Tisza",        "a Tisza középső szakasza"),
    (61,  "Hidasnémeti",     "Hernád",       "nyitott fal: Szlovákia felől"),
    (48,  "Ágerdőmajor",     "Kraszna",      "nyitott fal: Románia felől"),
    (99,  "Sarkad-Malomfok", "Fekete-Körös", "nyitott fal: Románia felől"),
    (92,  "Berettyóújfalu",  "Berettyó",     "nyitott fal: Románia felől"),
]


def _keres(view, **kw):
    token = os.environ.get("HYDROINFO_TOKEN", "").strip()
    if not token:
        raise SystemExit("Hiányzik a HYDROINFO_TOKEN környezeti változó.")
    q = urllib.parse.urlencode({"token": token, "view": view, **kw})
    r = urllib.request.Request(f"{API}?{q}", headers=FEJ)
    return json.loads(urllib.request.urlopen(r, timeout=40, context=SSL_CTX).read())


def _lista(d):
    e = d.get("entries") if isinstance(d, dict) else d
    if isinstance(e, dict):
        return list(e.values())
    return e if isinstance(e, list) else [e]


def egy_szelveny(statid, nev):
    """(pontok, hiba). A pontok: [{'ido': ..., 'cm': ..., 'sav': ...}]"""
    try:
        d = _keres("getfc", statid=statid, varid=VARID_VIZALLAS)
    except Exception as e:
        return None, f"{nev}: {e}"

    tetel = _lista(d)
    if not tetel or not isinstance(tetel[0], dict):
        return None, f"{nev}: üres válasz"
    elo = tetel[0].get("forecasts")
    if not isinstance(elo, list):
        # Szerkezet-ellenőrzés: ha a mező eltűnik vagy átnevezik, ne adjunk
        # csendben rossz adatot — az API 2023 óta változatlan, de ez olcsó.
        return None, f"{nev}: hiányzik a 'forecasts' mező (az API szerkezete változhatott)"

    pontok = []
    for x in elo:
        try:
            cm = float(x["value"])
            sav = float(x.get("conf") or 0)
            ido = x["date"]
        except (KeyError, TypeError, ValueError):
            continue
        # Fizikai ésszerűség: a magyar szelvények −400 és +1200 cm között
        # járnak (a nullpont alatt is lehet). Ezen kívül adathiba.
        if not -600 <= cm <= 1500:
            return None, f"{nev}: {cm} cm a várt tartományon kívül"
        pontok.append({"ido": ido, "cm": round(cm, 1), "sav": round(sav, 1)})

    if len(pontok) < 2:
        return None, f"{nev}: csak {len(pontok)} előrejelzési pont"
    return pontok, None


def main():
    sys.stdout.write("OVSZ vízállás-előrejelzés\n")
    ki, hibak = [], []

    for statid, nev, folyo, megj in SZELVENYEK:
        pontok, hiba = egy_szelveny(statid, nev)
        if hiba:
            hibak.append(hiba)
            sys.stdout.write(f"  {nev:<18} — {hiba}\n")
            continue
        # A változás iránya: az első és az utolsó pont különbsége.
        valtozas = pontok[-1]["cm"] - pontok[0]["cm"]
        ki.append({
            "statid": statid, "nev": nev, "folyo": folyo, "megjegyzes": megj,
            "pontok": pontok,
            "valtozas_cm": round(valtozas, 1),
            "orak": len(pontok) * 6,
        })
        sys.stdout.write(f"  {nev:<18} {pontok[0]['cm']:>7.0f} → {pontok[-1]['cm']:>7.0f} cm "
                         f"({valtozas:+.0f}) · {len(pontok)} pont, ±{pontok[-1]['sav']:.1f}\n")

    if not ki:
        raise SystemExit("Egyetlen szelvényre sem érkezett előrejelzés.")

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["elorejelzes"] = {
        "szelvenyek": ki,
        "keszult": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provenance": "modellezett",
        "forras": ("Országos Vízjelző Szolgálat (OVF) hydroinfo API, "
                   "getfc — vízállás-előrejelzés hatóránként"),
        "megjegyzes": ("Ez az OVSZ hivatalos előrejelzése, nem a lap saját "
                       "számítása. A sáv (±) a szolgálat saját bizonytalansági "
                       "becslése, amely az idővel nő."),
        "figyelmeztetes": ("Vízállás, nem vízhozam: a mérlegbe nem számít bele. "
                           "A cm-ből m³/s-ba váltáshoz vízhozamgörbe kellene, "
                           "ami a nyilvános adatban nincs benne."),
        "hibak": hibak,
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(f"\n  {len(ki)} szelvény beírva a params.json-be\n")


if __name__ == "__main__":
    main()
