// api.js — thin fetch wrapper matching SACD.md §3's frozen contract.
// One function per endpoint, nothing fancier — no need for axios/a client
// library for five endpoints (see SACD.md §4's "explicitly skipped" list).

export const BASE_URL = "http://localhost:8000";

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
  // multipart — let the browser set Content-Type so it can add the boundary
  detectUpload: async (file) => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`${BASE_URL}/api/detect/upload`, { method: "POST", body });
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload.detail || `upload failed (${res.status})`);
    }
    return res.json();
  },
  drift: (spillId) =>
    request("/api/drift", { method: "POST", body: JSON.stringify({ spill_id: spillId }) }),
  attribution: (spillId) =>
    request("/api/attribution", { method: "POST", body: JSON.stringify({ spill_id: spillId }) }),
  vessel: (vesselId) => request(`/api/vessels/${vesselId}`),
  basemapLand: () => request("/api/basemap/land"),
  // /api/detect returns image_url as a path on the API, not a full URL —
  // absolutize it here so components never rebuild BASE_URL themselves.
  imageUrl: (path) => `${BASE_URL}${path}`,
};
