import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Route = { allocation_id: string; leg_id: string; vehicle_name: string; plate: string; origin: string; destination: string; position: number };
type Planned = { name: string; address: string | null; query: string; kind: string | null; position: number; scheduled_at: string | null };
type Comparison = { created_at: string; planned_points: Planned[]; positions: { latitude: number; longitude: number; captured_at: string; accuracy_m: number }[]; events: { recorded_at: string; action: string; passengers: number }[]; sample_limit: number };

function Details({ route }: { route: Route }) {
  const [loadMap, setLoadMap] = useState(false);
  const query = useQuery({ queryKey: ["route-comparison", route.allocation_id, route.leg_id], queryFn: () => api<Comparison>(`/tracking/routes/${route.allocation_id}/${route.leg_id}`), refetchInterval: loadMap ? false : 30000 });
  const config = useQuery({ queryKey: ["route-map-config"], queryFn: () => api<{ browser_key: string | null }>("/tracking/routes/map") });
  if (query.error || config.error) return <Alert>Não foi possível carregar a comparação.</Alert>;
  const data = query.data;
  if (!data) return <p role="status">Carregando percurso…</p>;
  return <div className="modal-form">
    <p>Roteiro preservado em {new Date(data.created_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}. {data.positions.length} amostras GPS disponíveis. Inclui os celulares responsáveis por este veículo e trecho.</p>
    <p><strong>Azul: sequência planejada. Verde: posições GPS recebidas.</strong> As linhas ligam pontos e não reproduzem as ruas percorridas. Não indicam infração nem classificam desvios.</p>
    {!config.data?.browser_key && <p>Para mostrar o mapa, a Nexus precisa configurar a chave web do Google Maps no Superadmin.</p>}
    {config.data?.browser_key && !loadMap && <><p>Carregar o mapa envia os endereços planejados e as posições exibidas ao Google. O mapa e a localização dos endereços podem consumir consultas do Google.</p><button className="button secondary" onClick={() => setLoadMap(true)}>Carregar comparação no Google Maps</button></>}
    {loadMap && <><iframe title="Mapa da rota planejada e do percurso GPS" src="/route-comparison-map.html" sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" style={{ width: "100%", height: 480, border: 0 }} onLoad={event => {
      // An opaque sandbox separates Maps' script policy from the authenticated app.
      event.currentTarget.contentWindow?.postMessage({ type: "rotafy-route", key: config.data?.browser_key, planned: data.planned_points, positions: data.positions }, "*");
    }} /><p>O mapa mostra as amostras carregadas. Atualize para buscar posições novas.</p><button className="button secondary" onClick={async () => { setLoadMap(false); await query.refetch(); }}>Atualizar comparação</button></>}
    {data.positions.length === 0 && <p>Nenhuma posição GPS recebida para este veículo e trecho.</p>}
    {data.positions.length >= data.sample_limit && <p>Limite de {data.sample_limit} amostras atingido. O percurso pode estar incompleto.</p>}
    <p>Horários apresentados em Brasília.</p><h3>Pontos planejados</h3><ol>{data.planned_points.map((p, i) => <li key={i}><strong>{p.name}</strong>{p.kind === "boarding" ? " · Embarque" : p.kind === "dropoff" ? " · Desembarque" : ""}<p>{p.address || "Sem endereço informado"}{p.scheduled_at ? ` · ${new Date(p.scheduled_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}` : " · Sem horário fixo"}</p></li>)}</ol>
    <h3>Registros de embarque e desembarque</h3>{data.events.length >= 500 && <p>Limite de quinhentos grupos de registros atingido; a lista pode estar incompleta.</p>}{data.events.length === 0 ? <p>Nenhum registro disponível.</p> : <ul>{data.events.map((e, i) => <li key={i}>{new Date(e.recorded_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })} · {e.action === "board" ? "Embarque" : e.action === "disembark" ? "Desembarque" : "Correção de registro"} · {e.passengers} passageiro(s)</li>)}</ul>}
  </div>;
}

export function RouteComparison({ trips }: { trips: { id: string; name: string }[] }) {
  const [trip, setTrip] = useState(""), [selected, setSelected] = useState("");
  const routes = useQuery({ queryKey: ["comparison-routes", trip], queryFn: () => api<Route[]>(`/tracking/routes?trip_id=${trip}`), enabled: !!trip });
  const route = routes.data?.find(r => `${r.allocation_id}/${r.leg_id}` === selected);
  return <section className="operation-card modal-form"><h2>Rota planejada × percurso realizado</h2>
    <Field label="Viagem para comparar"><select value={trip} onChange={e => { setTrip(e.target.value); setSelected(""); }}><option value="">Selecione a viagem</option>{trips.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
    {routes.error && <Alert>Não foi possível carregar os trechos.</Alert>}
    {trip && routes.data?.length === 0 && <p>Nenhum roteiro preservado. Vale para trechos iniciados após esta atualização; não há histórico retroativo.</p>}
    {!!routes.data?.length && <Field label="Veículo e trecho"><select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Selecione o trecho</option>{routes.data.map(r => <option key={`${r.allocation_id}/${r.leg_id}`} value={`${r.allocation_id}/${r.leg_id}`}>{r.vehicle_name} · {r.plate} · {r.position}: {r.origin} → {r.destination}</option>)}</select></Field>}
    {route && <Details key={selected} route={route} />}
  </section>;
}
