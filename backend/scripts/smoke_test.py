"""
smoke_test.py — walk the whole pipeline and assert it still works.

Runs the same chain the demo does (detect -> drift -> attribution -> vessel
detail) against every registered sample image, plus the upload path, and
asserts the things that would actually embarrass us if they broke:

  * detection finds a slick in every sample tile
  * the hindcast recovers the scenario's known origin
  * the estimated spill window contains the scenario's known spill time
  * the guilty vessel ranks first, clearly ahead of the runner-up
  * every vessel comes back with at least one plain-language reason

Deliberately hits the running HTTP API rather than importing the modules —
that way it also covers the FastAPI wiring, the response schemas and CORS
config, which is where integration bugs actually live (PP.md Phase D).

Usage:
    uvicorn app.main:app --port 8000        # in another terminal
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url http://127.0.0.1:8000
"""
import argparse
import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, geo_utils  # noqa: E402

ORIGIN_TOLERANCE_KM = 3.0
MIN_GUILTY_SCORE = 0.7
MIN_SCORE_GAP = 0.2

failures = []
checks = 0


def check(label, ok, detail=""):
    global checks
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  — ' + detail if detail else ''}")
    if not ok:
        failures.append(f"{label}{'  — ' + detail if detail else ''}")


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.load(r)


