# SETUP.md — regisztrációk és API-kulcsok

Négy dolog hiányzik a mérlegből: **csapadék**, **párolgás**, **készletváltozás**, és a
**teljes medence dobozához** két külföldi hozamszelvény. Mind a négy ingyenes.
Sorrendben, ahogy a legtöbb hasznot hozzák.

Idő: a CDS és az Earthdata percek alatt megvan; az LSA-SAF és a külföldi szolgálatok
e-mailes visszaigazolásra várnak, ezért ezeket érdemes elsőként elindítani.

---

## 1 · ERA5-Land — csapadék (és tartalék párolgás)

**Ki adja:** Copernicus Climate Change Service, ECMWF üzemelteti.
**Amit ad:** órás csapadék és potenciális párolgás, ~9 km rács, 2–5 napos késéssel.
**Licenc:** Copernicus-licenc, szabad felhasználás, hivatkozási kötelezettséggel.

**Lépések**

1. Regisztrálj ECMWF-fiókot: <https://cds.climate.copernicus.eu> → *Login / register*.
   (2024 szeptembere óta a régi CDS-fiókok nem működnek — új ECMWF-fiók kell.)
2. Belépés után nyisd meg: <https://cds.climate.copernicus.eu/how-to-api>.
   Ez az oldal kiírja a személyes hozzáférési tokenedet.
3. Hozd létre a `~/.cdsapirc` fájlt:

   ```
   url: https://cds.climate.copernicus.eu/api
   key: <PERSONAL-ACCESS-TOKEN>
   ```

   A token jelszóként kezelendő. A régi `<UID>:<APIKEY>` formátum és az `/api/v2`
   végpont elavult — ha ezt látod egy tutorialban, az régi.
4. `pip install "cdsapi>=0.7"`
5. **Ezt a lépést ne hagyd ki, és vigyázz, melyik adatlapon vagy.** Két hasonló nevű
   adatkészlet létezik, és a licencet adatkészletenként külön kell elfogadni:

   | Adatlap címe | API-név | Mit ad |
   |---|---|---|
   | ERA5-Land **hourly data** from 1950 to present | `reanalysis-era5-land` | **rácsos**, `area` bbox-szal — EZ KELL a mérleghez |
   | ERA5-Land hourly **time-series** data from 1950 to present | `reanalysis-era5-land-timeseries` | egyetlen pont (lon/lat), de-akkumulált csapadékkal |

   A területi átlaghoz a rácsos kell; a pontos idősor nem tud 93 000 km²-t átlagolni.

   A licenc elfogadásához **nem kell kitölteni az űrlapot és nem kell elküldeni a kérést**:
   görgess a *Terms of use* dobozhoz, és fogadd el a CC-BY licencet. Ez a fiókodra
   mentődik. E nélkül az API 403-mal elszáll, pedig a kulcs jó.

   A rácsos adatkészletben a `total_precipitation` HALMOZOTT; a time-series változatban
   de-akkumulált. Ne keverd össze a kettőt.
6. Próba. **Ezt fájlba mentsd és `python`-nal futtasd — ne a shellbe másold.**
   A shellben az `import` egy egészen más program (az ImageMagick képernyőmentője),
   és zavaros hibaüzenettel száll el.

   A `test_cds.py` nem létezik előre — te hozod létre. A home könyvtáradba kerül
   (`/Users/<felhasználó>/test_cds.py`). Legegyszerűbb szerkesztővel:

```bash
nano ~/test_cds.py
```

   Illeszd be ezt, majd `Ctrl+O`, `Enter`, `Ctrl+X`:

```python
import cdsapi, datetime as dt

nap = dt.date.today() - dt.timedelta(days=7)   # ERA5-Land kb. 5 napot késik
c = cdsapi.Client()
c.retrieve("reanalysis-era5-land", {
    "variable": ["total_precipitation"],
    "year":  f"{nap:%Y}", "month": f"{nap:%m}", "day": [f"{nap:%d}"],
    "time":  [f"{h:02d}:00" for h in range(24)],
    "area":  [49.1, 16.0, 45.7, 22.9],   # É, Ny, D, K — magyar doboz
    "data_format": "netcdf",
}, "era5land_precip.nc")
```

   Futtatás:

```bash
source ~/cds-env/bin/activate
python ~/test_cds.py
```

