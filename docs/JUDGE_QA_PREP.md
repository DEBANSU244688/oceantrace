# JUDGE Q&A PREP — OceanTrace

**SIH 2026 · PS 26143 (NTRO) · Team The HackerPunk**
Based on the questioning pattern seen with an adjacent satellite/disaster-response
team: intro → technical walkthrough → **orchestration** → **scalability** →
**impact**, where impact turned into *"where does the image actually come from?"*

Skim time: 5 minutes. One person should own each theme.

---

## If you read nothing else

| Theme | Readiness | The one line |
|---|---|---|
| Orchestration | **READY** | *"The API contract is the handoff. Four stages, one direction, no magic."* |
| Scalability | **PARTIAL** | *"Stateless workers + a queue. Our state is in-process today — that's the first thing to change."* |
| Real-time imagery | **GAP** | *"We don't task satellites. NTRO already can. We're the analysis layer that makes the image worth having."* |
| Prior art | **READY** | *"Most of this exists — CleanSeaNet, Cerulean, GNOME. We built the auditable attribution layer between them, and India has none."* |

**Never say "agents."** We don't have any. The word appears nowhere in our repo —
keep it that way. (See Theme 1.)

---

## Theme 1 — Orchestration / workflow

**Likely questions**
- Walk me through how the stages actually hand off to each other.
- Is this an agentic system? How do the agents coordinate?
- What happens if one stage fails?

**Readiness: READY.** The API contract in `SACD.md` §3 *is* the documented handoff,
it was frozen before anyone wrote code, and FastAPI auto-publishes it at `/docs`.
Open that tab if challenged. Nine endpoints now; the contract grew but never broke —
every addition was made in `SACD.md` first.

**Say this — the workflow, out loud:**

> "It's a four-stage pipeline, and each stage is a REST call the frontend makes in
> order. Detection takes an image ID and returns a slick polygon with area,
> perimeter, centroid and confidence. That centroid feeds the drift engine, which
> advects 150 particles backward through real hourly ocean current and wind for that
> location and date, to get an origin probability cloud and a spill time window. That origin and window feed the
> attribution stage, which filters the AIS roster spatially, then temporally, then
> by trajectory, and scores what survives on eight weighted factors. Each stage's
> output is a typed schema that's the next stage's input — so the handoff is a
> contract, not a convention. We froze it in the first fifteen minutes, which is
> why backend and frontend could be built in parallel without blocking."

**On "agents" — say this, confidently:**

> "No — and I want to be precise about that, because the word gets used loosely.
> This is a deterministic pipeline: classical computer vision, a physics-based
> particle model, and a rule-based scoring formula. Fixed order, no LLM, nothing
> choosing its own next step, no tool selection. Same input gives the same output
> every time. An agentic system would have a model deciding what to do next — we
> deliberately didn't build that, because for attribution you want a result you can
> audit line by line, not one you have to trust."

**If pushed**
- Failure handling: each stage returns a proper HTTP status — 422 when no slick is
  found, 409 when a detection fails the attribution gate, 404 on an unknown ID. The
  frontend shows the error rather than a blank map.
- State between calls is keyed by `spill_id`; `/api/vessels/{id}` takes it explicitly.
- `scripts/smoke_test.py` walks the whole chain over HTTP — 78 assertions.

---

## Theme 2 — Feasibility & scalability

**Likely questions**
- How would this scale to a whole coastline / many users?
- What breaks first under load?
- Could it handle multiple spills at once?

**Readiness: PARTIAL — and be honest about it.** Our state lives in module-level
dicts inside the FastAPI process (`store.py`, per `DB.md` §0). That's a deliberate
choice for a single-machine demo, but it means the service as written is **not**
horizontally scalable — two workers wouldn't share a spill. Don't claim it scales.
Claim you know exactly what to change, which is a better answer anyway.

**Say this:**

> "Today it's one FastAPI process holding state in memory, which is the right call
> for a demo and the wrong call for production. To scale it you'd make the workers
> stateless — move spill state into Redis or Postgres — and then you can put as many
> behind a load balancer as you want, because the work is per-request and
> embarrassingly parallel. The heavy part is the CV, so that comes out of the
> request path into a job queue: the API accepts the image, returns a job ID, and
> the client polls. Imagery goes to object storage rather than through the API. None
> of that is novel — it's the standard shape for this kind of workload."

**If pushed**
- **What breaks first:** the in-process store, then the synchronous CV. Our tiles are
  256×256; a full Sentinel-1 IW scene covers a 250 km swath and runs to hundreds of
  megapixels. That's the point where a queue stops being optional.
