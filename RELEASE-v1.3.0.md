## Öntözővíz a Dunából

**Új szekció:** egy elképzelt mezőföldi szivattyútelep a dunaújvárosi szelvény
fölött, 1991. január 1-jétől napi adaton, két üzemmódban. **A:** kivétel az
öntözési igény szerint. **B:** kivétel csak a küszöb fölötti vízből, tározással.
A három csúszka (éves igény, kapacitás, küszöb) mindkét üzemmódot egyszerre állítja.

Új adatsor: a Duna napi vízhozama Dunaújvárosnál (OVF 547) és a paksi vízhő
(OVF 549) 1991-től, nyílt fájlként is: `duna.json`. A vízhő a reggeli felszíni
észlelés; ahol hiányzik (2026-ban egészében), a mederfenéki szonda napi átlaga,
amely a meleg napokon átlagosan 0,4 °C-kal alacsonyabb — a pótolt napok a meleg
napokat inkább alulbecsülik.

**Paks-nap:** a paksi vízhő legalább 25 °C, és a dunaújvárosi hozam a napi hozamok
20%-os percentilise (1 480 m³/s) alatt jár. Az alapértékekkel (évi 700 millió m³,
81 m³/s, küszöb a medián):

- a Paks-napok száma 1991–2008 között **27**, 2009–2026 között **114**, ebből 2026-ban **44**;
- 2026 Paks-napjain az igénykövető telep a Duna átlag **7,8%-át**, legfeljebb
  **11,2%-át** vinné el, teljes elkeveredéssel legfeljebb **+0,19 °C**-kal;
- a küszöbszabály 1991/92–2024/25 között **31/34** évben fedezi az igényt, medián
  **209 millió m³** tárolóval; 2025/26-ban a küszöb fölött csak **122 millió m³** volt kivehető;
- a szabad víz ablaka az alpesi olvadás: a havi medián hozam március–júliusban
  2 230–2 665, október–januárban 1 585–1 760 m³/s.

## Talajvíz-panel

A tízéves összevetés mostantól naponta újraszámolódik, és a lap dátummal mutatja.

## Üzem

Félórás indítás egy Cloudflare Durable Object riasztásával (`utemezo/`). A paksi
blokkteljesítmény közvetítővel érkezik, mert a forrás a GitHub-futtatók címeit
elutasítja; a közvetítő az utolsó sikeres értéket a korával együtt adja tovább.

## Adatvédelem, biztonság, kereshetőség

Saját tárhelyes betűtípus; szerveroldali, álnevesített statisztika; CSP és HSTS;
impresszum és adatkezelési tájékoztató; valódi 404; strukturált adat (Dataset)
mindkét adatfájllal; frissített `llms.txt`.

---

# English

## Irrigation water from the Danube

**New section:** a hypothetical pumping station on the Mezőföld, above the
Dunaújváros gauge, tested on daily data from 1 January 1991 in two modes. **A:**
abstraction following irrigation demand. **B:** abstraction only from flow above a
threshold, with storage. Three sliders (annual demand, capacity, threshold) set
both modes at once.

New series: daily Danube discharge at Dunaújváros (OVF 547) and river temperature at
Paks (OVF 549) from 1991, also as an open file: `duna.json`. Temperature is the
morning surface reading; where it is missing (all of 2026) the bottom probe's daily
mean is used, which runs on average 0.4 °C lower on warm days — filled days tend to
understate warm days.

**A Paks day:** water temperature at Paks at least 25 °C and discharge at Dunaújváros
below the 20th percentile of daily flows (1,480 m³/s). With the defaults (700 million m³
per year, 81 m³/s, threshold at the median):

- Paks days numbered **27** in 1991–2008 and **114** in 2009–2026, **44** of them in 2026;
- on the 2026 Paks days a demand-following station would have taken on average
  **7.8%** and at most **11.2%** of the Danube, warming it by at most **+0.19 °C** under full mixing;
- the threshold rule meets the demand in **31 of 34** water years (1991/92–2024/25) with a
  median storage of **209 million m³**; in 2025/26 only **122 million m³** was available above the threshold;
- the free-water window is the Alpine melt: monthly median discharge is 2,230–2,665 m³/s
  in March–July and 1,585–1,760 m³/s in October–January.

## Groundwater panel

The ten-year comparison is now recomputed daily and dated on the page.

## Operations

Half-hourly runs triggered by a Cloudflare Durable Object alarm (`utemezo/`). The Paks
unit output is relayed, because the source rejects GitHub runner addresses; the relay
passes on the last successful value together with its age.

## Privacy, security, findability

Self-hosted fonts; server-side pseudonymised analytics; CSP and HSTS; imprint and
privacy notice; a real 404; structured data (Dataset) with both data files; updated `llms.txt`.

---

**Live:** https://basin.equora.institute
**Documentation:** `README.md`, `MODSZERTAN.md`, `README.en.md`, `METHODOLOGY.md`
**Licences:** code MIT; data outputs (`data.json`, `duna.json`) CC BY 4.0
