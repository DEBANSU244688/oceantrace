# EVALUATOR BRIEF — OceanTrace

**What to say, what's real, what's deliberately not built, and what an evaluator
will probably poke at.** Read alongside `next_steps.md` (what's left).

---

## The 30-second version

> Marine oil spills usually go unattributed. OceanTrace takes one satellite SAR
> image and produces a ranked list of suspect vessels: it detects and measures
> the slick, runs a particle drift model backward to find where and when the
> spill started, then filters historic AIS traffic through that origin and time
> window and scores every vessel on proximity, trajectory and behavioural
> anomalies — with a plain-language reason for each flag.

Every click in the demo is a real HTTP call from React to FastAPI. Open the
browser Network tab if asked — nothing in the flow is mocked frontend data.

---

## The demo, in the order you should run it

1. **Pick a tile** — three real Sentinel-1 tiles plus a synthetic fallback in
   the selector. Each one is an observation of a *different* spill event in the
   region. Or hit **upload** and let them hand you an image.
2. **Detect spill** — the real SAR tile appears on the map, georeferenced, with
   the detected polygon on top. Area, perimeter, centroid, confidence, and a
   look-alike note in the panel. **Drag the SAR opacity slider down** — that is
   the single most convincing three seconds in the demo, because it shows the
   polygon tracking the actual slick rather than being drawn from an answer key.
3. **Trace origin** — the backward drift animates along the drift axis, then
   resolves into 150 advected particles and an uncertainty circle. Say out loud:
   *"the origin is a probability cloud, not a point."* The estimated slick age
   appears alongside the spill window.
4. **Analyse AIS** — the funnel narrows 26 → 2 → 2 → 2 and the ranked list
   appears.
5. **Click the top vessel** — its track is drawn, and the why-flagged panel
   lists the reasons in plain language.
6. **Now switch to a different tile and run it again.** Different origin,
   different spill window, different vessel caught. This is the single most
   important thing to show, and the reason it exists is in the next section.

Whole flow runs in about half a second. `PRD.md` allows 60.

### Why step 6 matters more than the rest

An earlier version of this build anchored every tile to the same location, so
every image produced the same origin, the same funnel and the same culprit.
The code was honest — nothing read the answer at runtime — but the *observable
behaviour* was identical to a hardcoded result, and no amount of explaining
would have fixed that in front of someone who tried two images.

The region now carries four separate spill events. Each tile is bound to one,
origins are 35+ km apart, and each event has its own guilty vessel:

| Tile | Event | Culprit |
|---|---|---|
| `s1_371` | Paradip approach | BAY VOYAGER |
| `s1_485` | Outer anchorage | MV KALINGA PRIDE |
| `s1_473` | Southern lane | ORIENT MARINER |
| `sar_001` | Deep-water crossing | MV SILVER TIDE |

Notice on the second tile that BAY VOYAGER is still in the list — down at 38,
because it's in the region but nowhere near *that* origin at *that* time. The
scoring is doing real work, not selecting a pre-chosen winner.

---

## What is implemented

### 1. Detection — `detector.py`

Classical computer vision, no trained model:
Gaussian denoise → **Otsu** thresholding (inverted — oil is *darker* than open
water in SAR backscatter, because it flattens capillary waves and drops radar
return) → morphological open/close to kill speckle → contour extraction →
pick the best candidate by `area × compactness`.

**Look-alike risk (S4).** Oil is not the only thing that goes dark in SAR —
low-wind areas, biogenic slicks, rain cells and current fronts all suppress
backscatter the same way, and they are the dominant false-positive source in
real operational use. We don't have a classifier for them and don't claim to.
What we report is how *contested* the detection was, from two signals already
in hand: **ambiguity** (how close the runner-up dark region scored to the
winner) and **faintness** (contrast against the scene mean). That risk value
lowers the reported confidence and produces the note in the panel — it isn't a
separate number nobody looks at.

### 2. Characterisation — `characterize.py`

Contour → Shapely polygon → area (km²), perimeter (km), centroid (lat/lon), via
a local equirectangular projection. Handles any tile size.

### 3. Drift — `drift_engine.py`

Physics-based **particle advection**, pure NumPy. 150 particles stepped every
30 min under a combined current+wind vector plus per-particle random diffusion.

- **Backward** → origin probability cloud. Cloud centroid = probable origin,
  90th-percentile spread = uncertainty radius. Both the cloud and the backward
  path are drawn on the map.
- **Forward** → predicted slick path (SHOULD item S1).
- **Slick age estimate (S2)** — measured from the slick's *own shape*: a spill
  advected for T hours is smeared into a streak about `v × T` long, so the
  extent along the drift axis divided by drift speed gives an age. Confidence
  comes from elongation — a long thin streak is strong evidence of directional
  drift, a round blob carries almost no temporal information and we say so
  rather than quoting a firm number. **This is independent of the assumed
  satellite-pass lag**, which is the point: on the synthetic tile it returns
  3.1 h against an assumed 4.0 h, two separate routes to roughly the same
  answer.

### 4. AIS funnel + attribution — `attribution.py`

26-vessel synthetic roster, 60 h of positions at 20-minute intervals.
Three-stage funnel — **spatial → temporal → trajectory** — then a weighted
score over eight sub-scores:

| Sub-score | Weight | How it's computed |
|---|---|---|
| Spatial | 0.25 | closest approach to origin *during the window* |
| Temporal | 0.20 | time offset between closest approach and the window |
| Trajectory | 0.20 | closest approach at *any* time (does the path cross the zone) |
| Speed anomaly | 0.10 | speed drop vs the vessel's own median speed |
| Course anomaly | 0.10 | mean course change near the closest approach |
| Loitering | 0.05 | did it come to a stop near the origin |
| AIS transmission gap | 0.05 | largest gap between position reports |
| Vessel type | 0.05 | tanker 0.9 / cargo 0.6 / fishing 0.2 |

Weights sum to 1.00. **The "why flagged" text is generated from the same
numbers the score is built from** — there is no separate explanation layer that
could disagree with the score. That is the honest answer to "is this
explainable?"

### 5. API — `main.py` (FastAPI)

Eight endpoints, contract frozen in `SACD.md` §3, auto-documented at `/docs`:
`/health`, `/api/scenario`, `/api/images/{id}`, `/api/detect`,
`/api/detect/upload`, `/api/drift`, `/api/attribution`, `/api/vessels/{id}`.
In-memory state — no database server, per `DB.md`.

### 6. The attribution gate — it refuses to accuse when unsure

Otsu always returns the darkest region in a frame, so a tile with **no oil in
it** still yields a polygon. Left alone the pipeline would hindcast that
non-existent slick and name a real vessel as responsible. That is the worst
failure this system has available: not a missed detection, a false accusation.

So a detection has to clear a bar — **confidence ≥ 40% and look-alike risk
≤ 60%** — before `/api/drift` or `/api/attribution` will touch it. Both return
**409** otherwise, and the UI greys out the steps and prints the reason.
Enforced server-side, not just in the frontend, because a rule that only lives
in the UI is not a rule.

The thresholds are measured against the dataset's own labels, not guessed:

| | blocked by the gate |
|---|---|
| 60 tiles the dataset labels **no oil** | **60 / 60 (100%)** |
| 60 tiles that **do** contain oil | 12 / 60 (20%) |

Reproduce with `python scripts/validate_detector.py --gate`. The asymmetry is
the argument: declining to attribute a real spill costs an analyst a second
look; attributing one that never happened costs a ship operator their
reputation. (The detector already refused outright on 28 of those 60 no-oil
tiles — no region above the size threshold at all. The gate catches the rest.)

### 7. Real ocean forcing

The drift model is no longer driven by a number we chose. Real hourly current
and wind, per event, per date, from Open-Meteo. Cached to disk so the demo runs
with no internet. Fallback to the old static vector if the cache is missing, so
a fresh clone still works.

Say it like this: *"The physics was always real — particle advection is what a
production system does. What used to be a guess was the forcing. Now that's
real too, and it's why these four events drift in four different directions."*

### 8. Upload your own image

Same pipeline; the detector doesn't care where its pixels came from. An upload
carries no geocoding, so it's anchored at the scenario location exactly the way
the downloaded Zenodo tiles are — which keeps drift and AIS meaningful instead
of dead-ending after detection. Non-images are rejected with a 415, images with
no slick-like region with a 422.

### 9. Frontend — React + Vite + react-leaflet

Minimalist dark UI, three-step linear flow. SAR tile as a georeferenced
`<ImageOverlay>` under the polygon with an opacity slider; animated backward
drift; particle cloud; tile selector and upload; funnel counter; ranked vessel
list; why-flagged panel. Light and dark themes, following the OS preference
with a header toggle that overrides and persists; the light palette clears
WCAG AA on every token.

---

## Numbers you can quote

| Claim | Number |
|---|---|
| Detector accuracy vs the dataset's own ground-truth masks | **mean IoU 0.43, median 0.41, 27/70 tiles above 0.5** |
| Origin recovery vs scenario ground truth | within **~50 m** (tested: 0.03–0.11 km) |
| Spill window recovery | **exact** |
| Guilty vessel score vs next-highest | **0.94 vs 0.50** |
| Full flow, detect → vessel detail | **~0.5 s** (`PRD.md` allows 60 s) |
| Distinct results across the four tiles | **4 origins, 4 windows, 4 culprits** |
| No-oil tiles blocked from attribution | **60/60 (100%)**, costing 20% of real slicks |
| Automated pipeline checks passing | **78/78**, including the gate and upload paths |

Two things you can run live if challenged:

- `python scripts/validate_detector.py` — scores `detector.py` against labels
  shipped by the same Zenodo record. **We did not grade our own homework.**
- `python scripts/smoke_test.py` — 78 assertions over the live HTTP API.
- `python scripts/validate_detector.py --gate` — measures the refusal gate
  against tiles the dataset labels as containing no oil.

---

## What is synthetic, and why — say this before they ask

Volunteering the cuts reads as engineering judgement. Being caught hiding them
reads as the opposite.

1. **AIS data is synthetic.** The problem statement explicitly permits it:
   *"Real AIS if available may be used else synthetic data can be prepared."*
   Real historic AIS matched to a specific spill isn't obtainable in this
   window. The roster is built to test the funnel properly — one guilty vessel,
   three near-misses (right place, wrong time), three false positives (right
   time, wrong place), 19 clean background tracks. A funnel that only ever
   returned one result would prove nothing.

2. ~~**The current/wind field is a static vector**~~ — **no longer true, and
   worth saying so.** The drift engine runs on the real hourly ocean current
   and 10 m wind over each event's own coordinates and dates (Open-Meteo, free,
   no key), cached so the demo still works offline. Drift is `current + 3% ×
   wind`, the conventional windage for oil. The four events drift at 0.64–2.19
   km/h on bearings from 204° to 324° — you can see the paths curve on the map.
   The hindcast inverts that same series and recovers the origin to 22–91 m,
   which is a real inversion rather than undoing a constant.

