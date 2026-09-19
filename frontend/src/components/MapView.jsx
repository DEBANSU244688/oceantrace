import {
  MapContainer, TileLayer, GeoJSON, CircleMarker, Circle, Polyline,
  ImageOverlay, Pane, useMap,
} from "react-leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api";

// Dark basemap so the data (not the map chrome) carries the color.
const CARTO_BASEMAPS_API_KEY = import.meta.env.VITE_CARTO_BASEMAPS_API_KEY;
if (!CARTO_BASEMAPS_API_KEY) {
  console.warn("Missing VITE_CARTO_BASEMAPS_API_KEY. CARTO tiles will show an API key watermark.");
}
const TILE_QUERY = CARTO_BASEMAPS_API_KEY
  ? `?${new URLSearchParams({ key: CARTO_BASEMAPS_API_KEY }).toString()}`
  : "";
const TILE_URL = `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png${TILE_QUERY}`;
// Credits both sources, because both can be what's on screen: CARTO/OSM raster
// when there's internet, Natural Earth land polygons when there isn't. Natural
// Earth is public domain and doesn't require attribution — crediting it anyway
// is cheap, and claiming only CARTO while rendering something else is not right.
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a> · ' +
  'land <a href="https://www.naturalearthdata.com/">Natural Earth</a>';

// Leaflet's built-in panes: tilePane sits at z-index 200, overlayPane (all the
// vector layers below) at 400. The SAR tile goes in its own pane between them
// so it always covers the basemap and never covers the spill polygon.
const SAR_PANE = "sar-pane";
const SAR_PANE_Z = 250;

// The offline basemap. Leaflet's tilePane sits at z-index 200, so land drawn
// below that is covered by CARTO's opaque tiles whenever they load — and is
// what remains when they don't. No fallback logic, no blank map.
const LAND_PANE = "land-pane";
const LAND_PANE_Z = 150;

const HINDCAST_STEP_MS = 150;

function toLatLngs(feature) {
  const coords = feature?.geometry?.coordinates ?? [];
  return coords.map(([lon, lat]) => [lat, lon]);
}