def post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def post_file(base, path, filename, data, content_type="image/png"):
    boundary = uuid.uuid4().hex
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
               .encode())
    body.write(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.write(data)
    body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        base + path, data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def run_chain(base, spill):
    """drift -> attribution -> vessel detail for an already-detected spill."""
    drift = post(base, "/api/drift", {"spill_id": spill["spill_id"]})
    attribution = post(base, "/api/attribution", {"spill_id": spill["spill_id"]})
    top = attribution["ranked_vessels"][0]
    vessel = get(base, f"/api/vessels/{top['vessel_id']}?spill_id={spill['spill_id']}")
    return drift, attribution, top, vessel


def assert_scenario(label, spill, drift, attribution, top, vessel):
    """Check against the spill event this image is bound to — each tile is an
    observation of a different event, so the expected origin, window and
    culprit all change with the image."""
    sc = config.SCENARIOS_BY_ID[spill["scenario_id"]]

    origin = drift["origin_zone"]["center"]
    err_km = geo_utils.haversine_km(origin[0], origin[1],
                                    sc["origin_lat"], sc["origin_lon"])
    check(f"{label}: hindcast recovers {sc['id']} origin",
          err_km <= ORIGIN_TOLERANCE_KM,
          f"{err_km:.2f} km from ground truth (tolerance {ORIGIN_TOLERANCE_KM} km)")

    start = drift["spill_window"]["start"]
    end = drift["spill_window"]["end"]
    spill_time = sc["spill_time"].isoformat()
    check(f"{label}: spill window brackets {sc['id']} spill time",
          start <= spill_time <= end, f"{start} .. {end}")

    check(f"{label}: {sc['guilty']} ranks first",
          top["name"] == sc["guilty"],
          f"got {top['name']} at {top['score']}")
    check(f"{label}: guilty vessel scores above {MIN_GUILTY_SCORE}",
          top["score"] >= MIN_GUILTY_SCORE, f"score {top['score']}")

    runner_up = attribution["ranked_vessels"][1]["score"]
    check(f"{label}: clear gap to runner-up",
          top["score"] - runner_up >= MIN_SCORE_GAP,
          f"{top['score']} vs {runner_up}")

    funnel = attribution["funnel"]
    check(f"{label}: funnel narrows",
          funnel["total"] > funnel["spatial"] >= funnel["trajectory"] >= 1,
          f"{funnel['total']} -> {funnel['spatial']} -> {funnel['temporal']} "
          f"-> {funnel['trajectory']}")

    check(f"{label}: every vessel has a reason",
          all(v["reasons"] for v in attribution["ranked_vessels"]))
    check(f"{label}: vessel detail returns a track",
          len(vessel["trajectory_geojson"]["geometry"]["coordinates"]) >= 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    try:
        health = get(base, "/health")
    except (urllib.error.URLError, OSError) as e:
        print(f"Cannot reach {base} — is uvicorn running?  ({e})")
        return 2
    check("backend is up", health.get("status") == "ok")

    scenario = get(base, "/api/scenario")
    images = scenario["sample_images"]
    check("scenario lists sample images", len(images) >= 1, f"{len(images)} tiles")
    check("a real Sentinel-1 tile is registered",
          any(i["id"].startswith("s1_") for i in images))

    seen = {}
    for img in images:
        label = img["id"]
        spill = post(base, "/api/detect", {"image_id": img["id"]})
        check(f"{label}: detection returns a polygon",
              spill["area_km2"] > 0 and spill["polygon_geojson"]["type"] == "Polygon",
              f"{spill['area_km2']} km2, confidence {spill['confidence']}")
        check(f"{label}: detection is attributable",
              spill.get("attributable") is True,
              spill.get("attribution_block_reason") or "")
        check(f"{label}: look-alike context present (S4)",
              "lookalike_risk" in spill and bool(spill["lookalike_note"]),
              f"{spill['candidate_regions']} candidates, "
              f"risk {spill['lookalike_risk']}")

        drift, attribution, top, vessel = run_chain(base, spill)
        check(f"{label}: age estimate present (S2)",
              drift.get("age_estimate") is not None,
              f"{drift['age_estimate']['estimated_age_hours']}h at confidence "
              f"{drift['age_estimate']['confidence']}"
              if drift.get("age_estimate") else "missing")
        check(f"{label}: hindcast path present for animation",
              len((drift.get("hindcast_path_geojson") or {})
                  .get("geometry", {}).get("coordinates", [])) >= 2)
        assert_scenario(label, spill, drift, attribution, top, vessel)
        seen[label] = (spill["scenario_id"],
                        tuple(round(c, 3) for c in drift["origin_zone"]["center"]),
                        top["name"])

    # The whole point of binding tiles to different events: if every image
    # produced the same origin and the same culprit, the demo would be
    # indistinguishable from a hardcoded answer.
    origins = {v[1] for v in seen.values()}
    culprits = {v[2] for v in seen.values()}
    check("different images give different origins",
          len(origins) == len(seen), f"{len(origins)} distinct origins across {len(seen)} tiles")
    check("different images give different culprits",
          len(culprits) == len(seen), f"{sorted(culprits)}")

    # the upload path, using a sample tile as the payload
    tile = (Path(__file__).resolve().parent.parent / config.SAMPLE_IMAGES_DIR
            / "s1_371.png")
    if tile.exists():
        uploaded = post_file(base, "/api/detect/upload", tile.name, tile.read_bytes())
        check("upload: accepted and detected",
              uploaded["source"] == "upload" and uploaded["area_km2"] > 0,
              f"{uploaded['area_km2']} km2 as {uploaded['image_id']}")
        check("upload: names the event it was placed in",
              bool(uploaded.get("scenario_id")) and bool(uploaded.get("scenario_label")),
              f"{uploaded.get('scenario_id')} {uploaded.get('scenario_label')}")
        second = post_file(base, "/api/detect/upload", tile.name, tile.read_bytes())
        check("upload: consecutive uploads rotate events",
              second["scenario_id"] != uploaded["scenario_id"],
              f"{uploaded['scenario_id']} then {second['scenario_id']}")
        served = urllib.request.urlopen(base + uploaded["image_url"], timeout=30)
        check("upload: image is served back for the map overlay",
              served.status == 200 and served.headers["content-type"].startswith("image/"))
        u_drift, u_attr, u_top, u_vessel = run_chain(base, uploaded)
        assert_scenario("upload", uploaded, u_drift, u_attr, u_top, u_vessel)

    # The attribution gate: a tile the dataset labels as containing no oil must
    # not reach attribution, because naming a vessel for a spill that never
    # happened is the worst failure this system has available to it.
    for name in ("06_no_oil_lookalikes_only.png", "07_no_oil_faint.png"):
        blank = (Path(__file__).resolve().parent.parent / "data" / "demo_uploads" / name)
        if not blank.exists():
            continue
        try:
            spill = post_file(base, "/api/detect/upload", blank.name, blank.read_bytes())
        except urllib.error.HTTPError as e:
            check(f"gate: {name} refused at detection", e.code == 422, f"HTTP {e.code}")
            continue
        check(f"gate: {name} marked not attributable",
              spill.get("attributable") is False,
              f"confidence {spill['confidence']}, risk {spill['lookalike_risk']}")
        check(f"gate: {name} has an explanation",
              bool(spill.get("attribution_block_reason")))
        for endpoint in ("/api/drift", "/api/attribution"):
            try:
                post(base, endpoint, {"spill_id": spill["spill_id"]})
                check(f"gate: {name} refused by {endpoint}", False, "it was allowed")
            except urllib.error.HTTPError as e:
                check(f"gate: {name} refused by {endpoint}", e.code == 409, f"HTTP {e.code}")

    # a non-image upload must be refused, not guessed at
    try:
        post_file(base, "/api/detect/upload", "notes.txt", b"this is not an image",
                  content_type="text/plain")
        check("upload: junk file is rejected", False, "it was accepted")
    except urllib.error.HTTPError as e:
        check("upload: junk file is rejected", e.code in (415, 422), f"HTTP {e.code}")

    print(f"\n{checks - len(failures)}/{checks} checks passed")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("pipeline is healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