**Három buktató, mindegyikbe bele lehet esni elsőre**

- **Ne a shellbe másold a Python kódot.** Vagy `python` promptot indíts, vagy fájlba mentsd.
- **Késés:** az ERA5-Land kb. 5 nappal marad el a valós időtől. A tegnapi napra kért adat
  üresen jön vissza. A napi cron mindig 6–7 nappal korábbi napot kérjen.
- **Halmozott mennyiség:** a `total_precipitation` az adott nap 00 UTC-jétől halmozódik,
  ezért egy nap teljes csapadéka a KÖVETKEZŐ nap 00:00-s értéke. Ha a 24 órás értéket
  egyszerűen összeadod, sokszorosát kapod a valóságnak.

A kérések szerver oldalon sorba állnak, ezért a letöltés külön scriptbe való,
nem a dashboard-generálásba.

---

## 2 · LSA SAF — tényleges párolgás (ET)

**Ki adja:** EUMETSAT Land Surface Analysis SAF, az IPMA (portugál meteorológiai
szolgálat) üzemelteti.
**Amit ad:** `ET` fél óránként és `DMET` napi összegben, 3–5 km, Európára,
near-real-time.
**Licenc:** CC BY 4.0 — szabadon használható, forrásmegjelöléssel.

**Lépések**

1. Menj a <https://lsa-saf.eumetsat.int/en/data/data-access/> oldalra.
2. Regisztrálj az **LSA SAF data service**-hez (a preferált hozzáférési pont):
   <https://datalsasaf.lsasvcs.ipma.pt/>. Az űrlap kitöltése után a felhasználónevet
   és jelszót **e-mailben** küldik — ez nem azonnali, ezért ezzel kezdd.
3. A szolgáltatás HTTP-n és OpenDAP-on át érhető el. A hivatalos példák
   (WebDAV, Colab-notebookok, HDF5→netCDF konverzió) itt vannak:
   <https://lsa-saf.eumetsat.int/en/user-support/tutorials/>.
4. Termékazonosítók, amiket keresel: **DMETv3** (napi ET, LSA-312.3 / LSA-351) —
   a napi mérleghez ez kell; az `ETv3` a fél órás változat.
5. Tedd a hitelesítést `~/.netrc`-be, ne a kódba:

   ```
   machine datalsasaf.lsasvcs.ipma.pt login <FELHASZNÁLÓ> password <JELSZÓ>
   ```

6. Ha 5 napnál hosszabb gördülő archívum kell near-real-time-ban, kérhető SFTP-hozzáférés
   is — e-mailben, az LSA SAF helpdesknél.

**Kötelező hivatkozás** a lap alján: a terméket az EUMETSAT LSA SAF szolgáltatta,
Trigo et al. (2011) hivatkozással.

---

## 3 · GRACE-FO — készletváltozás

**Ki adja:** NASA/JPL, a PO.DAAC szolgáltatja.
**Amit ad:** havi teljes vízkészlet-anomália (mascon rács, ~300 km), 1–2 hónapos
késéssel. Élő panelre alkalmatlan, a kumulált egyenleghez viszont pont ez kell.

**Lépések**

1. Hozz létre **Earthdata Login** fiókot: <https://urs.earthdata.nasa.gov>.
2. `~/.netrc`:

   ```
   machine urs.earthdata.nasa.gov login <FELHASZNÁLÓ> password <JELSZÓ>
   ```

   Jogosultság: `chmod 600 ~/.netrc`.
3. `pip install earthaccess`
4. A konkrét adatkészlet-azonosítót a PO.DAAC keresőjében nézd ki
   (`GRACE-FO mascon`), mert a verziószám időről időre változik — ne írj be fixen
   egy régi RL06-os stringet.

   ```python
   import earthaccess
   earthaccess.login()          # a .netrc-ből olvas
   r = earthaccess.search_data(short_name="<PO.DAAC short name>", count=5)
   earthaccess.download(r, "grace/")
   ```

**Fontos:** a GRACE anomáliát ad, nem abszolút készletet. A 2. panel épp ezért hiányt
mutat, nem telítettséget — a lapnak ezt a különbséget mindig ki kell mondania.

---

## 3b · GPM IMERG Early — gyors csapadék

Az ERA5-Land 5 napot késik, ezért a mérleg mindig 5-6 nappal marad el. Az IMERG Early
napi terméke néhány órás késéssel jön, cserébe műholdas becslés, nem reanalízis.