- **Multiple concurrent spills:** the data model already keys everything by
  `spill_id`, and the region already carries four independent spill events with four
  different culprits. What's missing is a UI for more than one at a time and a
  shared store — not a rethink.
- **AIS at real scale:** the funnel is a spatial-then-temporal filter, which is what
  a spatial index (PostGIS, or a geohash key) is built for. We cut PostGIS for the
  10-hour build; it's the obvious first addition.
- **Cost:** the pipeline runs in about half a second per spill on a laptop. This is
  not a compute-bound problem; it's a data-availability problem — which is Theme 3.

---

## Theme 3 — Impact: *"the user may not have the picture"*

**This is our real exposure.** `DRD.md` §1 builds on Zenodo's **archival** Sentinel-1
dataset. If the judge asks where the image comes from during an actual incident, we
have nothing in the build that answers it. Don't improvise — use the below.

**Likely questions**
- During a real spill, who gives you the satellite image, and how fast?
- Archival data is days old. What use is that in an emergency?
- Isn't the satellite the bottleneck, not your software?

**Readiness: GAP in the build, READY in the answer.** Frame it as a scope boundary
you chose, not something you overlooked.

**Say this:**

> "We deliberately don't solve satellite tasking, because that infrastructure already
> exists and our sponsor can already invoke it. The International Charter on Space
> and Major Disasters lets an authorised national agency trigger coordinated tasking
> across multiple operators' satellites over a specific area — ISRO is a member, and
> NTRO is exactly the kind of body that would be the authorised user. Domestically,
> ISRO and NRSC already run the Disaster Management Support programme feeding the
> National Database for Emergency Management, and that channel already delivers SAR
> imagery to national disaster bodies for floods and cyclones today. Europe has the
> same thing through Copernicus EMS. So the picture arrives through a pipe that's
> already built — an oil spill just needs to be a valid trigger on it. What doesn't
> exist is the thing that turns that image into an answer fast enough to matter, and
> that's the gap we're filling: image in, spill characterised, origin traced, ranked
> vessel list out, in under a second."

**Then land the killer follow-up — this is ours, from our own model:**

> "And we can actually price the delay. Our hindcast is what compensates for the lag
> between the spill and the image, and its uncertainty grows with that lag. This is run on
> real ocean current and wind for that location — same slick, same real forcing, only the
> image age changes:"

| Image age when we get it | Origin zone radius | Search area |
|---|---|---|
| 3 hours | 1.05 km | **3 km²** |
| 6 hours | 1.56 km | 8 km² |
| 24 hours | 3.07 km | 30 km² |
| 48 hours | 4.22 km | **56 km²** |

> "A three-hour image gives you a three-square-kilometre search box. A two-day-old
> archival image gives you fifty-six — sixteen times the area, and by then the
> vessel has left. That's the argument for tasking, and it's the argument for
> automating the analysis: there's no point cutting hours off image delivery if the
> analysis then sits in a queue for a day."

Reproduce it yourself before quoting: `drift_engine.hindcast(..., hours=N)` for the event
you are showing. The numbers move a little between events because each one has its own
real forcing.

**If pushed**
- **"Why SAR and not optical?"** SAR sees through cloud and at night — for a spill
  response you can't wait for a clear daytime pass. It's also why oil is detectable
  at all: it flattens capillary waves and drops the radar return, so a slick reads as
  a dark patch.
- **"What about revisit time?"** Archival revisit is measured in days. That's exactly
  why tasking matters, and why the table above is the honest framing.
- **"So you're just the last mile?"** Yes — and say it without flinching. The last
  mile is where this problem statement's value is. Detection-to-attribution is the
  part nobody has automated.

**Before you quote these as hard numbers:** sanity-check the NRSC turnaround figure
(~3–4 hours is the widely cited one for flood/cyclone products) and the Copernicus
REACT acronym. Wrong specifics in front of a judge cost more than omitting them —
"a few hours" is safe if you're unsure.

---

---

## Theme 4 — Prior art: *"this already exists, doesn't it?"*

**Yes, largely. Know this before you walk in.** Being unaware of CleanSeaNet in a
room that knows about CleanSeaNet is the fastest way to lose credibility. Naming
it yourself is the fastest way to gain some.

**Likely questions**
- Isn't EMSA already doing this?
- What's actually new here?
- Why would NTRO need this if the models already exist?

**Readiness: READY, but only if you lead with the prior art.**

### What exists