3. **Tile georeferencing is the demo scenario's, not the tile's.** The Zenodo
   tiles are crops shipped with no geocoding, so there is no true lat/lon to
   recover. Each tile is anchored so its detected slick sits on *its own
   event's* origin, at 10 m/px (Sentinel-1 IW GRD nominal). **The pixels are
   real Sentinel-1 backscatter; the position is ours.** That is what lets real
   imagery compose with a synthetic AIS roster. Four events rather than one is
   a deliberate reversal of a line on `BL.md`'s WON'T list — annotated there
   with the reason.

4. **Classical CV, not deep learning.** Training and validating a segmentation
   model eats the whole budget for marginal demo benefit. We measured what the
   classical approach actually achieves instead — see the IoU number.

---

## Not built

**One SHOULD item is complete-adjacent but unpolished:** per-vessel score
breakdown bars. The eight sub-scores are in the API response and drive the
reasons text, but the UI shows the reasons rather than the bars.

**Still genuinely open:**

- **Offline basemap.** `PRD.md` §5 says the demo must run with no internet, but
  the basemap comes from CARTO. The map now detects tile failures and says
  "basemap offline" instead of rendering a silent black void, and every data
  layer still draws — but the tiles themselves aren't cached. Degraded, not
  solved. **Test the venue wifi.**
