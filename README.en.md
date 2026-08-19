# basin.equora.institute — water balance

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21852060.svg)](https://doi.org/10.5281/zenodo.21852060)

An open water-balance monitoring system for Hungary, the measurable slice of the
Middle Danube Basin. Every quantity carries a **provenance label**, so the reader
always knows whether a number was measured, derived, modelled, or is a placeholder.

**Live:** https://basin.equora.institute
**Hungarian documentation:** `README.md`, `MODSZERTAN.md`
**Methodology (English):** `METHODOLOGY.md`

## What it measures

| Quantity | Status | Source | Cadence |
|---|---|---|---|
| Water level, discharge, temperature | **measured** | OVF open API, 22 gauges | 15 min |
| Precipitation | **measured** | HungaroMet ground network, 269 stations | daily |
| Precipitation (cross-check) | satellite estimate | GPM IMERG Early | daily |
| Evapotranspiration | satellite measurement | EUMETSAT LSA SAF DMETv3 | daily |
| ET (cross-check) | reanalysis | ECMWF ERA5-Land | daily, 5–6 day lag |
| Reference ET | satellite measurement | LSA SAF METREF (FAO-56) | daily |
| Root-zone soil water deficit | **measured** | OVF Drought Monitoring, 127 stations | daily |
| Groundwater depth | **measured** | OVF open API, 487 wells | daily |
| Total water storage anomaly | satellite measurement | NASA GRACE/GRACE-FO | monthly |
| Paks cooling-water withdrawal | derived | reactor output (holadelej.hu, CC BY 4.0) | 30 min |
| Running balance since 2021 | **placeholder** | to be computed from GRACE + OVF | — |
| Daily closure residual | residual term | from the other terms; not a measurement | daily |

## Why the precipitation source changed (v1.2.0)

The satellite product systematically overestimates summer convective rainfall: it
reads high, ice-topped clouds as precipitation even when the water evaporates
before reaching the ground.

On 2026-08-17 GPM IMERG Early reported **3.92 mm/day** where the 269-station ground
network measured **1.43**. Switching the primary source reduced the unclosed term of
the balance from **4186 to 1505 m³/s**. The satellite estimate is retained as a
cross-check — the discrepancy is itself data.

## What the system does not know

The balance is written for Hungary, not the whole basin. Several inflows are not
yet instrumented: the Hernád, Kraszna, Fekete-Körös and Berettyó rivers, and
transboundary groundwater flow. These appear in the residual term, which is why the
page names it *daily closure residual* rather than storage change.

The running balance since 2021 is a placeholder, and the page says so.

## Licence

Code and text: CC BY 4.0. Source data belongs to the originating institutions,
each named on the page and in `MODSZERTAN.md`.

## Citation

> Papp L. (2026). *Water balance of the Middle Danube Basin: an open,
> provenance-labelled monitoring method.* EQUORA Institute. Zenodo.
> https://doi.org/10.5281/zenodo.21852060