**Lépések**

1. Ugyanaz az Earthdata Login fiók, mint a GRACE-hez (3. pont).
2. **Ez a lépés a legtöbb leírásból kimarad:** az Earthdata profilodban
   *Applications → Authorized Apps* alatt engedélyezd a **NASA GESDISC DATA ARCHIVE**
   alkalmazást. Enélkül a letöltés némán átirányít a bejelentkező oldalra, és HTML-t
   ment `.nc4` néven — a hiba csak az xarray-nál jön elő, félrevezető üzenettel.
3. `pip install earthaccess`
4. `python imerg_precip.py`

A termék `GPM_3IMERGDE` (Early, napi, 0,1°). A `GPM_3IMERGDF` (Final) pontosabb, de
hónapokat késik — az a történeti sorozathoz jó, nem az élő laphoz.

**Ne keverd a kettőt egy idősorban.** Az IMERG és az ERA5-Land más hibaszerkezetű;
a `params.json` ezért mindig beírja, melyikből jött az érték.

## 4 · A teljes medence doboza — két hozamszelvény

Ez a legkisebb munka a legnagyobb hozadékkal. A Középső-Duna-medence falaihoz
**mindössze két szelvény kell**, mert a Tisza, a Dráva, a Száva és a Morava vízgyűjtője
teljes egészében a dobozon belül van:

| Fal | Szelvény | Kitől |
|---|---|---|
| Belépés | Duna, Dévény / Pozsony | SHMÚ — Szlovák Hidrometeorológiai Intézet |
| Kilépés | Duna, Vaskapu / Orsova (vagy Baziás) | INHGA — román Nemzeti Hidrológiai Intézet |

**Lépések**

1. Írj adatigénylést mindkét szolgálatnak. Ne „szeretnénk adatot" formában: kérj
   **napi átlagos vízhozamot egyetlen szelvényre**, kutatási célra, forrásmegjelöléssel,
   és ajánld fel a kimenet nyilvánosságát. Egy szelvény sokkal könnyebben megy át, mint
   egy hálózat.
2. Párhuzamosan: az **ICPDR** (Duna-védelmi Nemzetközi Bizottság) a természetes
   partner, ha a projekt hivatkozható módszertannal és DOI-val rendelkezik. Ezért is
   érdemes a Zenodo-deposit előbb, az adatkérés utána.
3. Amíg nincs válasz, tartalékként a **GloFAS/EFAS** (CEMS, JRC) ad modellezett napi
   hozamot ugyanezekre a pontokra, ugyanazzal a CDS-fiókkal, amit az 1. pontban
   létrehoztál — de az EWDS katalógusból, és `provenance: modellezett` címkével.
4. A `fetch_data.py`-ban a `DOBOZOK["mdb"]` már készen áll; az `AKTIV_DOBOZ`-t kell
   `"mdb"`-re állítani, ha a két szelvény megvan.

**A területszám ellenőrizendő.** A `mdb` doboz jelenlegi 445 900 km²-e a Vaskapu I.
vízgyűjtőjéből (577 250 km²) és a Duna dévényi vízgyűjtőjéből (~131 350 km²) áll elő
kivonással. Az első szám hivatkozható, a második még nem — kérd be az ICPDR-től vagy
az SHMÚ-tól, és cseréld ki a `terulet_provenance` mezővel együtt.

---

## Amit sehova ne írj be

Egyik kulcs se kerüljön a repóba, a `params.json`-be vagy a `data.json`-be.
Mind a négy szolgáltatás fájlalapú hitelesítést használ (`~/.cdsapirc`, `~/.netrc`),
így a kód kulcs nélkül fut. A cron-felhasználó home-jában legyenek a fájlok,
`chmod 600`-zal.

## Sorrend, ha csak egy délutánod van

1. LSA SAF regisztráció elküldése (e-mailre vár) — **most**
2. Adatkérő levél az SHMÚ-nak és az INHGA-nak — **most**
3. CDS-fiók + `.cdsapirc` + ERA5-Land licenc elfogadása — 15 perc
4. Earthdata-fiók + `.netrc` — 10 perc
5. A csapadék bekötése a `params.json` helyett — ez az első tétel, ami helyőrzőből
   méréssé válik