- **Rehearsal and a backup video.** `PP.md` Phase E. Not done. The 60-second
  target is verified by script, not by a human driving it.
- **`docs/` is untracked in git.** The whole planning set.
- **Reconciling the second, parallel HTML/JS build** of this same project.

**Explicitly out of scope** (`BL.md` WON'T): live AIS ingestion, multi-spill
support, auth, persistence across restarts, deployment pipeline, mobile app.

---

## Questions to expect

**"Does it only work on that one cherry-picked image?"**
Four tiles in the selector, three real Sentinel-1 — run any of them. Then hand
them the upload button. And the IoU script scores 70 random tiles, not
hand-picked ones.

**"How do you know the detection is right?"**
Scored against the dataset's own ground-truth masks: mean IoU 0.43 with no
training. Then drag the opacity slider and let them watch the polygon sit on
the slick.

**"Isn't the answer hardcoded?"**
Best answered by doing rather than explaining: **switch the tile and run it
again.** Different origin, different spill window, different vessel caught —
four tiles, four culprits. Then point out that the previous tile's culprit is
still in the ranked list, just scored down, because it was in the region but
not near *this* origin at *this* time.

Then the supporting detail: the scoring formula runs over generated AIS; the
detector recovers the centroid from pixels. Nothing reads ground truth at
runtime — `config.py` holds it only so the *generators* can build the
scenario, and the pipeline's job is to rediscover it. Open the Network tab and
watch the calls.

**"Can I try my own image?"**
Yes — and you have seven real tiles ready in `backend/data/demo_uploads/` that
the app has never seen, including two with no oil in them. Lead with
`01_sentinel1_strong_slick.png`, then `03_palsar_different_satellite.png`
(*"this one isn't even Sentinel-1 — different satellite, different band"*).

**Be precise about one thing here.** An uploaded tile carries no geocoding, so
*we* choose where to put it — the app rotates through the four events and the
panel says which one it used ("uploaded · placed at Outer anchorage"). What the
upload genuinely tests is the detection and characterisation; the attribution
that follows is against whichever event we dropped it into. Say that plainly.
Claiming the upload proves the attribution too is the one overclaim available
here, and it is not worth making.

**"What if I upload something that isn't a SAR image?"**
Be straight: *"It will still find something, because Otsu always finds the
darkest region — that's why we report look-alike risk rather than just a
confidence number."* Then show them the note. Owning this is far stronger than
being caught by it. A non-image file is rejected outright.

**"Show me it failing."** — *this is your best moment, do not skip it*
Upload `06_no_oil_lookalikes_only.png`. The dataset labels that tile as
containing no oil. The detector still outlines the darkest region, because Otsu
always finds something — but the detection scores 31% against a 40% floor, so
**Trace origin and Analyse AIS grey out and the panel says why**. Try it from
`/docs` instead and the API returns 409.

Then give them the number: the gate blocks 100% of no-oil tiles, at the cost of
20% of genuine slicks, measured against the dataset's own labels. And the line
that explains the choice:

> *"Declining to attribute a real spill costs an analyst a second look.
> Attributing one that never happened costs a ship operator their reputation.
> We picked which error to make."*

A system that knows when to stay quiet is a much stronger result than one that
always produces an answer.

**"Your slick age says 1 hour but the window is 4 hours — which is it?"**
Two different measurements, deliberately. The window comes from the assumed
satellite-pass lag; the age comes from the slick's own geometry. On the
synthetic tile they agree closely (3.1 h vs 4.0 h). On a small real crop the
geometry estimate is low *and reports low confidence*, which is the system
being honest rather than confident and wrong.

**"Why not deep learning?"**
Time budget — and we can tell you what classical CV actually scores. A trained
model is the obvious next sprint; the detector sits behind a fixed interface,
so swapping it changes nothing downstream.

**"What would you do next?"**
Real ocean currents from Copernicus, a trained segmentation model, live AIS
ingestion, multi-spill support. In that order.
