# basin.equora.institute — vízmérleg v2.1

Középső-Duna-medence vízmérleg. Egyetlen pipeline, egyetlen kimenet (`data.json`),
két fogyasztó: az Institute-dashboard és — később — az iterators.org darab.

```
fetch_data.py  →  data.json + data.js  →  index.html
      ↑
  params.json   (csak az, ami még nem él)
```

```bash
python3 fetch_data.py     # 22 mérce + a paksi üzemállapot
open index.html
```

Cron: `5 * * * *` — a mércék óras idősort adnak.

## Ami a v2-ben megváltozott

A v1 azt állította, hogy a vízhozam nem publikus, és GloFAS kell hozzá. **Ez tévedés volt.**
Az OVF mércénkénti adatlapja óránként ad **vízállást, vízhozamot (m³/s) és vízhőfokot**.
A mérleg folyó-tagjai innentől mérések. 22 mércéből 22 ad hozamot.

## Előjelek

Ami a dobozba kerül, pozitív; ami elhagyja, negatív. Az öt tag összege a készletváltozás,
és a Pulzus panel rúdjai a nullavonal két oldalára nőnek.

## A doboz — kettő van

| | terület | állapot | falak |
|---|---|---|---|
| `hu` Magyarország | 93 030 km² | **aktív** | 11 belépő + 3 kilépő magyar mérce, mind mért |
| `mdb` Középső-Duna-medence | ~445 900 km² | tervezett | **két szelvény elég**: Duna Dévénynél és Duna a Vaskapunál |

A `mdb` doboz azért ilyen olcsó, mert a Tisza, a Dráva, a Száva és a Morava vízgyűjtője
teljes egészében belül van. A terület a Vaskapu I. vízgyűjtőjéből (577 250 km²) mínusz
a dévényi vízgyűjtőből (~131 350 km²) jön — a második szám még hivatkozandó.

A csapadék és a párolgás területtel skálázódik, ezért amíg a `hu` az aktív doboz,
ezek a tagok is a magyar területre vonatkoznak. A váltás egyetlen sor: `AKTIV_DOBOZ`.

**Regisztrációk és API-kulcsok: lásd [SETUP.md](SETUP.md).**

## Mi él, mi nem

| Tétel | Állapot | Forrás | Kadencia |
|---|---|---|---|
| Vízállás, vízhozam, vízhő | **él** | OVF / vizugy.hu, mércénkénti idősor | óras |
| Paksi hűtővízkivétel | **származtatott** | blokkteljesítmény: holadelej.hu (CC BY 4.0) | 30 perc |
| Csapadék | helyőrző | ERA5-Land — CDS API-kulcs kell | napi |
| Párolgás ET | helyőrző | EUMETSAT LSA-SAF ET — regisztráció kell | fél óra |
| Készletváltozás | helyőrző | GRACE-FO | havi |

## A doboz falai

Belépő (10): Duna-Nagybajcs, Ipoly-Ipolytarnóc, Dráva-Őrtilos, Rába-Szentgotthárd,
Tisza-Tiszabecs, Szamos-Csenger, Bodrog-Felsőberecki, Sajó-Sajópüspöki, Maros-Makó,
Sebes-Körös-Körösszakál, Fehér-Körös-Gyula.

Kilépő (3): Duna-Mohács, Dráva-Drávaszabolcs, Tisza-Szeged.

**Nyitott falak** (a `NYITOTT_FALAK` listában, a lap alján is megjelenik): Hernád,
Kraszna, Fekete-Körös, Berettyó — ezek hiánya a maradéktagban jelenik meg.

## Paks — vízoldal, nem energia

A blokkteljesítmény egyetlen célt szolgál: a hűtővízkivétel ne konstans legyen.
Névleges üzemben ~100 m³/s kondenzátorhűtés, leállított blokkoknál ~100 m³/**perc**
fenntartó hűtés — hatvanszoros különbség. A v1 ezt konstansként kezelte, tévesen.

Két vízoldali fal, mindkettő a lapon: a vízszint (a szívócsonk fix magasságban van)
és a vízhő (a melegvíz-csatorna torkolatától 500 m-re a Duna nem lehet 30 °C-nál melegebb).

Semmilyen egyéb energiaadatot nem tárolunk. Ha nincs víz, nincs áram — de a lap a vízről szól.

## Nyitott kérdések

1. **Scraping**: a vizugy.hu-nak nincs dokumentált nyílt API-ja; a parser a HTML-táblára
   támaszkodik. Adatigénylést érdemes indítani az OVF-nél.
2. **LKV frissessége**: a mércék adatlapján szereplő „Legkisebb vízállás" hivatalos érték,
   de nem tudni, mikor frissítették utoljára. A „mérce a kisvíz alatt" állítás ezen áll.
3. **Kivétel-adatok**: az öntözés, ivóvíz és ipari hűtés még nagyságrendi helyőrző;
   a valódit a vízgyűjtő-gazdálkodási terv és a vízjogi engedélyek adják.
4. **Hozamgörbék pontossága**: a cm → m³/s átváltás a mederbevágódással vándorol.
   A közeli be/ki egyensúlyt ezért nem szabad túlértelmezni.

## Ami szándékosan így van

- A készletváltozás **maradéktagként** áll elő, nem bemenetként.
- A 3. panel nem a vizet méri, hanem a mérésrendszer hiányát.
- Három óra a fejlécben (óras / napi / havi) — a mérleg három sebességből áll össze.
  A három számlap maga a disclaimer.

## Idézhetőség

A módszertan menjen Zenodóra DOI-val; a dashboard arra hivatkozzon vissza.
A holadelej.hu CC BY 4.0 — a forrásmegjelölés a lap alján kötelező marad.
