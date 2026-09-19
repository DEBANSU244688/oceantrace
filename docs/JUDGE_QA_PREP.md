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
Open that tab if challenged.

**Say this — the workflow, out loud:**

> "It's a four-stage pipeline, and each stage is a REST call the frontend makes in
> order. Detection takes an image ID and returns a slick polygon with area,
> perimeter, centroid and confidence. That centroid feeds the drift engine, which
> advects 150 particles backward through a current-and-wind field to get an origin
> probability cloud and a spill time window. That origin and window feed the
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
> between the spill and the image, and its uncertainty grows with that lag. Same
> slick, same drift model, only the image age changes:"

| Image age when we get it | Origin zone radius | Search area |
|---|---|---|
| 3 hours | 1.0 km | **3 km²** |
| 6 hours | 1.7 km | 9 km² |
| 24 hours | 3.1 km | 29 km² |
| 48 hours | 4.1 km | **53 km²** |

> "A three-hour image gives you a three-square-kilometre search box. A two-day-old
> archival image gives you fifty-three — eighteen times the area, and by then the
> vessel has left. That's the argument for tasking, and it's the argument for
> automating the analysis: there's no point cutting hours off image delivery if the
> analysis then sits in a queue for a day."

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

## Traps to avoid

1. **Don't say "agents," "AI-powered," or "the model decides."** We built none of
   those. Precision is the whole advantage here.
2. **Don't claim it scales today.** It doesn't — it's one process with in-memory
   state. Knowing that is the better answer.
3. **Don't oversell the upload feature.** An uploaded tile has no geocoding, so we
   choose where to place it. The upload tests detection; the attribution that follows
   is against whichever event we dropped it into. Say so.
4. **Don't hide the synthetic AIS.** The problem statement explicitly permits it.
   Volunteering it reads as judgement; being caught reads as the opposite.
5. **Do show it refusing.** Upload `06_no_oil_lookalikes_only.png` — no oil in it, and
   the pipeline declines to trace or attribute. A system that knows when to stay quiet
   beats one that always has an answer.

---

## Related docs

`evaluator_brief.md` (what's built, numbers, deliberate cuts) ·
`SACD.md` §3 (API contract) · §4 (explicitly skipped) ·
`BL.md` (MoSCoW) · `next_steps.md` (what's still open)
