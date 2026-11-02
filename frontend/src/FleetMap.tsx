import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { TrackingMap } from "./TrackingMap";

type Vehicle = { id: string; vehicle_name: string; plate: string; trip_name: string; origin: string; destination: string; latitude: number | null; longitude: number | null; accuracy_m: number | null; captured_at: string | null };
const time = (value: string | number) => new Date(value).toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo" });

export function FleetMap() {
  const query = useQuery({ queryKey: ["tracking", "vehicles"], queryFn: () => api<Vehicle[]>("/tracking/vehicles"), refetchInterval: 15000 });
  const root = useRef<HTMLElement>(null);
  const [center, setCenter] = useState(0), [fullscreen, setFullscreen] = useState(false), [error, setError] = useState("");
  useEffect(() => {
    const change = () => setFullscreen(document.fullscreenElement === root.current);
    document.addEventListener("fullscreenchange", change);
    return () => document.removeEventListener("fullscreenchange", change);
  }, []);
  const vehicles = query.data || [], located = vehicles.filter(v => v.latitude != null && v.longitude != null);
  const markers = located.map(v => {
    const stale = !v.captured_at || Date.now() - Date.parse(v.captured_at) > 120000;
    return { latitude: v.latitude!, longitude: v.longitude!, stale, label: `${v.vehicle_name} · ${v.plate} · ${v.trip_name} · ${v.origin} → ${v.destination} · ${v.captured_at ? `GPS às ${time(v.captured_at)} (Brasília)` : "Sem horário GPS"} · Precisão ${Math.round(v.accuracy_m || 0)} m${stale ? " · Posição desatualizada" : ""}` };
  });
  return <section className="fleet-map" ref={root} aria-label="Acompanhamento da frota">
    <div className="fleet-map-canvas"><TrackingMap key={center} points={[]} markers={markers} height="100%" preserveView /></div>
    <div className="fleet-map-panel">
      <h1>Mapa da frota</h1>
      <p>{located.length} veículo(s) no mapa{vehicles.length > located.length ? ` · ${vehicles.length - located.length} aguardando GPS` : ""}</p>
      <p className="muted">Consulta a cada 15 s · GPS previsto a cada 1 min</p>
      {query.dataUpdatedAt > 0 && <small>Última consulta: {time(query.dataUpdatedAt)} · Brasília</small>}
      <p className="fleet-map-legend"><span>● Posição recente</span><span>● Mais de 2 min</span></p>
      {query.isPending && <p role="status">Consultando veículos…</p>}
      {!query.isPending && !query.isError && located.length === 0 && <p>Nenhuma posição disponível. Inicie o rastreamento no APK para mostrar o veículo.</p>}
      {query.isError && <p role="alert">Não foi possível atualizar. As últimas posições recebidas podem estar desatualizadas.</p>}
      {error && <p role="alert">{error}</p>}
      <div className="fleet-map-actions">
        <button className="button secondary" onClick={() => setCenter(v => v + 1)} disabled={!located.length}>Centralizar</button>
        <button className="button secondary" onClick={() => query.refetch()} disabled={query.isFetching}>Atualizar agora</button>
        {document.fullscreenEnabled && <button className="button secondary" onClick={async () => {
          setError("");
          try { if (document.fullscreenElement === root.current) await document.exitFullscreen(); else await root.current?.requestFullscreen(); }
          catch { setError("O navegador não permitiu expandir o mapa. A visualização continua disponível."); }
        }}>{fullscreen ? "Sair da tela cheia" : "Tela cheia"}</button>}
      </div>
      <a className="fleet-map-privacy" href="/privacidade" target="_blank" rel="noopener noreferrer">Privacidade</a>
    </div>
  </section>;
}
