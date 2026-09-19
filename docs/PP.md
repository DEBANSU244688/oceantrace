# PP — Project/Sprint Plan
**OceanTrace · 10-hour timeline, FastAPI + React**

Rule #1: plan for 40% of the full vision, build toward 60%. Never plan for 100%.

**Status: Phases A–D are done. What remains is Phase E (rehearsal) and Phase F
(freeze).** The phases below are kept as a record of what each covered and what
actually came out of it — a plan nobody revisits is worse than no plan.

The build now stands well beyond the original 60% target: all MUSTs, all four SHOULDs,
real Sentinel-1 imagery, real ocean forcing, four distinct spill events, an attribution
refusal gate, an upload path, an offline basemap, light/dark themes, and 78 automated
checks. That is a comfortable position — the risk has moved from *"will it work"* to
*"can we present it well"*, which is exactly what Phases E and F are for.

## PHASE A — Environment check, not a build (0:00–0:30)
*Was "Foundation" in the original plan — now just proving everyone's laptop can run what
already exists.*
- Clone the repo, `pip install -r backend/requirements.txt`, `npm install` in `/frontend`
- Run both servers, confirm the existing flow still works end to end on each laptop:
  Detect → Trace Origin → Analyse AIS → click a vessel
- Confirm real Zenodo SAR image(s) are wired in per `DRD.md` §4 (should be done pre-round —
  if not, do it now, before anything else)

**CHECKPOINT (0:30) — PARTLY MET.** The flow runs clean and does so on real Sentinel-1
imagery. What has *not* been done is confirming it on every teammate's laptop, and that is
not a formality: `python-multipart` was added for the upload endpoint, so an existing setup
fails at import until `pip install -r requirements.txt` is re-run. Use `python -m uvicorn`
rather than bare `uvicorn` where a laptop has more than one Python.

## PHASE B — Real-data integration + remaining SHOULD items — DONE
- ✅ Real Sentinel-1 tiles (three, plus a synthetic fallback), accuracy measured against
  the dataset's own masks at mean IoU 0.43
- ✅ **S2 age estimate** — from the slick's extent along the drift axis, independent of the
  assumed satellite-pass lag rather than a restatement of it
- ✅ **S4 look-alike note** — ambiguity + faintness, lowering the reported confidence
- ✅ Beyond plan: **real ocean forcing** (hourly current + 3% windage, Open-Meteo) replacing
  the invented drift vector, and **four distinct spill events** so switching tiles changes
  the origin and the culprit

## PHASE C — UI/UX polish + robustness — DONE
- ✅ Minimalist redesign; SAR tile under the polygon with an opacity slider; animated
  backward drift resolving into the particle cloud; map fits its data
- ✅ Light + dark themes, WCAG AA checked
- ✅ Loading and error states; refused detections disable the downstream steps and say why
- ✅ Full flow re-run against all four tiles and the upload path

## PHASE D — Integration hardening — MOSTLY DONE
- ✅ Cold-start test automated — `scripts/smoke_test.py`, 78 assertions over the live API
- ✅ Basemap no longer needs the venue's wifi: a public-domain Natural Earth coastline sits
  under the raster tiles, and the map says "basemap offline" instead of going black
- ✅ CORS widened to Vite's 5173–5176 fallback range; `/api/vessels/{id}` survives a reload
- ⬜ **Still to do: run it on the actual presenting laptop, on the venue network.**

## PHASE E — Rehearsal — NOT DONE, this is the priority
- Full run-through of the demo script (`MASTER_REFERENCE_INDEX.md`), timed
- Fix ONLY what breaks in rehearsal — no new features
- Record a video/screenshot backup of a working run in case live demo, Wi-Fi, or CORS
  breaks in front of judges

## PHASE F — Buffer + code freeze — NOT DONE
- **Code freeze by 9:15–9:30. Non-negotiable.**
- Final checks: correct sample image loaded by default, browser zoomed/sized sensibly,
  backup video accessible offline

## Role split (assumes 4–6 people; merge if smaller — see TASKS.md)
| Role | Owns |
|---|---|
| R1 — Detection & CV | ✅ done. Now: be the one who can explain the refusal gate |
| R2 — Drift & Oceanography | ✅ done. Now: be the one who can explain real forcing vs. the old constant |
| R3 — AIS & Attribution | ✅ done. Now: own the "isn't it hardcoded?" answer — switch tiles, show four culprits |
| R4 — React Frontend & Integration | ✅ done. Now: own the presenting laptop and the venue network test |
| R5 — Data prep & presentation | **Phase E rehearsal + backup recording. Nothing else is blocking.** |

If the team is 4 people, fold R5 into whichever of R1–R4 has the lightest load once Phase B
is done — don't merge R4, it still has the most integration surface area in this stack.
