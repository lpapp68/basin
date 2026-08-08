# A Középső-Duna-medence vízmérlege

## Nyílt, provenance-címkézett monitorozási módszer

**Papp László** · EQUORA Institute · ORCID 0009-0005-6329-5808
Élő felület: https://basin.equora.institute

---

## Összefoglalás

A Középső-Duna-medence vízmérlegét mutatjuk be nyilvános, óránként frissülő felületen.
A medence hidrológiailag majdnem zárt doboz: a Duna Dévénynél belép, Baziásnál kilép,
és a Tisza, a Dráva, a Száva meg a Morava vízgyűjtője teljes egészében belül marad.
A mérleg minden tagja **provenance-osztályt** kap — helyszíni mérés, helyszíni adatból
számított, műholdas becslés, számított vagy helyőrző —, és a hiányzó tudás a felületen
külön számként jelenik meg. A módszer központi tervezési döntése, hogy a készletváltozás
**maradéktagként** áll elő: így a mérlegben megjelenő eltérés azt méri, mennyire zárt a
mérési rendszer.

---

## 1. A doboz

| | terület | falak | állapot |
|---|---|---|---|
| `hu` Magyarország | 93 030 km² | 11 belépő és 3 kilépő magyar mérce, órás hozammal | **aktív** |
| `mdb` Középső-Duna-medence | ~445 900 km² | Duna, Dévény (SHMÚ) és Duna, Baziás (INHGA) | falak bekötve, a doboz még nem aktív |

**A terület levezetése és a mért szelvény két különböző dolog.** A ~445 900 km² a
Vaskapu I. vízgyűjtőjéből (577 250 km²) mínusz a Duna dévényi vízgyűjtőjéből
(~131 350 km²) áll elő — ez a szakirodalmi medencehatár. A ténylegesen **mért** kilépő
szelvény ezzel szemben **Baziás** (fkm 1072), amely a Tisza, a Száva és a Velika Morava
torkolata után, a Vaskapu gátja **előtt** van. A kettő közti szakasz hozzáfolyása a
mérlegből kimarad; ez a nyitott tételek között szerepel.

**A magyar doboz azért aktív, mert a területi tagok maszkja országhatárra készült.**
A csapadék és a párolgás területtel skálázódik, ezért a doboz átváltásához a maszkot
vízgyűjtő-poligonra kell cserélni (HydroSHEDS/HydroBASINS). A második akadály a
kadencia: a baziási hozam naponta jön, ezért az `mdb` doboz mérlege napi ütemű lenne.

**A magyar doboz nyitott falai:** Hernád, Kraszna, Fekete-Körös, Berettyó, valamint a
határon átnyúló felszín alatti vízáramlás. Ezek a maradéktagban jelennek meg.

---

## 2. A mérlegegyenlet és az előjelek

    P + Q_be − ET − Q_ki − kivétel_veszteség = ΔS

**Előjel-konvenció:** a dobozba érkező tételek pozitívak, a távozók negatívak. Az öt tag
összege adja a készletváltozást.

**A központi döntés:** a ΔS maradéktagként áll elő. Ez a szokásos vízmérlegek
fordítottja, és szándékos — így a mérlegben megjelenő eltérés megmondja, mennyire
hihető a többi tag.

---

## 3. A tagok és az öt provenance-osztály

| Tag | Forrás | Kadencia | Osztály |
|---|---|---|---|
| Vízállás, vízhő | OVF Országos Vízjelző Szolgálat | órás | helyszíni mérés |
| Vízhozam | OVF, vízállásból vízhozamgörbével | órás | helyszíni adatból számított |
| Talaj vízhiánya | OVF Aszálymonitoring, WD35 és WD80 | napi | helyszíni mérés |
| Csapadék | GPM IMERG Early, 0,1° | napi | műholdas becslés |
| Párolgás | EUMETSAT LSA SAF DMETv3, 0,05° | napi | műholdas becslés |
| Referencia-párolgás | EUMETSAT LSA SAF METREF | napi | műholdas becslés |
| Készlet-anomália | NASA/JPL GRACE és GRACE-FO mascon | havi, 40–60 nap késéssel | műholdas becslés |
| Medence falai | SHMÚ Dévény, INHGA Baziás | napi | helyszíni adatból számított |
| Vízkivétel | éves statisztika × havi profil × veszteséghányad | napi | számított |
| Paks hűtővíz | blokkteljesítményből arányosítva | 30 perc | számított |
| Készletváltozás | maradéktag | napi | számított |

### Az osztályok jelentése

