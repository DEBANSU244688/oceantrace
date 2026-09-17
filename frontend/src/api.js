// api.js — thin fetch wrapper matching SACD.md §3's frozen contract.
// One function per endpoint, nothing fancier — no need for axios/a client
// library for five endpoints (see SACD.md §4's "explicitly skipped" list).

const BASE_URL = "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${path} failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  scenario: () => request("/api/scenario"),
  detect: (imageId) =>
    request("/api/detect", { method: "POST", body: JSON.stringify({ image_id: imageId }) }),
  drift: (spillId) =>
    request("/api/drift", { method: "POST", body: JSON.stringify({ spill_id: spillId }) }),
  attribution: (spillId) =>
    request("/api/attribution", { method: "POST", body: JSON.stringify({ spill_id: spillId }) }),
  vessel: (vesselId) => request(`/api/vessels/${vesselId}`),
};