// A real Sentinel-1 tile covers ~2.5 km while the hindcast origin sits ~10 km
// away, so a fixed zoom either buries the slick or crops the origin out. Fit to
// whatever layers currently exist instead, and re-fit as each step adds one.
function FitToData({ bounds, fallbackCenter }) {
  const map = useMap();
  const key = bounds ? bounds.toBBoxString() : null;
  useEffect(() => {
    // animate:false deliberately. Leaflet drops a fitBounds issued while a
    // previous zoom animation is still in flight, so clicking Detect then Trace
    // origin quickly enough left the map framed on the tile with the origin
    // zone off-screen. Snapping also reads better in a demo than gliding.
    if (bounds) map.fitBounds(bounds, { padding: [70, 70], maxZoom: 14, animate: false });
    else if (fallbackCenter) map.setView(fallbackCenter, 11);
    // `key` stands in for `bounds`, which is a fresh object on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

const TILE_FAILURES_BEFORE_OFFLINE = 4;

export default function MapView({ regionCenter, spill, drift, vesselDetail }) {
  const [sarOpacity, setSarOpacity] = useState(0.85);
  const [basemapOffline, setBasemapOffline] = useState(false);
  const [land, setLand] = useState(null);
  // tileerror is emitted by the TileLayer, not by the map — useMapEvents would
  // never see it, which is why this has to hang off the layer's eventHandlers.
  const tileFailures = useRef(0);

  useEffect(() => {
    api.basemapLand().then(setLand).catch(() => setLand(null));
  }, []);
  const [hindcastStep, setHindcastStep] = useState(0);

  // bbox from /api/detect -> Leaflet's [[south, west], [north, east]]
  const bbox = spill?.image_bbox;
  const sarBounds = bbox
    ? [
        [bbox.lat_bottom, bbox.lon_left],
        [bbox.lat_top, bbox.lon_right],
      ]
    : null;

  const hindcastPath = useMemo(
    () => toLatLngs(drift?.hindcast_path_geojson),
    [drift]
  );
  const hindcastDone = hindcastPath.length > 0 && hindcastStep >= hindcastPath.length;

  // Animate the backward drift, PRD.md §4 step 3. The particle cloud and the
  // origin zone only resolve once the run finishes, so the map tells the story
  // in the order it actually happens: slick -> drift backward -> origin.
  useEffect(() => {
    if (!hindcastPath.length) {
      setHindcastStep(0);
      return undefined;
    }
    setHindcastStep(1);
    const timer = setInterval(() => {
      setHindcastStep((s) => {
        if (s >= hindcastPath.length) {
          clearInterval(timer);
          return s;
        }
        return s + 1;
      });
    }, HINDCAST_STEP_MS);
    return () => clearInterval(timer);
  }, [hindcastPath]);

  const particles = useMemo(() => {
    const feats = drift?.origin_zone?.particle_cloud_geojson?.features ?? [];
    return feats.map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      return [lat, lon];
    });
  }, [drift]);

  const fitBounds = useMemo(() => {
    const b = L.latLngBounds([]);
    if (sarBounds) b.extend(sarBounds);
    if (drift) {
      // the origin circle's full extent, not just its centre
      const { center, radius_km } = drift.origin_zone;
      b.extend(L.latLng(center).toBounds(radius_km * 2000));
    }
    // Deliberately NOT extended to the vessel track: the framing should stay
    // put when a judge clicks through the ranked list, and a track that runs
    // off the edge reads as "it came from over there" rather than shrinking
    // the slick to a speck.
    return b.isValid() ? b : null;
  }, [sarBounds && JSON.stringify(sarBounds), drift]);

  return (
    <>
      <MapContainer center={regionCenter || [20.05, 86.95]} zoom={11} zoomControl={true}>
        {/* PRD.md §5 wants the demo to run with no internet, but these tiles
            come from CARTO. When they fail we say so, and the public-domain
            land layer below keeps the map readable regardless. */}
        <TileLayer
          url={TILE_URL}
          attribution={TILE_ATTRIBUTION}
          eventHandlers={{
            tileerror: () => {
              tileFailures.current += 1;
              if (tileFailures.current >= TILE_FAILURES_BEFORE_OFFLINE) {
                setBasemapOffline(true);
              }
            },
            tileload: () => {
              tileFailures.current = 0;
              setBasemapOffline(false);
            },
          }}
        />

        <Pane name={LAND_PANE} style={{ zIndex: LAND_PANE_Z }}>
          {land && (
            <GeoJSON
              key="land"
              data={land}
              style={{ color: "#2a313c", weight: 1, fillColor: "#171b22", fillOpacity: 1 }}
            />
          )}
        </Pane>
        <FitToData bounds={fitBounds} fallbackCenter={regionCenter} />

        {/* The actual SAR pixels the detection came from — PRD.md §4 step 2
            wants the polygon overlaid on the image, not floating on a basemap. */}
        <Pane name={SAR_PANE} style={{ zIndex: SAR_PANE_Z }}>
          {sarBounds && spill?.image_url && (
            <ImageOverlay
              key={`sar-${spill.image_id}`}
              url={api.imageUrl(spill.image_url)}
              bounds={sarBounds}
              opacity={sarOpacity}
            />
          )}
        </Pane>

        {spill && (
          <GeoJSON
            key={`spill-${spill.spill_id}`}
            data={spill.polygon_geojson}
            style={{ color: "#4fd6b0", weight: 2, fillColor: "#4fd6b0", fillOpacity: 0.25 }}
          />
        )}

        {drift && (
          <>
            {/* the backward run, drawn as it happens */}
            {hindcastStep > 1 && (
              <Polyline
                positions={hindcastPath.slice(0, hindcastStep)}
                pathOptions={{ color: "#e8b04b", weight: 2, dashArray: "3 4" }}
              />
            )}

            {/* 150 advected particles — the origin is a probability cloud, not
                a point, and showing the cloud is what makes that legible */}
            {hindcastDone &&
              particles.map((p, i) => (
                <CircleMarker
                  key={`particle-${i}`}
                  center={p}
                  radius={1.6}
                  pathOptions={{
                    color: "#e8b04b", weight: 0,
                    fillColor: "#e8b04b", fillOpacity: 0.55,
                  }}
                />
              ))}

            {hindcastDone && (
              <>
                <Circle
                  center={drift.origin_zone.center}
                  radius={drift.origin_zone.radius_km * 1000}
                  pathOptions={{
                    color: "#e8b04b", weight: 1.5,
                    fillColor: "#e8b04b", fillOpacity: 0.08,
                  }}
                />
                <CircleMarker
                  center={drift.origin_zone.center}
                  radius={5}
                  pathOptions={{ color: "#e8b04b", fillColor: "#e8b04b", fillOpacity: 1 }}
                />
              </>
            )}

            {drift.forecast_path_geojson && (
              <GeoJSON
                key="forecast-path"
                data={drift.forecast_path_geojson}
                style={{ color: "#99a2ae", weight: 2, dashArray: "4 5" }}
              />
            )}
          </>
        )}

        {vesselDetail && (
          <GeoJSON
            key={`vessel-${vesselDetail.vessel_id}`}
            data={vesselDetail.trajectory_geojson}
            style={{ color: "#f07167", weight: 2 }}
          />
        )}
      </MapContainer>

      {basemapOffline && (
        <div className="map-note">
          basemap offline — coastline and data layers unaffected
        </div>
      )}

      {/* Fading the tile out mid-demo is the cheapest way to show a judge the
          polygon really traces the slick in the image rather than being drawn
          from an answer key. */}
      {sarBounds && (
        <div className="sar-control">
          <label htmlFor="sar-opacity">SAR tile</label>
          <input
            id="sar-opacity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={sarOpacity}
            onChange={(e) => setSarOpacity(Number(e.target.value))}
          />
          <span className="sar-opacity-value">{Math.round(sarOpacity * 100)}%</span>
        </div>
      )}
    </>
  );
}
