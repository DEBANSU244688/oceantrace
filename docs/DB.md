# DB — Data Storage Design
**OceanTrace · minimal by design — don't let this eat build hours**

## 0. Recommendation
Skip a real database server entirely. FastAPI is a long-running process, so — unlike a
rerun-per-interaction model — a plain in-process store persists naturally across requests
with no extra work:
1. **In-memory Pandas DataFrames / dicts** at module level in the FastAPI app — populate on
   first request or at startup, keyed by `spill_id`. Simplest, zero setup, and survives for
   the whole demo session as long as the server process isn't restarted.
2. **SQLite** (single file, no server) — only worth it if you specifically want results to
   survive a backend restart mid-demo. Not needed for a single rehearsed scenario.

Either way, the schema below is the same — it's just "table structure" whether it lands in
a `CREATE TABLE` or a `pd.DataFrame`/dict keyed by ID.

## 1. `spills`
| field | type | notes |
|---|---|---|
| spill_id | PK, text | e.g. `SP-001` |
| image_source | text | filename / dataset reference |
| scenario_id | text | which spill event this image observes (`sc_01`…`sc_04`) |
| source | text | `sample` or `upload` |
| polygon_geojson | text/json | detected slick boundary |
| area_km2 | float | |
| perimeter_km | float | |
| centroid_lat, centroid_lon | float | |
| confidence | float 0–1 | detection confidence, *after* the look-alike penalty |
| candidate_regions | int | dark regions that survived thresholding (S4) |
| rejected_lookalikes | int | …of which this many lost to the winner (S4) |
| lookalike_risk | float 0–1 | ambiguity + faintness; also lowers `confidence` (S4) |
| lookalike_note | text | the plain sentence shown in the panel |
| attributable | bool | did it clear the gate? false ⇒ drift/attribution return 409 |
| attribution_block_reason | text | shown to the user when `attributable` is false |
| image_bbox | json | the tile's geographic footprint, for the map overlay |

The age estimate lives on the drift result rather than here — it is derived from the
polygon at drift time, not stored at detection.

## 2. `origin_zones`
| field | type | notes |
|---|---|---|
| origin_id | PK, text | |
| spill_id | FK → spills | |
| origin_lat, origin_lon | float | most-probable point (particle-cloud peak) |
| radius_km | float | uncertainty radius shown on the map |
| origin_confidence | float 0–1 | |
| spill_window_start, spill_window_end | timestamp | estimated emergence window |
| particle_cloud_geojson | text/json | 150 advected particles, drawn on the map |
| forecast_path_geojson | text/json | S1 — forward run |
| hindcast_path_geojson | text/json | backward run's centroid track, for the animation |
| estimated_age_hours | float | S2 — from the slick's extent along the drift axis |
| age_confidence | float 0–1 | S2 — from the slick's elongation |

## 3. `vessels` (synthetic AIS roster — static per demo scenario)
| field | type | notes |
|---|---|---|
| vessel_id | PK, text | synthetic MMSI-style ID |
| name | text | e.g. "MV OCEAN STAR" |
| type | text | tanker / cargo / fishing etc. |

## 4. `ais_positions` (synthetic AIS time series)
| field | type | notes |
|---|---|---|
| position_id | PK | |
| vessel_id | FK → vessels | |
| ts | timestamp | |
| lat, lon | float | |
| speed_knots | float | |
| course_deg | float | |
| status | text | underway / stopped |

## 5. `vessel_scores` (attribution output — this is what `/api/attribution` serialises)
| field | type | notes |
|---|---|---|
| score_id | PK | |
| spill_id | FK → spills | |
| vessel_id | FK → vessels | |
| spatial_score, temporal_score, trajectory_score | float 0–1 | |
| speed_anomaly_score, course_anomaly_score | float 0–1 | |
| loitering_score, ais_anomaly_score, vessel_type_score | float 0–1 | |
| total_risk_score | float 0–1 | weighted sum, see formula in `MASTER_REFERENCE_INDEX.md` |
| rank | int | |
| reasons | text[] | short bullet strings for the "why flagged" panel |

## 5b. Reference data on disk (not a table, but it is state)

| file | what | built by |
|---|---|---|
| `data/sample_images/` | the SAR tiles + their bounding boxes | `fetch_sar_tiles.py` |
| `data/demo_uploads/` | tiles for the upload button, incl. two with no oil | `fetch_demo_uploads.py` |
| `data/ocean_forcing.json` | real hourly current + wind per event | `fetch_ocean_forcing.py` |
| `data/coastline.geojson` | public-domain land polygons, the offline basemap | `fetch_coastline.py` |
| `data/vessels.json`, `ais_positions.csv` | the synthetic AIS roster and tracks | `generate_ais.py` |

All are committed, so a fresh clone runs without executing a single script. The scripts
only need re-running when `app/config.py` changes.

Uploaded images are held in a module-level dict keyed by `upload_NNN` and deliberately do
not outlive the process.

## 6. What's deliberately NOT here
No user table, no session table, no auth, no multi-spill history beyond what's needed to
demo — this is a single-scenario demo data model, not a product schema. The FastAPI process
holding this in memory for the length of the demo is a *feature* here, not a shortcut to
apologise for.