- **helyszíni mérés** — műszer mérte a helyszínen. Példa: a vízállás Paksnál, centiméterben.
- **helyszíni adatból számított** — a folyók vízhozama: helyszíni vízállásból, kalibrált
  vízhozamgörbével. Külön osztályt kap, mert a görbe a mederbevágódással vándorol —
  ugyanaz a jelenség, amely a paksi szivattyúk szívócsonkját víz fölé emelte.
- **műholdas becslés** — műholdas mérésekből modellel visszaszámítva. Példa: a párolgás
  a Meteosat sugárzási adataiból; a GRACE tömeganomália-inverzióból, kb. 300 km-es
  természetes felbontással.
- **számított** — más tételekből, feltételezésekkel. Példa: az augusztusi öntözés az
  éves 154 millió m³ havi eloszlásából.
- **helyőrző** — nagyságrendi becslés, amíg a forrás bekötésre vár.

**Az osztály a forrásnál dől el, és a felület csak megjeleníti.** Az egyes lekérő
scriptek írják be a `params.json`-be; a `fetch_data.py` továbbadja, felülírás nélkül.
Ez a szabály egy korábbi hiba után született (lásd a változásnaplót).

### Három óra a fejlécben

A mérleg három sebességű adatból áll össze: **órás** (vízállás, hozam, vízhő), **napi**
(csapadék, párolgás), **havi** (készletváltozás). A három számlap a fenntartás vizuális
formája. Mindhárom dátum magából az adatból származik, ezért egy forrás leállása a
fejlécben azonnal látszik.

A rendszer hibaként jelzi, ha a csapadék és a párolgás dátuma eltér: egy mérleg tagjai
egyetlen naphoz tartoznak.

---

## 4. Területi átlagolás

A csapadék és a párolgás **országhatár-maszkkal** átlagolódik. A maszk a Natural Earth
10m közigazgatási határából készül, sugárvetéses pont-a-poligon eljárással, cellánként
valódi gömbi területtel súlyozva.

**Ellenőrzés:** a maszkolt terület 0,05°-os rácson 93 218 km², a hivatalos 93 030-hoz
képest 0,2% eltéréssel.

**A korrekció nagysága:** a korábbi befoglaló téglalap 223 000 km², vagyis a maszkolt
terület annak 42%-a. A téglalap-átlag 58%-ban külföldi területet mért. A váltás a
párolgás napi értékét 2,20-ról 1,90 mm-re módosította — 14% szisztematikus eltérés.

---

## 5. A teljes medence két fala

A `kulfold.py` két nyilvános forrásból olvassa a doboz falait:

| Fal | Forrás | Formátum | Példa (2026-08-07) |
|---|---|---|---|
| Belépő — Duna, Dévény | SHMÚ napi jelentés | táblázat: vízállás, hozam, vízhő | 981,0 m³/s |
| Kilépő — Duna, Baziás | INHGA napi bulletin | próza | 1 400,0 m³/s |

**A medence hozzáfolyása 419 m³/s** — ennyit ad hozzá a Tisza, a Dráva, a Száva, a
Morava és minden belső hozzáfolyás együttvéve, nagyjából 446 ezer km²-ről. A kilépő
hozam a sokéves augusztusi átlag (3 900 m³/s) **36%-a**.

**Két fenntartás.** Mindkét forrás operatív, korrekció nélküli adat; a SHMÚ ezt ki is
mondja. A baziási hozam a bulletin *szövegéből* származik, ezért a minta törékeny —
átfogalmazás esetén a script hangosan elhasal, ahelyett hogy csendben rosszat írna.

**A dunai profil és a bősi hatás.** A SHMÚ jelentéséből a magyar szakasz előtti profil
is kiolvasható: Dévény 981 → Medve 722 → Komárom 761 → Párkány 790 m³/s. A Dévény és
Medve közti 259 m³/s-os esés a bősi vízlépcső üzemrendjéből ered — a víz nagy része az
üzemvízcsatornán halad. Üzemeltetési átrendezés, nem vízveszteség.

---

## 6. Paks mint küszöb-csomópont

Paks külön szekciót kap, mert ez az egyetlen pont az országban, ahol néhány centiméter
vízszint és néhány tizedfok hőmérséklet **korlátozhatja a blokkok termelését**. A mérleg
többi tétele mennyiségről szól; ez küszöbökről.

**Két vízoldali fal:** a szivattyúk szívócsonkjának magassága, és a 30 °C-os hőterhelési
korlát a melegvíz-csatorna torkolatától 500 méterre.

