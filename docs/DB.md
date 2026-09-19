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
| polygon_geojson | text/json | detected slick boundary |
| area_km2 | float | |
| perimeter_km | float | |
| centroid_lat, centroid_lon | float | |
| confidence | float 0–1 | detection confidence |
| est_age_min_hr, est_age_max_hr | float | optional (SHOULD item) |
| age_confidence | float 0–1 | optional |

## 2. `origin_zones`
| field | type | notes |
|---|---|---|
| origin_id | PK, text | |
| spill_id | FK → spills | |
| origin_lat, origin_lon | float | most-probable point (particle-cloud peak) |
| radius_km | float | uncertainty radius shown on the map |
| origin_confidence | float 0–1 | |
| spill_window_start, spill_window_end | timestamp | estimated emergence window |
| particle_cloud_geojson | text/json | for the probability-heatmap visual |
| forecast_path_geojson | text/json | optional (S1) |

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

## 6. What's deliberately NOT here
No user table, no session table, no auth, no multi-spill history beyond what's needed to
demo — this is a single-scenario demo data model, not a product schema. The FastAPI process
holding this in memory for the length of the demo is a *feature* here, not a shortcut to
apologise for.