| System | Who | What it does |
|---|---|---|
| **CleanSeaNet** | EMSA, EU, operational since 2007 | Near-real-time SAR spill detection. Trained operators correlate detections with AIS from SafeSeaNet to identify the likely polluter. Its operator integrates **backward and forward drift** to estimate the source. Imagery has been used as evidence in court. |
| **Cerulean** | SkyTruth, global, public | Fully automated. A ResNet34 U-Net over every Sentinel-1 VV scene, then matches slicks against public AIS from −8 h to +6 h around the acquisition to name likely sources. Public near-real-time database. |
| **OOSA** | INCOIS, India, since 2015 | Online Oil Spill Advisory for the Indian Coast Guard. NOAA's **GNOME** trajectory model adapted for the Indian Ocean, coupled to ocean circulation and atmospheric models. Validated against Sentinel-1 observations. |
| **GNOME / ADIOS** | NOAA | The standard oil trajectory model. Forward and backward. |
| **OpenDrift / OpenOil** | Norwegian Met Institute | Open-source Lagrangian particle drift framework with an oil module and backtracking. |

So: SAR detection is decades old, particle backtracking to a source is standard
practice, and AIS correlation is operational in two separate systems today.

### Say this — and say it first

> "Most of this exists. EMSA's CleanSeaNet has been doing satellite spill detection
> with AIS correlation since 2007, SkyTruth's Cerulean does it automatically and
> publicly with a deep learning model, and NOAA's GNOME — which INCOIS already runs
> for the Indian Coast Guard — does the drift modelling. We didn't invent the
> pipeline. What we built is the part that is missing between them."

### What is actually ours — claim these, and nothing more

1. **An auditable attribution score, not an analyst judgement or a proximity match.**
   CleanSeaNet leaves the call to trained operators. Cerulean associates slicks with
   vessels that were nearby in a time window. Neither publishes a per-vessel weighted
   score with a stated reason per factor. Ours is eight weighted factors summing to
   1.00, with the plain-language reasons generated from the same numbers the score is
   built from — so the explanation cannot drift from the score. In a domain where the
   output ends up in court, "here is the number and here is why" is the useful shape.

2. **A calibrated refusal.** The system declines to attribute when the detection does
   not clear a measured bar, and we can state what that costs: blocks 60/60 tiles the
   dataset labels as containing no oil, at the price of 20% of genuine slicks. Cerulean
   uses human verification for this; we encoded it as a threshold with published
   performance.

3. **Pricing the imaging delay.** The origin uncertainty our hindcast reports grows
   with the age of the image — 3 km² at a 3-hour lag, 56 km² at 48 hours. That turns
   "should we task a satellite?" into a number. Theme 3 has the table.

4. **The gap in the Indian context, which is the actual pitch for PS 26143.**
   CleanSeaNet is EU-only. India already has the two ends — ISRO/NRSC do SAR
   detection, INCOIS runs GNOME for trajectory — but they are separate services and
   neither closes the loop to *attribution*. Nothing domestic takes an image and
   returns a ranked, evidenced list of suspect vessels. That is the hole we are in.

### What existing systems do better — concede these early

- **Detection accuracy.** Ours is classical CV at mean IoU 0.43. Cerulean's U-Net and
  the published deep learning models on these datasets do considerably better. We
  traded accuracy for a 10-hour build and something we can fully explain — and we
  measured the trade rather than hiding it.
- **Real AIS.** Theirs is real, ours is synthetic. The PS permits synthetic explicitly,
  and no open real AIS covers the Bay of Bengal.
- **Scale and acquisition.** They process every Sentinel-1 scene, continuously, at
  global scale. We process one tile on a laptop.

> "We're not claiming to beat CleanSeaNet. We're claiming that the attribution layer
> it keeps in the heads of trained operators can be made explicit, scored and
> auditable — and that India doesn't have that layer at all yet."

## Traps to avoid

1. **Don't say "agents," "AI-powered," or "the model decides."** We built none of
   those. Precision is the whole advantage here.
2. **Never imply this field is empty.** CleanSeaNet has been operational since 2007
   and Cerulean is public and automated. Name them before the judge does — see
   Theme 4.
3. **Don't claim it scales today.** It doesn't — it's one process with in-memory
   state. Knowing that is the better answer.
4. **Don't oversell the upload feature.** An uploaded tile has no geocoding, so we
   choose where to place it. The upload tests detection; the attribution that follows
   is against whichever event we dropped it into. Say so.
5. **Don't hide the synthetic AIS.** The problem statement explicitly permits it.
   Volunteering it reads as judgement; being caught reads as the opposite.
6. **Do show it refusing.** Upload `06_no_oil_lookalikes_only.png` — no oil in it, and
   the pipeline declines to trace or attribute. A system that knows when to stay quiet
   beats one that always has an answer.

---

## Related docs

`evaluator_brief.md` (what's built, numbers, deliberate cuts) ·
`SACD.md` §3 (API contract) · §4 (explicitly skipped) ·
`BL.md` (MoSCoW) · `next_steps.md` (what's still open)
