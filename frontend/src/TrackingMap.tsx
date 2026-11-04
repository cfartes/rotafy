import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type GeoPoint = { latitude: number; longitude: number };
export function TrackingMap({ points, onPick, markers, height = 360, preserveView = false, segments, ariaLabel }: { points: GeoPoint[]; onPick?: (point: GeoPoint) => void; markers?: (GeoPoint & { label: string; stale: boolean })[]; height?: number | string; preserveView?: boolean; segments?: GeoPoint[][]; ariaLabel?: string }) {
  const root = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null), layerRef = useRef<L.LayerGroup | null>(null), fitted = useRef(false);
  const canvasRef = useRef<L.Canvas | null>(null);
  const pick = useRef(onPick); pick.current = onPick;
  useEffect(() => {
    if (!root.current) return;
    const map = L.map(root.current).setView([-14.2, -51.9], 4);
    mapRef.current = map; layerRef.current = L.layerGroup().addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
      maxZoom: 19, referrerPolicy: "origin",
    }).addTo(map);
    map.on("click", e => pick.current?.({ latitude: e.latlng.lat, longitude: e.latlng.lng }));
    const container = root.current;
    const keyboardPick = (event: KeyboardEvent) => {
      if (event.key === "Enter" && pick.current && event.target === container) {
        event.preventDefault(); const center = map.getCenter();
        pick.current({ latitude: center.lat, longitude: center.lng });
      }
    };
    container.addEventListener("keydown", keyboardPick);
    const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(container);
    return () => { container.removeEventListener("keydown", keyboardPick); observer.disconnect(); map.remove(); mapRef.current = null; layerRef.current = null; fitted.current = false; canvasRef.current = null; };
  }, []);
  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const fit = !preserveView || !fitted.current;
    const coordinates = (segments ? segments.flat() : points).map(p => [p.latitude, p.longitude] as L.LatLngTuple);
    if (coordinates.length) {
      if (segments) {
        const renderer = canvasRef.current || (canvasRef.current = L.canvas());
        for (const segment of segments) {
          const line = segment.map(p => [p.latitude, p.longitude] as L.LatLngTuple);
          if (line.length > 1) L.polyline(line, { color: "#0c7a76", weight: 4, dashArray: "6 6", renderer }).addTo(layer);
          else if (line.length) L.circleMarker(line[0], { radius: 4, color: "#0c7a76", renderer }).addTo(layer);
        }
      } else {
        L.polyline(coordinates, { color: "#0c7a76", dashArray: "6 6" }).addTo(layer);
        coordinates.forEach((p, i) => L.circleMarker(p, { radius: i === coordinates.length - 1 ? 9 : 4, color: "#0c7a76" }).addTo(layer));
      }
      if (fit) {
        if (coordinates.length === 1) map.setView(coordinates[0], 16);
        else map.fitBounds(L.latLngBounds(coordinates), { padding: [24,24], maxZoom: 17 });
      }
      fitted.current = true;
    }
    if (markers?.length) {
      markers.forEach(p => {
        const label = document.createElement("span"); label.textContent = p.label;
        const marker = L.circleMarker([p.latitude, p.longitude], { radius: 9, color: p.stale ? "#a34b00" : "#0c7a76" }).bindTooltip(label, { permanent: false, direction: "top" }).addTo(layer);
        const element = marker.getElement();
        if (element) { element.setAttribute("tabindex", "0"); element.setAttribute("role", "img"); element.setAttribute("aria-label", p.label); element.addEventListener("focus", () => marker.openTooltip()); element.addEventListener("blur", () => marker.closeTooltip()); }
      });
      if (fit && !segments) map.fitBounds(L.latLngBounds(markers.map(p => [p.latitude, p.longitude] as L.LatLngTuple)), { padding: [40,40], maxZoom: 16 });
      fitted.current = true;
    }
  }, [points, markers, preserveView, segments]);
  return <div ref={root} role="region" style={{ height, width: "100%", zIndex: 0 }} aria-label={ariaLabel || (onPick ? "Mapa: use as setas para mover e Enter para selecionar o centro, ou clique para selecionar o embarque" : markers ? "Mapa de veículos em viagem" : "Mapa das posições coletadas")} />;
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
