# Water balance of the Middle Danube Basin

## An open, provenance-labelled monitoring method

**László Papp** · EQUORA Institute · ORCID 0009-0005-6329-5808
Live interface: https://basin.equora.institute
Full methodology (Hungarian): `MODSZERTAN.md`

---

## Summary

This project publishes a continuously updated water balance for the Middle Danube Basin.
The basin forms an almost closed hydrological box: the Danube enters at Devín and leaves
at Baziaş, while the catchments of the Tisza, Drava, Sava and Morava lie entirely inside.
Every term of the balance carries a **provenance label** — in-situ measurement, derived
from in-situ data, satellite estimate, computed, or placeholder — and the interface
reports missing knowledge as an explicit number rather than hiding it. The central design
decision is that **storage change is derived as a residual**: the resulting discrepancy
therefore measures how closed our observation system is, rather than pretending to
measure water.

---

## 1. The box

| | area | walls | status |
|---|---|---|---|
| `hu` Hungary | 93,030 km² | 11 inflow and 3 outflow Hungarian gauges, hourly discharge | **active** |
| `mdb` Middle Danube Basin | ~445,900 km² | Danube at Devín (SHMÚ) and Danube at Baziaş (INHGA) | walls connected, box not yet active |

**The area derivation and the measured cross-section are two different things.** The
~445,900 km² figure follows from the Iron Gate I catchment (577,250 km²) minus the
Danube catchment at Devín (~131,350 km²) — the basin boundary as used in the literature.
The cross-section we actually **measure**, however, is **Baziaş** (rkm 1072), located
downstream of the Tisza, Sava and Velika Morava confluences but **upstream** of the Iron
Gate dam. Inflow along the reach between Baziaş and the Iron Gate is therefore excluded;
this appears among the open items.

**Hungary is the active box because the spatial mask follows the national boundary.**
Precipitation and evapotranspiration scale with area, so switching the box requires
replacing the mask with a catchment polygon (HydroSHEDS/HydroBASINS). A second obstacle
is cadence: the Baziaş discharge is published daily, so the `mdb` balance would run at
daily resolution.

**Open walls of the Hungarian box:** Hernád, Kraszna, Fekete-Körös, Berettyó, and
transboundary groundwater flow. These surface in the residual term.

---

## 2. Balance equation and sign convention

    P + Q_in − ET − Q_out − consumptive_abstraction = ΔS

Terms entering the box are positive, terms leaving it are negative. The sum of the five
terms yields the storage change.

**ΔS is a residual, not an input.** This inverts the usual construction of water
balances, and it is deliberate: the discrepancy that appears in the balance tells the
reader how much the remaining terms can be trusted.

---

## 3. Terms and the five provenance classes

| Term | Source | Cadence | Class |
|---|---|---|---|
| Water level, water temperature | OVF National Hydrological Forecasting Service | hourly | in-situ measurement |
| Discharge | OVF, from stage via rating curve | hourly | derived from in-situ data |
| Soil water deficit | OVF Drought Monitoring, WD35 and WD80 | daily | in-situ measurement |
| Precipitation | GPM IMERG Early, 0.1° | daily | satellite estimate |
| Evapotranspiration | EUMETSAT LSA SAF DMETv3, 0.05° | daily | satellite estimate |
| Reference ET | EUMETSAT LSA SAF METREF | daily | satellite estimate |
| Storage anomaly | NASA/JPL GRACE and GRACE-FO mascon | monthly, 40–60 day latency | satellite estimate |
| Basin walls | SHMÚ Devín, INHGA Baziaş | daily | derived from in-situ data |
| Water abstraction | annual statistics × monthly profile × consumptive fraction | daily | computed |
| Paks cooling water | scaled from unit output | 30 min | computed |
| Storage change | residual | daily | computed |

### What the classes mean

- **in-situ measurement** — an instrument measured it on site. Example: stage at Paks,
  in centimetres.
- **derived from in-situ data** — river discharge: from in-situ stage via a calibrated
  rating curve. It receives its own class because rating curves drift with channel
  incision — the same process that lifted the Paks intake structures above the water
  surface.
- **satellite estimate** — retrieved from satellite measurements through a model.
  Example: evapotranspiration from Meteosat radiation data; GRACE from mass-anomaly
  inversion at roughly 300 km native resolution.
- **computed** — derived from other terms under stated assumptions. Example: August
  irrigation from the monthly distribution of an annual 154 million m³.
