import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert } from "./components/ui";
import { PaginatedTable } from "./components/PaginatedTable";

type Journey = {
  allocation_id: string;
  leg_id: string;
  vehicle_id: string;
  vehicle_name: string;
  plate: string;
  position: number;
  origin: string;
  destination: string;
  distance_m: number | null;
  samples: number;
  valid_intervals: number;
  gaps: number;
  session_breaks: number;
  rejected_accuracy: number;
  rejected_jumps: number;
  invalid_timestamps: number;
  retention_limited: boolean;
  timing_unknown: boolean;
  partial: boolean;
  has_tracking: boolean;
};
type Mileage = {
  journeys: Journey[];
  distance_m: number | null;
  partial: boolean;
  trip_status: string;
  untracked_journeys: number;
  retention_days: number;
  gap_minutes: number;
  max_accuracy_m: number;
  max_speed_kmh: number;
};
const km = (meters: number | null) =>
  meters === null
    ? "Não calculável"
    : `${(meters / 1000).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km`;

export function TripMileage({
  trip,
  selected,
}: {
  trip: string;
  selected?: { allocation_id: string; leg_id: string };
}) {
  const query = useQuery({
    queryKey: ["trip-mileage", trip],
    retry: false,
    queryFn: () => api<Mileage>(`/tracking/history/${trip}/distance`),
  });
  const data = query.data;
  if (query.isPending)
    return <p role="status">Calculando a quilometragem registrada…</p>;
  if (query.error)
    return (
      <Alert>
        Não foi possível calcular a quilometragem.{" "}
        <button
          className="button secondary"
          onClick={() => void query.refetch()}
        >
          Tentar calcular novamente
        </button>
      </Alert>
    );
  if (!data) return null;
  const chosen = data.journeys.find(
    (j) =>
      j.allocation_id === selected?.allocation_id &&
      j.leg_id === selected?.leg_id,
  );
  const vehicles = new Map<
    string,
    {
      name: string;
      plate: string;
      distance: number;
      calculated: boolean;
      partial: boolean;
      legs: number;
    }
  >();
  for (const j of data.journeys) {
    const vehicle = vehicles.get(j.vehicle_id) || {
      name: j.vehicle_name,
      plate: j.plate,
      distance: 0,
      calculated: false,
      partial: false,
      legs: 0,
    };
    if (j.distance_m !== null) {
      vehicle.distance += j.distance_m;
      vehicle.calculated = true;
    }
    vehicle.partial ||= j.partial;
    vehicle.legs++;
    vehicles.set(j.vehicle_id, vehicle);
  }
  return (
    <section
      className="operation-card modal-form"
      aria-label="Quilometragem registrada"
    >
      <h2>Quilometragem estimada pelo GPS</h2>
      <dl className="history-summary">
        <div>
          <dt>Total registrado na viagem</dt>
          <dd>{km(data.distance_m)}</dd>
        </div>
        <div>
          <dt>Trecho selecionado</dt>
          <dd>{chosen ? km(chosen.distance_m) : "Selecione um trecho"}</dd>
        </div>
        <div>
          <dt>Coleta da viagem</dt>
          <dd>
            {data.distance_m === null
              ? "Dados insuficientes"
              : data.partial
                ? "Percurso parcial"
                : "Sem lacunas detectadas"}
          </dd>
        </div>
      </dl>
      <p>
        O total soma os quilômetros dos veículos nos trechos encerrados, sem
        ligar ida e volta ou celulares diferentes. Não corresponde à distância
        de um único ônibus quando há vários veículos.
      </p>
      <div className="table-scroll">
        <PaginatedTable aria-label="Quilometragem por veículo">
          <thead>
            <tr>
              <th>Veículo</th>
              <th>Trechos encerrados</th>
              <th>Km estimados</th>
              <th>Coleta</th>
            </tr>
          </thead>
          <tbody>
            {[...vehicles].map(([id, v]) => (
              <tr key={id}>
                <td>
                  {v.name} · {v.plate}
                </td>
                <td>{v.legs}</td>
                <td>{km(v.calculated ? v.distance : null)}</td>
                <td>
                  {!v.calculated
                    ? "Dados insuficientes"
                    : v.partial || data.trip_status !== "completed"
                      ? "Parcial"
                      : "Sem lacunas detectadas"}
                </td>
              </tr>
            ))}
          </tbody>
        </PaginatedTable>
      </div>
      {data.untracked_journeys > 0 && (
        <p>
          {data.untracked_journeys} trecho(s) encerrado(s) sem sessão de
          rastreamento. Não foram considerados como zero quilômetro.
        </p>
      )}
      {data.trip_status !== "completed" && data.trip_status !== "cancelled" && (
        <p>
          A viagem ainda não foi concluída. O total considera somente os trechos
          encerrados.
        </p>
      )}
      {data.trip_status === "cancelled" && (
        <p>
          A viagem foi cancelada. Os valores representam somente os registros
          disponíveis antes do encerramento.
        </p>
      )}
      {chosen && (
        <div>
          <h3>
            Qualidade do trecho {chosen.position}: {chosen.origin} →{" "}
            {chosen.destination}
          </h3>
          <p>
            {chosen.distance_m === null
              ? "Dados insuficientes para calcular: é necessário ao menos um intervalo válido entre duas posições."
              : chosen.partial
                ? "Percurso parcial: alguns intervalos não puderam ser considerados."
                : "Sem lacunas detectadas nos registros disponíveis."}
          </p>
          {(chosen.gaps > 0 ||
            chosen.session_breaks > 0 ||
            chosen.rejected_accuracy > 0 ||
            chosen.rejected_jumps > 0 ||
            chosen.invalid_timestamps > 0 ||
            chosen.retention_limited ||
            chosen.timing_unknown) && (
            <ul>
              {chosen.gaps > 0 && (
                <li>
                  {chosen.gaps} lacuna(s) de coleta acima de {data.gap_minutes}{" "}
                  minutos, incluindo início ou fim sem cobertura. As distâncias
                  ausentes não são interpoladas.
                </li>
              )}
              {chosen.session_breaks > 0 && (
                <li>
                  {chosen.session_breaks} troca(s) de sessão/celular; a
                  distância entre sessões não é somada.
                </li>
              )}
              {chosen.rejected_accuracy > 0 && (
                <li>
                  {chosen.rejected_accuracy} posição(ões) com precisão acima de{" "}
                  {data.max_accuracy_m} metros ignorada(s).
                </li>
              )}
              {chosen.rejected_jumps > 0 && (
                <li>
                  {chosen.rejected_jumps} salto(s) incompatível(is) com
                  deslocamento de até {data.max_speed_kmh} km/h ignorado(s).
                </li>
              )}
              {chosen.invalid_timestamps > 0 && (
                <li>
                  {chosen.invalid_timestamps} posição(ões) com horário
                  conflitante ignorada(s).
                </li>
              )}
              {chosen.retention_limited && (
                <li>
                  O início do rastreamento ultrapassa a retenção de{" "}
                  {data.retention_days} dias; posições antigas podem ter sido
                  removidas.
                </li>
              )}
              {chosen.timing_unknown && (
                <li>
                  Os limites de início ou fim da coleta não estão disponíveis
                  para conferir toda a cobertura.
                </li>
              )}
            </ul>
          )}
        </div>
      )}
      <p className="muted">
        Estimativa entre amostras, não substitui o hodômetro. A oscilação dentro
        da margem de precisão é desconsiderada. Curvas entre coletas podem
        reduzir o valor registrado. Mesmo sem lacunas detectadas, não há
        garantia de cobertura integral. O cálculo usa todas as posições retidas;
        o mapa exibe até dez mil amostras brutas.
      </p>
    </section>
  );
}
