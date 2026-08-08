# Zenodo — feltöltési terv

**Belső munkaanyag.** A deposit tárgya a `MODSZERTAN.md` (magyar) és a `METHODOLOGY.md`
(angol kivonat); ez a fájl a feltöltés mechanikájáról szól.

---

## A választott út: GitHub–Zenodo összekötés

A repó publikus, ezért a Zenodo minden GitHub-release-nél **a teljes repót archiválja**.
Nincs kézi fájlválogatás, és a verziózás a fejlesztés mellékterméke lesz.

**Beállítás egyszer:**

1. Zenodo → belépés GitHub-fiókkal
2. Settings → GitHub → az `lpapp68/basin` repó kapcsolójának bekapcsolása
3. GitHub → Releases → *Create a new release*, tag: `v1.0.0`
4. A Zenodo néhány percen belül kiadja a DOI-t

**Két DOI keletkezik.** A **koncepció-DOI** mindig a legfrissebb verzióra mutat — ez megy
a levelekbe, a lap forrás-szekciójába és a `MODSZERTAN.md` hivatkozásába. A
**verzió-DOI** egy adott release-re mutat; erre hivatkozik, aki pontosan azt az állapotot
akarja idézni.

---

## A `.zenodo.json` a repó gyökerében

A Zenodo ezt olvassa a metaadatokhoz. Enélkül a repó nevét és leírását veszi át, ami
gyengébb.

```json
{
  "title": "Water balance of the Middle Danube Basin: an open, provenance-labelled monitoring method",
  "upload_type": "software",
  "language": "hun",
  "license": "MIT",
  "creators": [
    { "name": "Papp, László",
      "affiliation": "EQUORA Institute",
      "orcid": "0009-0005-6329-5808" }
  ],
  "keywords": [
    "water balance", "Middle Danube Basin", "Pannonian Basin",
    "evapotranspiration", "GRACE", "data provenance", "drought",
    "open data", "hydrology", "Hungary"
  ],
  "related_identifiers": [
    { "identifier": "https://basin.equora.institute",
      "relation": "isDocumentedBy", "resource_type": "other" }
  ]
}
```

A `description` mezőt a Zenodo felületén érdemes kitölteni, mert HTML-t fogad:
**a `METHODOLOGY.md` Summary bekezdése angolul, alatta a magyar Összefoglalás.**

---

## Hivatkozandó források a `references` mezőben

- Copernicus C3S: ERA5-Land hourly data — CDS DOI
- EUMETSAT LSA SAF: DMETv3, METREF — Trigo et al. (2011), Remote Sensing
- NASA GPM IMERG — GES DISC DOI
- NASA/JPL GRACE és GRACE-FO mascon RL06.3 V4 — PO.DAAC DOI
- OVF Országos Vízjelző Szolgálat — vizugy.hu
- OVF Aszálymonitoring — aszalymonitoring.vizugy.hu
- SHMÚ napi hidrológiai jelentés — shmu.sk
- INHGA napi hidrológiai bulletin — hidro.ro
- Állami Számvevőszék: jelentés a Nemzeti Vízstratégia végrehajtásáról

---

## Amit a repóból ki kell venni a publikussá tétel előtt

**Ellenőrizd, mielőtt a repó publikus lesz:**

- `.netrc`, `.cdsapirc` — sosem volt benne, de érdemes megnézni
- a `.gitignore` fedi-e: `*.nc`, `*.nc4`, `grace/`, `imerg/`, `hatar.geojson`,
  `maszk_cache/`, `data.json`, `data.js`, `_publish/`
- a commit-történet: kulcs vagy jelszó sosem került bele
- **a CDS-token és az LSA SAF jelszó cseréje** — ezek korábban chatbe kerültek

Gyors ellenőrzés:

    git log -p --all | grep -iE "password|token|api[_-]?key|secret" | head

---

## Verziózási séma

| Szám | Mikor lép | Példa |
|---|---|---|
| fő | a doboz vagy a mérlegegyenlet változik | váltás a magyar dobozról a teljes medencére |
| közép | új tag kerül be, vagy egy osztály feljebb lép | a talaj vízhiánya az aszálymonitoringból |
| utolsó | javítás, pontosítás, szövegezés | a provenance-osztályok felülírásának javítása |

---

## A release után

1. A koncepció-DOI beírása három helyre:
   - `MODSZERTAN.md` és `METHODOLOGY.md` hivatkozás-blokkja
   - `levelek.md` három `[DOI: …]` helyőrzője
   - `index.html` forrás-szekciója, „Módszertan" linkként
2. A három adatigénylő levél kiküldése:
   - OVF — `adatszolgaltatas@ovf.hu` (magyar)
   - SHMÚ — angol, a `METHODOLOGY.md`-re hivatkozva
   - INHGA — angol, ugyanígy
3. A `README.md` kiegészítése a DOI-badge-dzsel