- **placeholder** — order-of-magnitude estimate pending a real source.

**The class is assigned at the source; the interface only displays it.** Each retrieval
script writes it into `params.json`, and `fetch_data.py` passes it through without
overriding. This rule followed a bug in which the interface layer silently downgraded a
computed term to placeholder.

### Three clocks in the header

The balance combines data at three speeds: **hourly** (stage, discharge, water
temperature), **daily** (precipitation, ET), **monthly** (storage change). The three
clocks are the caveat made visual. Each date is read from the data itself, so a stalled
source becomes visible in the header immediately.

The system raises an error if the precipitation and ET dates diverge: the terms of one
balance belong to one day.

---

## 4. Spatial averaging

Precipitation and ET are averaged under a **national boundary mask** built from the
Natural Earth 10m administrative boundary, using a ray-casting point-in-polygon test and
weighting each cell by its true spherical area.

**Verification:** the masked area on a 0.05° grid is 93,218 km², a 0.2% deviation from
the official 93,030 km².

**Magnitude of the correction:** the earlier bounding box covered 223,000 km², so the
masked area is 42% of it — 58% of the bounding-box average came from foreign territory.
The switch changed daily ET from 2.20 to 1.90 mm, a 14% systematic bias.

---

## 5. The two walls of the full basin

`kulfold.py` reads the box walls from two public sources:

| Wall | Source | Format | Example (2026-08-07) |
|---|---|---|---|
| Inflow — Danube, Devín | SHMÚ daily report | table: stage, discharge, water temperature | 981.0 m³/s |
| Outflow — Danube, Baziaş | INHGA daily bulletin | prose | 1,400.0 m³/s |

**Basin contribution: 419 m³/s** — the combined addition of the Tisza, Drava, Sava,
Morava and all internal inflow across roughly 446,000 km². The outflow stands at **36%**
of the long-term August mean (3,900 m³/s).

**Two caveats.** Both sources are operational, uncorrected data; SHMÚ states this
explicitly. The Baziaş discharge is extracted from the *prose* of the bulletin, so the
pattern is fragile — if the wording changes, the script fails loudly rather than writing
a wrong value silently.

**The Danube profile and the Gabčíkovo effect.** The SHMÚ report also yields the profile
upstream of the Hungarian reach: Devín 981 → Medveďov 722 → Komárno 761 → Štúrovo
790 m³/s. The 259 m³/s drop between Devín and Medveďov follows from the operating regime
of the Gabčíkovo scheme, where most of the flow travels through the power canal. This is
an operational redistribution, not a water loss.

---

## 6. Paks as a threshold node

The Paks nuclear plant receives its own section because it is the one point in the
country where a few centimetres of stage and a few tenths of a degree of water
temperature can **constrain electricity generation**. Every other term of the balance
concerns quantity; this one concerns thresholds.

**Two water-side limits:** the elevation of the pump intake structures, and the 30 °C
thermal load limit measured 500 m downstream of the warm-water canal outfall.

**Cooling water abstraction is state-dependent.** Condenser cooling at nominal output is
roughly 100 m³/s; residual cooling of shut-down units is roughly 100 m³ per **minute** —
a factor of sixty. Unit output serves this scaling and nothing else.

---

## 7. Abstraction: gross and consumptive

Annual statistical volumes are converted to daily values through a monthly profile, then
multiplied by a consumptive fraction.

| Item | Annual volume | Source | August abstraction | Consumptive |
|---|---|---|---|---|
| Fish ponds | 356 million m³ | State Audit Office, 2019–2023 mean | 22.6 m³/s | 15.8 |
| Agricultural irrigation | 154 million m³ | State Audit Office, 2019–2023 mean | 13.8 m³/s | 12.4 |
| Household drinking water | 38.7 m³/capita/year | HCSO, 2022 | 12.9 m³/s | 3.2 |
| Industry, excluding Paks | 290 million m³ | derived | 9.0 m³/s | 1.4 |
| Paks cooling water | state-dependent | scaled from unit output | 13.0 m³/s | 0.0 |
| **Total** | | | **71.3 m³/s** | **32.8** |

**The distinction matters.** Water supplied to fish ponds is a gross delivered volume:
part returns to the river system on drawdown, part recharges groundwater, and only a
fraction evaporates. Only the consumptive share enters the balance.

