import { useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";
import { TrackingMap, type GeoPoint } from "./TrackingMap";

type Trip = { id: string; name: string; status: string; starts_at: string; first_session_at: string; last_position_at: string | null };
type Journey = { allocation_id: string; leg_id: string; vehicle_name: string; plate: string; origin: string; destination: string; position: number; trip_name: string; trip_status: string; session_count: number; position_count: number; tracking_started_at: string; tracking_ended_at: string | null };
type Position = GeoPoint & { id: string; session_id: string; captured_at: string; received_at: string; accuracy_m: number };
type Recorded = Journey & { positions: Position[]; truncated: boolean; sample_limit: number; gap_minutes: number; retention_days: number };
const date = (value: string) => new Date(value).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
const day = (value: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(value);

function RecordedRoute({ trip, journey }: { trip: string; journey: Journey }) {
  const query = useQuery({ queryKey: ["recorded-route", trip, journey.allocation_id, journey.leg_id], queryFn: () => api<Recorded>(`/tracking/history/${trip}/${journey.allocation_id}/${journey.leg_id}`) });
  const [center, setCenter] = useState(0);
  const data = query.data;
  const segments = useMemo(() => {
    const result: Position[][] = [];
    for (const point of data?.positions || []) {
      const last = result.at(-1)?.at(-1);
      if (!last || point.session_id !== last.session_id || Date.parse(point.captured_at) - Date.parse(last.captured_at) > (data?.gap_minutes || 10) * 60000) result.push([]);
      result.at(-1)!.push(point);
    }
    return result;
  }, [data]);
  if (query.isPending) return <p role="status">Carregando o trajeto registrado…</p>;
  if (query.error) return <Alert>Não foi possível carregar o trajeto. <button className="button secondary" onClick={() => void query.refetch()}>Tentar carregar novamente</button></Alert>;
  if (!data) return null;
  const points = data.positions, first = points[0], last = points.at(-1);
  const markers = first ? [first, ...(last && last !== first ? [last] : [])].map((p, i) => ({ ...p, stale: false, label: `${i === 0 ? "Primeira posição" : "Última posição"} · ${date(p.captured_at)} · Precisão ${Math.round(p.accuracy_m)} m` })) : [];
  return <section className="operation-card modal-form" aria-label="Percurso selecionado">
    <div><h2>{journey.vehicle_name} · {journey.plate}</h2><p>Trecho {journey.position}: {journey.origin} → {journey.destination}</p></div>
    <dl className="history-summary"><div><dt>Amostras exibidas</dt><dd>{points.length.toLocaleString("pt-BR")}</dd></div><div><dt>Primeiro GPS</dt><dd>{first ? date(first.captured_at) : "Não recebido"}</dd></div><div><dt>Último GPS exibido</dt><dd>{last ? date(last.captured_at) : "Não recebido"}</dd></div></dl>
    <p>Horários de Brasília. {data.session_count} sessão(ões) de rastreamento reunida(s), incluindo trocas do celular responsável.</p>
    {points.length ? <><p>A linha verde liga amostras GPS e representa um percurso aproximado. Não reconstrói as ruas percorridas. Trocas de celular e intervalos superiores a {data.gap_minutes} minutos interrompem a linha.</p><div className="history-map"><TrackingMap key={center} points={[]} segments={segments} markers={markers} height="100%" ariaLabel="Mapa do percurso registrado" /></div><div className="history-map-actions"><button className="button secondary" onClick={() => setCenter(value => value + 1)}>Centralizar percurso</button><span>{segments.length} segmento(s) de coleta</span></div></> : <p role="status">Nenhuma posição GPS disponível para este trecho. A coleta pode não ter ocorrido ou os dados podem ter ultrapassado a retenção de {data.retention_days} dias.</p>}
    {points.length === 1 && <p>Há somente uma posição salva. Ela não permite desenhar um percurso.</p>}
    {points.some(p => p.accuracy_m > 100) && <p>Há posições com precisão superior a 100 metros; considere essa margem ao analisar o percurso.</p>}
    {data.truncated && <Alert>Exibindo as primeiras {data.sample_limit.toLocaleString("pt-BR")} amostras. O percurso está parcial.</Alert>}
  </section>;
}

export function RouteHistory() {
  const [period, setPeriod] = useState(() => ({ start: day(new Date(Date.now() - 29 * 86400000)), end: day(new Date()) }));
  const [trip, setTrip] = useState(""), [selected, setSelected] = useState("");
  const trips = useQuery({ queryKey: ["recorded-trips", period.start, period.end], queryFn: () => api<{ trips: Trip[]; truncated: boolean; limit: number; retention_days: number }>(`/tracking/history?start_date=${period.start}&end_date=${period.end}`) });
  const journeys = useQuery({ queryKey: ["recorded-journeys", trip], queryFn: () => api<Journey[]>(`/tracking/history/${trip}`), enabled: !!trip });
  const journey = journeys.data?.find(j => `${j.allocation_id}/${j.leg_id}` === selected) || (journeys.data?.length === 1 ? journeys.data[0] : undefined);
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setTrip(""); setSelected("");
    const next = { start: String(form.get("start")), end: String(form.get("end")) };
    if (next.start === period.start && next.end === period.end) void trips.refetch();
    else setPeriod(next);
  }
  return <div className="modal-form route-history">
    <section className="operation-card modal-form"><h2>Consultar viagem executada</h2><p>Consulte viagens ou trechos encerrados com rastreamento registrado. As posições GPS ficam disponíveis por até 90 dias. Não é necessário ter preservado o roteiro planejado.</p>
      <form className="history-filters" onSubmit={search}><Field label="Início do período"><input type="date" name="start" defaultValue={period.start} required /></Field><Field label="Fim do período"><input type="date" name="end" defaultValue={period.end} required /></Field><button className="button secondary" disabled={trips.isFetching}>Buscar viagens</button></form>
      <p>O período localiza viagens pela coleta. O mapa mostra todo o trecho ainda disponível, inclusive se passar da meia-noite.</p>
      {trips.isPending && <p role="status">Consultando viagens…</p>}
      {trips.error && <Alert>{trips.error.message}</Alert>}
      {trips.data?.truncated && <Alert>Mais de {trips.data.limit} viagens encontradas. Reduza o período para localizar as demais.</Alert>}
      {trips.data && !trips.data.trips.length && <p>Nenhuma viagem ou trecho encerrado com rastreamento registrado neste período.</p>}
      <div className="history-pickers">{!!trips.data?.trips.length && <Field label="Viagem executada"><select value={trip} onChange={e => { setTrip(e.target.value); setSelected(""); }}><option value="">Selecione a viagem</option>{trips.data.trips.map(t => <option key={t.id} value={t.id}>{t.name} · {date(t.last_position_at || t.first_session_at)}{t.status === "cancelled" ? " · Cancelada" : t.status === "in_progress" ? " · Trecho encerrado" : ""}</option>)}</select></Field>}
      {journeys.isFetching && trip && <p role="status">Consultando veículos e trechos…</p>}
      {journeys.error && <Alert>Não foi possível consultar os veículos e trechos.</Alert>}
      {!!journeys.data?.length && <Field label="Veículo e trecho registrado"><select value={journey ? `${journey.allocation_id}/${journey.leg_id}` : selected} onChange={e => setSelected(e.target.value)}><option value="">Selecione o veículo e trecho</option>{journeys.data.map(j => <option key={`${j.allocation_id}/${j.leg_id}`} value={`${j.allocation_id}/${j.leg_id}`}>{j.vehicle_name} · {j.plate} · Trecho {j.position}: {j.origin} → {j.destination}{j.position_count ? "" : " · Sem GPS disponível"}</option>)}</select></Field>}</div>
    </section>
    {trip && journey && <RecordedRoute key={`${trip}/${journey.allocation_id}/${journey.leg_id}`} trip={trip} journey={journey} />}
  </div>;
}
