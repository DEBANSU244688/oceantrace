# PP — Project/Sprint Plan
**OceanTrace · 10-hour timeline, FastAPI + React**

Rule #1: plan for 40% of the full vision, build toward 60%. Never plan for 100%.

**Status: a working, tested scaffold already exists** (backend + frontend, full pipeline
verified against ground truth — see the repo). This changes the plan below significantly
from a from-scratch build: most of the original Phase 1 is already done. The 10 hours now
go toward real-data integration, the remaining SHOULD items, robustness, and rehearsal —
which is a meaningfully lower-risk position to start Round 2 from. Treat every phase below
as provisional — if the pre-round checklist (DRD.md §4) isn't fully done by the time the
clock starts, that eats into Phase A first.

## PHASE A — Environment check, not a build (0:00–0:30)
*Was "Foundation" in the original plan — now just proving everyone's laptop can run what
already exists.*
- Clone the repo, `pip install -r backend/requirements.txt`, `npm install` in `/frontend`
- Run both servers, confirm the existing flow still works end to end on each laptop:
  Detect → Trace Origin → Analyse AIS → click a vessel
- Confirm real Zenodo SAR image(s) are wired in per `DRD.md` §4 (should be done pre-round —
  if not, do it now, before anything else)

**CHECKPOINT (0:30)**: full flow runs clean on every laptop, on the real (not synthetic)
sample image. If any laptop can't get there, pair them with someone whose setup works
rather than debugging solo — don't let one environment issue eat the whole team's morning.

## PHASE B — Real-data integration + remaining SHOULD items (0:30–2:30)
S1 (forecast path) and S3 (why-flagged reasons) are **already built and tested** in the
scaffold — they're not tasks anymore, just verify they still render correctly with the real
image swapped in.
- Add 1–2 more real Zenodo sample images beyond the first, so the demo isn't a single
  cherry-picked case if a judge asks "does it only work on that one image?"
- **S2 — spill age estimate**: not yet built. A simple heuristic is enough (e.g. derived
  from the hindcast confidence/radius) — see `BL.md`, this is explicitly "if feasible"
- **S4 — look-alike confidence note**: not yet built. `detector.py` already scores/rejects
  decoy regions internally — surface that as a UI note ("N candidate regions found, M
  rejected as likely look-alikes") rather than building new detection logic

## PHASE C — UI/UX polish + robustness (2:30–5:00)
- Map interaction polish: legend, layer toggle, better vessel-click popups
- Refine loading/error states (already present, make them feel intentional not default)
- Re-run the full flow against every sample image added in Phase B — no crashes, no
  inconsistent-looking results between them

## PHASE D — Integration hardening (5:00–7:00)
- Cold-start test: kill and restart both servers, confirm a clean run from nothing
- Test on the actual presenting laptop + venue Wi-Fi if possible (the map's basemap tiles
  need internet — confirm that works at the venue, or pre-cache/screenshot a fallback)
- Fix laptop-specific quirks found in Phase A/C now, not during rehearsal

## PHASE E — Rehearsal (7:00–8:45)
- Full run-through of the demo script (`MASTER_REFERENCE_INDEX.md`), timed
- Fix ONLY what breaks in rehearsal — no new features
- Record a video/screenshot backup of a working run in case live demo, Wi-Fi, or CORS
  breaks in front of judges

## PHASE F — Buffer + code freeze (8:45–10:00)
- **Code freeze by 9:15–9:30. Non-negotiable.**
- Final checks: correct sample image loaded by default, browser zoomed/sized sensibly,
  backup video accessible offline

## Role split (assumes 4–6 people; merge if smaller — see TASKS.md)
| Role | Owns |
|---|---|
| R1 — Detection & CV | Phase B: real image swap, S4 look-alike note |
| R2 — Drift & Oceanography | Phase B: S2 age estimate |
| R3 — AIS & Attribution | Verify funnel/scoring holds up across the new sample images |
| R4 — React Frontend & Integration | Phase C UI polish, owns Phase D's cold-start test |
| R5 — Data prep & presentation | Owns Phase E rehearsal + backup recording |

If the team is 4 people, fold R5 into whichever of R1–R4 has the lightest load once Phase B
is done — don't merge R4, it still has the most integration surface area in this stack.