**The consumptive fractions are assumptions:** irrigation 90%, fish ponds 70%, household
25%, industry 15%. They lack a measurement basis; water resource levy declarations would
replace them with observed values.

**Irrigation statistics are incomplete.** The Hungarian Central Statistical Office states
that unpermitted abstraction is excluded, and studies estimate it at roughly double the
reported volume.

---

## 8. The soil compartment and residence time

The OVF drought monitoring network supplies the soil compartment: hourly soil moisture at
six depths (10–75 cm) and daily water deficit in **millimetres** (WD35, WD80).

**Example, 5 August 2026:** in the 80 cm layer the deficit reaches 35.0 mm at
Kiskunfélegyháza, 34.7 mm at Apaj and 18.3 mm at Csólyospálos; the five-station mean is
26.6 mm.

**Three compartments, three orders of magnitude:**

- **days** — the river. The Danube crosses Hungary in roughly one week.
- **weeks** — the soil. The deficit above accumulated over this span and can be
  replenished over a comparable span, from rainfall.
- **decades** — groundwater. The Danube–Tisza Interfluve ridge has fallen 2–5 m since the
  1970s, locally by 10 m.

**One substantive claim follows:** river flow and agricultural drought occupy different
compartments. Danube water circulates in the fast one while dryness deepens in the slow
one.

**The ratio of deficit to daily ET is a replenishment-time equivalent**, not a residence
time: it states how much rainfall would refill the root zone.

---

## 9. Irrigation demand versus actual abstraction

`ETc = Kc × ET_ref`, `deficit = max(0, ETc − ET_act)`, with Kc treated as a range
(0.8–1.2).

**Example, 4 August 2026:** reference ET 5.30 mm/day, actual ET 1.92 mm/day, water stress
index 0.36. Supplying 4.3 million hectares of arable land without water deficit would
require 100–191 million m³ per day — comparable to the total river inflow to the country.

A notable coincidence: the water stress index stands at 36%, and the Baziaş discharge
also stands at 36% of its long-term August mean. Two independent measurements point the
same way.

---

## 10. Scope of validity

1. **The box is Hungary.** The full-basin walls are connected; the switch depends on the
   mask and the cadence.
2. **The measured outflow is Baziaş; the area derivation uses the Iron Gate.** Inflow
   along the intervening reach is excluded.
3. **Abstraction is computed.** Annual volumes are referenced statistics; the monthly
   distribution and consumptive fractions are assumptions.
4. **Industrial abstraction is derived** by subtraction from total net abstraction.
5. **The currency of the record low water levels needs confirmation.** The claim that a
   gauge stands below its all-time low depends on when OVF last updated these values.
6. **GRACE resolves ~300 km**, with 40–60 day latency. Suitable for trends, less so for
   single months. Ten-year slope: −1.30 km³/year from 257 monthly points since April 2002.
7. **The mask follows the national boundary.** A catchment polygon is the next step.
8. **The drought monitoring endpoint was reverse-engineered** from the site's JavaScript.
9. **The Baziaş discharge is extracted from prose**, so the pattern is fragile.
10. **Rating curves drift with channel incision.**
11. **The two ET estimates diverge.** The difference appears as an explicit number and
    measures the openness of the observation system.
12. **Channel–groundwater exchange is an internal redistribution** and therefore does not
    inflate the residual — transboundary groundwater flow does, and we do not measure it.

---

## 11. Licensing

| Element | Licence |
|---|---|
| Code | MIT |
| Documentation | CC BY 4.0 |
| Copernicus / ERA5-Land | Copernicus licence, attribution required |
| EUMETSAT LSA SAF | CC BY 4.0, cite Trigo et al. (2011) |
| NASA GPM IMERG, GRACE-FO | open, attribution required |
| holadelej.hu (Paks unit status) | CC BY 4.0 |
| **OVF, SHMÚ, INHGA data** | **under clarification — data requests in progress** |

---

## 12. Reproducibility

    ./frissit.sh napi      # full daily cycle, seven sources
    ./frissit.sh oras      # gauges only

Credentials come from `~/.netrc` and `~/.cdsapirc`; the code contains no keys. The cycle
runs hourly in GitHub Actions. The `archiv/` directory accumulates our own daily series —
the only data in the project that cannot be regenerated.

---

## Citation

> Papp, L. (2026). *Water balance of the Middle Danube Basin: an open,
> provenance-labelled monitoring method.* EQUORA Institute. Zenodo.
> https://doi.org/10.5281/zenodo.21852060
