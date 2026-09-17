import { MapContainer, TileLayer, GeoJSON, CircleMarker, Circle, useMap } from "react-leaflet";
import { useEffect } from "react";
import "leaflet/dist/leaflet.css";

// Dark basemap so the data (not the map chrome) carries the color.
const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

function Recenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

export default function MapView({ regionCenter, spill, drift, vesselDetail }) {
  const center = spill ? spill.centroid : regionCenter;

  return (
    <MapContainer center={center || [20.31, 86.61]} zoom={10} zoomControl={true}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      <Recenter center={center} />

      {spill && (
        <GeoJSON
          key="spill-polygon"
          data={spill.polygon_geojson}
          style={{ color: "#35d0b0", weight: 2, fillColor: "#35d0b0", fillOpacity: 0.25 }}
        />
      )}

      {drift && (
        <>
          <Circle
            key="origin-zone"
            center={drift.origin_zone.center}
            radius={drift.origin_zone.radius_km * 1000}
            pathOptions={{ color: "#f2a93b", weight: 1.5, fillColor: "#f2a93b", fillOpacity: 0.12 }}
          />
          <CircleMarker
            key="origin-point"
            center={drift.origin_zone.center}
            radius={5}
            pathOptions={{ color: "#f2a93b", fillColor: "#f2a93b", fillOpacity: 1 }}
          />
          {drift.forecast_path_geojson && (
            <GeoJSON
              key="forecast-path"
              data={drift.forecast_path_geojson}
              style={{ color: "#8b98ac", weight: 2, dashArray: "4 5" }}
            />
          )}
        </>
      )}

      {vesselDetail && (
        <GeoJSON
          key={`vessel-${vesselDetail.vessel_id}`}
          data={vesselDetail.trajectory_geojson}
          style={{ color: "#e8544e", weight: 2 }}
        />
      )}
    </MapContainer>
  );
}
