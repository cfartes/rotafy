import { DataUseNotice } from "./components/DataUseNotice";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { TrackingMap, mapsCoordinate, type GeoPoint } from "./TrackingMap";

type Settings = { enabled: boolean; proximity_enabled: boolean; departure_enabled: boolean; radius_m: number };
type Vehicle = { id: string; trip_name: string; trip_id: string; vehicle_name: string; plate: string; responsible: string; origin: string; destination: string; captured_at: string | null; accuracy_m: number | null };
type Boarding = { reservation_id: string; leg_id: string; contact_name: string; boarding_name: string; boarding_address: string; coordinates_valid: boolean; latitude: number | null; longitude: number | null; source_hash: string; starts_at: string };

function ConfirmBoarding({ point, onClose }: { point: Boarding; onClose: () => void }) {
  const cache = useQueryClient();
  const [coordinate, setCoordinate] = useState<GeoPoint | null>(point.coordinates_valid && point.latitude !== null && point.longitude !== null ? { latitude: point.latitude, longitude: point.longitude } : null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  return <Modal title="Confirmar ponto de embarque" onClose={onClose} wide><div className="modal-form">
    <p><strong>{point.boarding_name}</strong> · {point.boarding_address} · Reserva de {point.contact_name}</p>
    <a className="button secondary" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(point.boarding_address || point.boarding_name)}`} target="_blank" rel="noopener noreferrer">Localizar no Google Maps</a>
    <Field label="Link do Google Maps com coordenadas ou latitude, longitude"><input placeholder="Cole um link completo ou -26.90, -49.06" onChange={e => { const p = mapsCoordinate(e.target.value); if (p) { setCoordinate(p); setError(""); } else setError("Esse link não contém coordenadas explícitas. Clique no mapa para selecionar o local; links curtos não são expandidos."); }} /></Field>
    <p>Clique no mapa para ajustar e confira o ponto antes de confirmar.</p>
    <TrackingMap points={coordinate ? [coordinate] : []} onPick={setCoordinate} />
    {coordinate && <p>Ponto selecionado: {coordinate.latitude.toFixed(6)}, {coordinate.longitude.toFixed(6)}</p>}
    {error && <Alert>{error}</Alert>}
    <button className="button primary" disabled={!coordinate || busy} onClick={async () => {
      setBusy(true); setError("");
      try { await api(`/tracking/boardings/${point.reservation_id}/${point.leg_id}`, { method: "PUT", body: JSON.stringify({ ...coordinate, source_hash: point.source_hash }) }); await cache.invalidateQueries({ queryKey: ["tracking-boardings"] }); onClose(); }
      catch (e) { setError(e instanceof Error ? e.message : "Não foi possível confirmar."); } finally { setBusy(false); }
    }}>Confirmar este ponto de embarque</button>
  </div></Modal>;
}

function Preferences({ settings }: { settings: Settings }) {
  const cache = useQueryClient();
  const [value, setValue] = useState<Settings>(() => ({ enabled: settings.enabled, proximity_enabled: settings.proximity_enabled, departure_enabled: settings.departure_enabled, radius_m: settings.radius_m })), [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice,setNotice] = useState("");
  async function save(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); setNotice(""); try { await api("/tracking/settings", { method: "PUT", body: JSON.stringify(value) }); await cache.invalidateQueries({ queryKey: ["tracking"] }); setNotice("Configuração salva."); } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível salvar."); } finally { setBusy(false); } }
  return <form className="operation-card modal-form" onSubmit={save}>
<DataUseNotice purpose="configurar e acompanhar a localização operacional do veículo durante a viagem" /><h2>Rastreamento e avisos</h2>
    <label><input type="checkbox" checked={value.enabled} onChange={e=>setValue({...value,enabled:e.target.checked})}/>Permitir rastreamento dos veículos durante as viagens</label>
    <label><input type="checkbox" checked={value.proximity_enabled} onChange={e=>setValue({...value,proximity_enabled:e.target.checked})}/>Avisar proximidade por WhatsApp, quando o rastreamento estiver ativo</label>
    <Field label="Raio de proximidade (km)"><input type="number" min="0.5" max="20" step="0.5" required value={value.radius_m/1000} onChange={e=>setValue({...value,radius_m:Math.round(Number(e.target.value)*1000)})}/></Field>
    <label><input type="checkbox" checked={value.departure_enabled} onChange={e=>setValue({...value,departure_enabled:e.target.checked})}/>Lembrar a saída de cada trecho com 15 minutos de antecedência, incluindo a volta</label>
    <p>O lembrete de saída funciona pelo horário, mesmo sem rastreamento. Os avisos usam o WhatsApp da empresa e o telefone de cada reserva. Desativar o rastreamento encerra as sessões no servidor; o aparelho interrompe a coleta ao receber essa informação.</p>
    {error && <Alert>{error}</Alert>}{notice && <p role="status">{notice}</p>}<button className="button primary" disabled={busy}>Salvar configurações</button>
  </form>;
}

export function Tracking() {
  const settings = useQuery({ queryKey: ["tracking","settings"], queryFn:()=>api<Settings>("/tracking/settings") });
  const vehicles = useQuery({ queryKey: ["tracking","vehicles"], queryFn:()=>api<Vehicle[]>("/tracking/vehicles"), refetchInterval:30000 });
  const trips = useQuery({ queryKey:["tracking","trips"], queryFn:()=>api<{id:string;name:string;status:string}[]>("/trips") });
  const [session,setSession] = useState(""), [trip,setTrip] = useState(""), [editing,setEditing] = useState<Boarding|null>(null);
  const history = useQuery({ queryKey:["tracking","history",session],queryFn:()=>api<(GeoPoint & {captured_at:string})[]>(`/tracking/sessions/${session}/history`), enabled:!!session,refetchInterval:30000 });
  const boardings = useQuery({queryKey:["tracking-boardings",trip],queryFn:()=>api<Boarding[]>(`/tracking/boardings?trip_id=${trip}`),enabled:!!trip});
  return <div className="modal-form">
    {(settings.error || vehicles.error || history.error || boardings.error) && <Alert>Não foi possível atualizar o rastreamento. Confira sua conexão.</Alert>}
    {settings.data && <Preferences settings={settings.data}/>}
    <section className="operation-card"><h2>Veículos em viagem</h2><p>Coleta prevista a cada cinco minutos. A linha liga amostras de GPS e não representa todo o percurso pelas ruas.</p>
      {vehicles.data?.length===0 && <p>Nenhum veículo está compartilhando localização neste momento.</p>}
      {vehicles.data?.map(v=><article className="operation-card" key={v.id}><strong>{v.vehicle_name} · {v.plate}</strong><p>{v.trip_name} · {v.origin} → {v.destination}</p><p>Responsável: {v.responsible}</p><p>{v.captured_at ? `Última posição: ${new Date(v.captured_at).toLocaleString("pt-BR")} · Precisão: ${Math.round(v.accuracy_m||0)} m${Date.now()-Date.parse(v.captured_at)>6*60000 ? " · Localização desatualizada" : ""}` : "Aguardando a primeira posição"}</p><button className="button secondary" onClick={()=>{setSession(v.id);setTrip(v.trip_id);}}>Acompanhar no mapa</button></article>)}
      {session && <TrackingMap points={history.data||[]}/>}
    </section>
    <section className="operation-card"><h2>Locais de embarque para avisos</h2><Field label="Viagem"><select value={trip} onChange={e=>setTrip(e.target.value)}><option value="">Selecione a viagem</option>{trips.data?.filter(t=>["scheduled","in_progress"].includes(t.status)).map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
      <p>Confirme o local no mapa para habilitar o aviso de proximidade. Se o endereço mudar, confirme novamente.</p>
      {boardings.data?.map(p=><article className="operation-card" key={`${p.reservation_id}:${p.leg_id}`}><strong>{p.contact_name}</strong><p>{p.boarding_name} · {p.boarding_address}</p><p>Saída do trecho: {new Date(p.starts_at).toLocaleString("pt-BR")} · {p.coordinates_valid ? "Ponto confirmado" : "Sem coordenadas confirmadas"}</p><button className="button secondary" onClick={()=>setEditing(p)}>{p.coordinates_valid ? "Ajustar ponto no mapa" : "Confirmar ponto no mapa"}</button></article>)}
    </section>{editing && <ConfirmBoarding point={editing} onClose={()=>setEditing(null)}/>}
  </div>;
}
