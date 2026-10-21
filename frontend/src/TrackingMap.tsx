import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type GeoPoint = { latitude: number; longitude: number };
export function TrackingMap({ points, onPick }: { points: GeoPoint[]; onPick?: (point: GeoPoint) => void }) {
  const root = useRef<HTMLDivElement>(null);
  const pick = useRef(onPick); pick.current = onPick;
  useEffect(() => {
    if (!root.current) return;
    const map = L.map(root.current).setView([-14.2, -51.9], 4);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19, referrerPolicy: "origin",
    }).addTo(map);
    const coordinates = points.map(p => [p.latitude, p.longitude] as L.LatLngTuple);
    if (coordinates.length) {
      L.polyline(coordinates, { color: "#0c7a76", dashArray: "6 6" }).addTo(map);
      coordinates.forEach((p, i) => L.circleMarker(p, { radius: i === coordinates.length - 1 ? 9 : 4, color: "#0c7a76" }).addTo(map));
      if (coordinates.length === 1) map.setView(coordinates[0], 16);
      else map.fitBounds(L.latLngBounds(coordinates), { padding: [24,24], maxZoom: 17 });
    }
    map.on("click", e => pick.current?.({ latitude: e.latlng.lat, longitude: e.latlng.lng }));
    const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(root.current);
    return () => { observer.disconnect(); map.remove(); };
  }, [points]);
  return <div ref={root} style={{ height: 360, width: "100%", zIndex: 0 }} aria-label={onPick ? "Mapa: clique para selecionar o embarque" : "Mapa das posições coletadas"} />;
}

export function mapsCoordinate(value: string): GeoPoint | null {
  const explicit = value.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
  let pair = explicit ? [explicit[1], explicit[2]] : null;
  if (!pair) {
    try { const url = new URL(value); pair = (url.searchParams.get("q") || url.searchParams.get("query") || url.searchParams.get("ll"))?.split(",") || null; } catch { pair = value.split(","); }
  }
  if (!pair || pair.length !== 2 || !pair.every(p => /^\s*-?\d+(\.\d+)?\s*$/.test(p))) return null;
  const [latitude, longitude] = pair.map(Number);
  return Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null;
}