**A hűtővízkivétel állapotfüggő.** A névleges üzem kondenzátorhűtése kb. 100 m³/s, a
leállított blokkok fenntartó hűtése kb. 100 m³/**perc** — hatvanszoros különbség. A
blokkteljesítmény kizárólag ezt az arányosítást szolgálja.

---

## 7. Vízkivétel: teljes kivétel és veszteség

Az éves statisztikai mennyiség havi profillal napi értékké alakul, majd
veszteséghányaddal szorzódik.

| Tétel | Éves mennyiség | Forrás | Augusztusi kivétel | Ebből veszteség |
|---|---|---|---|---|
| Halastavak | 356 millió m³ | ÁSZ, 2019–2023 átlag | 22,6 m³/s | 15,8 |
| Mezőgazdasági öntözés | 154 millió m³ | ÁSZ, 2019–2023 átlag | 13,8 m³/s | 12,4 |
| Lakossági ivóvíz | 38,7 m³/fő/év | KSH, 2022 | 12,9 m³/s | 3,2 |
| Ipar, Paks nélkül | 290 millió m³ | származtatott | 9,0 m³/s | 1,4 |
| Paks hűtővíz | állapotfüggő | blokkteljesítményből | 13,0 m³/s | 0,0 |
| **Összesen** | | | **71,3 m³/s** | **32,8** |

**A megkülönböztetés lényegi.** A halastavakhoz vezetett víz bruttó szolgáltatott
mennyiség: egy része leeresztéskor visszatér, más része talajvizet táplál. A mérlegbe
kizárólag a veszteségrész számít — ami a vizsgált időszakon belül kívül marad a magyar
vízrendszeren.

**A veszteséghányadok feltételezések:** öntözés 90%, halastavak 70%, ivóvíz 25%,
ipar 15%. Mérési alapjuk hiányzik; a vízkészletjárulék-bevallások adnának helyettük
tényadatot.

**Az öntözési statisztika hiányos.** A KSH kimondja, hogy az engedély nélküli
vízkivételek kimaradnak belőle, és tanulmányok ezeket a bejelentett mennyiség
duplájára becsülik.

---

## 8. A talaj rekesze és a tartózkodási idő

Az OVF aszálymonitoring-hálózata adja a talaj rekeszét: óránkénti talajnedvesség hat
mélységben (10–75 cm), és napi vízhiány **milliméterben** (WD35, WD80).

**Példa, 2026. augusztus 5.:** a 80 cm-es rétegben Kiskunfélegyházán 35,0 mm,
Apajon 34,7 mm, Csólyospáloson 18,3 mm hiányzik; öt állomás átlaga 26,6 mm.

**Három rekesz, három nagyságrend:**

- **napok** — a folyó. A Duna nagyjából egy hét alatt halad át az országon.
- **hetek** — a talaj. A fenti hiány ennyi idő alatt épült fel, és esőből ennyi alatt
  tölthető vissza.
- **évtizedek** — a talajvíz. A Duna–Tisza közi hátságon 2–5 méterrel süllyedt az
  1970-es évek óta, helyenként 10 méterrel.

**A módszer egyik érdemi állítása ebből következik:** a folyón átfolyó víz és az aszály
két külön rekeszben van. A Duna vize a gyors rekeszben forog, a szárazság a lassúban
mélyül.

**A hiány és a napi párolgás hányadosa pótlási időegyenérték**, nem tartózkodási idő:
azt mondja meg, mekkora csapadék töltené vissza a gyökérzónát.

---

## 9. Öntözésigény kontra tényleges kivétel

`ETc = Kc × ET_ref`, `hiány = max(0, ETc − ET_act)`, Kc tartományként (0,8–1,2).

**Példa, 2026. augusztus 4.:** referencia-párolgás 5,30 mm/nap, tényleges 1,92 mm/nap,
vízstressz-index 0,36. A 4,3 millió hektár szántó vízhiánymentes ellátásához naponta
100–191 millió m³ víz kellene — nagyjából annyi, amennyi a folyókon beérkezik az
országba.

Figyelemre méltó egybeesés: a vízstressz-index 36%, és a baziási hozam is a sokéves
augusztusi átlag 36%-a. Két független mérés, azonos irány.

---

## 10. A számok érvényességi köre

1. **A doboz Magyarország területe.** A teljes medence falai bekötve, a váltás a maszkon
   és a kadencián múlik.
2. **A mért kilépő szelvény Baziás, a területi levezetés a Vaskapué.** A köztes szakasz
   hozzáfolyása a mérlegből kimarad.
3. **A vízkivétel számított.** Az éves mennyiségek hivatkozott statisztikák; a havi
   eloszlás és a veszteséghányad feltételezés.
4. **Az ipari kivétel származtatott** — a teljes nettó kivételből levonással.
5. **Az LKV frissessége tisztázásra vár.** A „mérce a mindenkori kisvíz alatt" állítás
   azon áll, mikor frissítette az OVF ezeket az értékeket.
6. **A GRACE 300 km-es felbontású**, 40–60 napos késéssel. Trendre alkalmas, egyetlen
   hónapra kevésbé. Tízéves meredekség: −1,30 km³/év, 257 havi pontból, 2002 áprilisától.
7. **A maszk országhatár.** A vízgyűjtő-poligon a következő lépés.
8. **Az aszálymonitoring végpontja visszafejtett** a lap JavaScriptjéből.
9. **A baziási hozam prózából származik**, ezért a minta törékeny.
10. **A vízhozamgörbék a mederbevágódással vándorolnak.**
11. **A két párolgásbecslés eltér.** A különbség a felületen külön számként szerepel, és
    a mérési rendszer nyitottságát méri.
12. **A meder és a felszín alatti víz cseréje a dobozon belüli átrendezés**, ezért a
    maradéktagot nem növeli — a határon átnyúló felszín alatti áramlás viszont igen,
    és azt nem mérjük.

---

## 11. Licencek

| Elem | Licenc |
|---|---|
| A kód | MIT |
| A dokumentáció | CC BY 4.0 |
| Copernicus / ERA5-Land | Copernicus-licenc, hivatkozási kötelezettséggel |
| EUMETSAT LSA SAF | CC BY 4.0, Trigo et al. (2011) hivatkozással |
| NASA GPM IMERG, GRACE-FO | nyílt, hivatkozási kötelezettséggel |
| holadelej.hu (paksi üzemállapot) | CC BY 4.0 |
| **OVF, SHMÚ, INHGA adat** | **tisztázás alatt — adatigénylés folyamatban** |

---

## 12. Reprodukálhatóság

    ./frissit.sh napi      # a teljes napi ciklus, hét forrásból
    ./frissit.sh oras      # csak a mércék

vagy egyenként:

    python maszk.py            # határvonal és maszk
    python imerg_precip.py     # csapadék (tartalék: era5_precip.py)
    python lsasaf_et.py        # párolgás
    python ontozesigeny.py     # referencia-párolgás, vízstressz
    python aszaly.py           # talaj vízhiánya
    python kivetel.py          # vízkivétel modell
    python kulfold.py          # a teljes medence két fala
    python grace.py            # készlet-anomália idősor, havonta
    python fetch_data.py       # mércék és mérleg → data.json

A hitelesítés a `~/.netrc` és a `~/.cdsapirc` fájlokból érkezik; a kód kulcsot mellőz.
A ciklus GitHub Actionsben óránként fut. Az `archiv/` mappa a saját napi idősort gyűjti
— ez az egyetlen adat, amely újraelőállításra alkalmatlan.

---

## 13. Változásnapló

**v1.0.0** — első nyilvános verzió.

Öt javítás érdemel említést, mert mindegyik nagyságrendi vagy bizalmi hibát szüntetett
meg:

- **A területi átlagolás maszkra váltása.** A befoglaló téglalap 58%-ban külföldi
  területet mért; a párolgás napi értéke 2,20-ról 1,90 mm-re módosult.
- **A veszteség-összegzés javítása.** A mérleg korábban a teljes kivételt vonta le, és
  kizárólag az 50% fölött veszteséges tételeket vette figyelembe. A javított összeg
  32,8 m³/s, és minden tétel veszteséghányada beleszámít.
- **A paksi hűtővíz állapotfüggővé tétele.** A korábbi 100 m³/s a névleges üzem értéke;
  a mai, arányosított érték 226 MW mellett 13 m³/s.
- **A provenance-osztályok felülírásának megszüntetése.** A `fetch_data.py` a vízkivétel
  osztályát `helyőrző`-re írta felül, holott a `kivetel.py` már `számított`-ként adta
  át. Innen a szabály: az osztályt a forrás írja, a felület csak megjeleníti.
- **Az ötödik osztály bevezetése.** A folyók vízhozama korábban `helyszíni mérés`
  címkét kapott, holott vízállásból származik. Az új `helyszíni adatból számított`
  osztály ezt a különbséget teszi láthatóvá.

---

## Hivatkozás

> Papp L. (2026). *Water balance of the Middle Danube Basin: an open,
> provenance-labelled monitoring method.* EQUORA Institute. Zenodo.
> https://doi.org/[koncepció-DOI]

Angol nyelvű kivonat: `METHODOLOGY.md`
