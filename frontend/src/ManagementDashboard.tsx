import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type User } from "./api";
import { Alert, Field } from "./components/ui";
import { localToday, money } from "./billing/types";

type Daily = { day: string; displacements: number; commercial_trips: number };
type Vehicle = {
  vehicle_id: string;
  name: string;
  plate: string;
  displacements: number;
  occupancy_pct: number;
  confirmed_peak_sum: number;
  capacity_sum: number;
  held_peak_sum: number;
};
type Management = {
  generated_at: string;
  summary: {
    commercial_trips: number;
    displacements: number;
    occupancy_pct: number | null;
    confirmed_families: number;
    confirmed_passengers: number;
    confirmed_value_cents: number;
    paid_value_cents: number;
    unpaid_value_cents: number;
    average_ticket_cents: number | null;
  };
  daily: Daily[];
  vehicles: Vehicle[];
  trip_statuses: { status: string; count: number }[];
  reservation_statuses: { status: string; count: number }[];
  ranking: {
    product_key: string;
    name: string;
    passengers: number;
    value_cents: number;
  }[];
  upcoming: {
    allocation_id: string;
    leg_id: string;
    trip_id: string;
    trip_name: string;
    leg_position: number;
    starts_at: string;
    vehicle_name: string;
    plate: string;
    destination: string;
    occupancy_pct: number;
    available: number;
  }[];
};
const labels: Record<string, string> = {
  scheduled: "Agendadas",
  in_progress: "Em andamento",
  completed: "Concluídas",
  cancelled: "Canceladas",
  confirmed: "Confirmadas",
  pending: "Pendentes válidas",
  expired: "Expiradas",
};
const number = (value: number) => value.toLocaleString("pt-BR");
const percent = (value: number | null) =>
  value === null
    ? "Sem dados"
    : `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const dayLabel = (day: string) => day.split("-").reverse().join("/");
const monthEnd = (day: string) => {
  const [year, month] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
};
const date = (value: string) =>
  new Date(value).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "short",
  });

function DailyChart({ data }: { data: Daily[] }) {
  const [selected, select] = useState<Daily | null>(null);
  const width = Math.max(650, data.length * 24 + 50),
    height = 240;
  const max = Math.max(
    1,
    ...data.flatMap((d) => [d.displacements, d.commercial_trips]),
  );
  const unit = (width - 65) / Math.max(1, data.length);
  return (
    <section className="manager-panel manager-wide">
      <h2>Movimento por dia</h2>
      <p className="muted">
        Cada deslocamento inclui ida, retorno ou etapa do pacote. Viagens
        comerciais contam apenas sua primeira saída. Inclui canceladas; use o
        filtro de situação.
      </p>
      <div className="manager-legend">
        <span>
          <i className="manager-teal" />
          Deslocamentos
        </span>
        <span>
          <i className="manager-blue" />
          Viagens comerciais iniciadas
        </span>
      </div>
      <div
        className="manager-chart-scroll"
        tabIndex={0}
        role="region"
        aria-label="Gráfico diário com rolagem horizontal"
      >
        <svg
          width={width}
          height={height}
          role="group"
          aria-label="Deslocamentos e viagens comerciais por dia"
        >
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line
                x1={40}
                x2={width - 15}
                y1={195 - f * 165}
                y2={195 - f * 165}
                stroke="#dce6ec"
              />
              <text
                x={30}
                y={200 - f * 165}
                textAnchor="end"
                fontSize={12}
                fill="#476276"
              >
                {Number((max * f).toFixed(1))}
              </text>
            </g>
          ))}
          {data.map((d, index) => {
            const x = 45 + index * unit,
              bar = Math.min(12, unit / 3);
            const description = `${dayLabel(d.day)}: ${d.displacements} deslocamentos, ${d.commercial_trips} viagens comerciais`;
            return (
              <g
                key={d.day}
                role="button"
                tabIndex={0}
                aria-label={description}
                onClick={() => select(d)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    select(d);
                  }
                }}
              >
                <title>{description}</title>
                <rect
                  x={x}
                  y={15}
                  width={unit - 1}
                  height={185}
                  fill={selected?.day === d.day ? "#e8f4f3" : "transparent"}
                />
                <rect
                  x={x + 2}
                  y={195 - (d.displacements / max) * 165}
                  width={bar}
                  height={(d.displacements / max) * 165}
                  fill="#0b817c"
                />
                <rect
                  x={x + bar + 3}
                  y={195 - (d.commercial_trips / max) * 165}
                  width={bar}
                  height={(d.commercial_trips / max) * 165}
                  fill="#3267b3"
                />
                {index % Math.max(1, Math.ceil(data.length / 12)) === 0 && (
                  <text x={x + 4} y={218} fontSize={11} fill="#476276">
                    {dayLabel(d.day).slice(0, 5)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <p role="status">
        {selected
          ? `${dayLabel(selected.day)} · ${number(selected.displacements)} deslocamentos · ${number(selected.commercial_trips)} viagens comerciais`
          : "Selecione um dia para consultar os valores."}
      </p>
      <details>
        <summary>Consultar dados do gráfico diário</summary>
        <div className="reports-table">
          <table>
            <thead>
              <tr>
                <th>Dia</th>
                <th>Deslocamentos</th>
                <th>Viagens comerciais</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.day}>
                  <td>{dayLabel(d.day)}</td>
                  <td>{number(d.displacements)}</td>
                  <td>{number(d.commercial_trips)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function Distribution({
  title,
  items,
}: {
  title: string;
  items: { status: string; count: number }[];
}) {
  const total = items.reduce((sum, i) => sum + i.count, 0);
  return (
    <section className="manager-panel">
      <h2>{title}</h2>
      {!total ? (
        <p>Sem registros no período.</p>
      ) : (
        items.map((i) => (
          <div className="manager-bar-row" key={i.status}>
            <div>
              <span>{labels[i.status] || i.status}</span>
              <strong>{number(i.count)}</strong>
            </div>
            <div className="manager-track">
              <span style={{ width: `${(i.count / total) * 100}%` }} />
            </div>
          </div>
        ))
      )}
    </section>
  );
}

export function ManagementDashboard({
  user,
  onConsumption,
  onOpenTrip,
}: {
  user: User;
  onConsumption: () => void;
  onOpenTrip?: (id: string) => void;
}) {
  const today = localToday();
  const [filters, setFilters] = useState({
    start: today.slice(0, 7) + "-01",
    end: monthEnd(today),
    status: "",
    trip_id: "",
    vehicle_id: "",
  });
  const [submitted, setSubmitted] = useState(filters);
  const trips = useQuery({
    queryKey: ["manager", "trips"],
    queryFn: () => api<{ id: string; name: string }[]>("/trips"),
  });
  const vehicles = useQuery({
    queryKey: ["manager", "vehicles"],
    queryFn: () =>
      api<{ id: string; name: string; plate: string }[]>("/vehicles"),
  });
  const params = new URLSearchParams(
    Object.entries(submitted).filter(([, value]) => !!value),
  );
  const report = useQuery({
    queryKey: ["reports", "management", params.toString()],
    queryFn: () => api<Management>(`/reports/management?${params}`),
    retry: false,
  });
  const data = report.data;
  function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitted({ ...filters });
  }
  function shortcut(month: boolean) {
    const end = localToday();
    const previous = new Date(end + "T12:00:00-03:00");
    previous.setUTCDate(previous.getUTCDate() - 29);
    const next = {
      ...filters,
      start: month
        ? end.slice(0, 7) + "-01"
        : previous.toISOString().slice(0, 10),
      end: month ? monthEnd(end) : end,
    };
    setFilters(next);
    setSubmitted(next);
  }
  return (
    <div className="management-dashboard">
      <div className="reports-summary">
        <button className="button secondary" onClick={() => shortcut(true)}>
          Mês atual
        </button>
        <button className="button secondary" onClick={() => shortcut(false)}>
          Últimos 30 dias
        </button>
        {user.role === "admin" && (
          <button className="button secondary" onClick={onConsumption}>
            Consultar franquia
          </button>
        )}
      </div>
      <form className="reports-filters" onSubmit={submit}>
        <Field label="Data inicial">
          <input
            type="date"
            required
            value={filters.start}
            onChange={(e) => setFilters({ ...filters, start: e.target.value })}
          />
        </Field>
        <Field label="Data final">
          <input
            type="date"
            required
            min={filters.start}
            value={filters.end}
            onChange={(e) => setFilters({ ...filters, end: e.target.value })}
          />
        </Field>
        <Field label="Situação da viagem">
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="">Todas</option>
            {["scheduled", "in_progress", "completed", "cancelled"].map((s) => (
              <option key={s} value={s}>
                {labels[s]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Veículo do relatório">
          <select
            value={filters.vehicle_id}
            disabled={vehicles.isPending || !!vehicles.error}
            onChange={(e) =>
              setFilters({ ...filters, vehicle_id: e.target.value })
            }
          >
            <option value="">Todos</option>
            {vehicles.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} · {v.plate}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Viagem do relatório">
          <select
            value={filters.trip_id}
            disabled={trips.isPending || !!trips.error}
            onChange={(e) =>
              setFilters({ ...filters, trip_id: e.target.value })
            }
          >
            <option value="">Todas</option>
            {trips.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </Field>
        <button className="button primary" disabled={report.isFetching}>
          Aplicar filtros
        </button>
      </form>
      <p className="muted">
        Período aplicado: {dayLabel(submitted.start)} a{" "}
        {dayLabel(submitted.end)} · horário de Brasília. Deslocamentos e
        ocupação usam cada saída no período. Vendas e reservas usam a saída
        inicial da viagem, sem repetir valores nos destinos do pacote. Ao
        filtrar um veículo, a venda do pacote permanece integral se ele atender
        a reserva.
      </p>
      {(trips.error || vehicles.error) && (
        <Alert>
          Não foi possível carregar algumas opções de filtro. Atualize a página
          para tentar novamente.
        </Alert>
      )}
      {report.error && (
        <Alert>
          {report.error instanceof Error
            ? report.error.message
            : "Não foi possível carregar a visão gerencial."}
        </Alert>
      )}
      {report.isPending ? (
        <p role="status">Carregando visão gerencial…</p>
      ) : (
        data &&
        !report.error && (
          <>
            <div className="reports-summary">
              <span className="muted">
                Atualizado em {date(data.generated_at)}
              </span>
              <button
                className="button secondary"
                disabled={report.isFetching}
                onClick={() => void report.refetch()}
              >
                Atualizar indicadores
              </button>
            </div>
            <div className="manager-kpis">
              {[
                ["Viagens comerciais", number(data.summary.commercial_trips)],
                ["Deslocamentos", number(data.summary.displacements)],
                ["Ocupação confirmada", percent(data.summary.occupancy_pct)],
                [
                  "Passageiros confirmados",
                  number(data.summary.confirmed_passengers),
                ],
                [
                  "Famílias / reservas confirmadas",
                  number(data.summary.confirmed_families),
                ],
                ["Valor confirmado", money(data.summary.confirmed_value_cents)],
                ["Marcado PAGO", money(data.summary.paid_value_cents)],
                ["Confirmado não pago", money(data.summary.unpaid_value_cents)],
                [
                  "Ticket médio por passageiro",
                  data.summary.average_ticket_cents === null
                    ? "Sem dados"
                    : money(data.summary.average_ticket_cents),
                ],
              ].map(([label, value]) => (
                <section className="manager-kpi" key={label}>
                  <h2>{label}</h2>
                  <strong>{value}</strong>
                </section>
              ))}
            </div>
            <p className="muted">
              Valores de reservas confirmadas e pagamentos marcados manualmente,
              excluindo viagens canceladas. Não representam conciliação
              bancária, fluxo de caixa ou lucro. Passageiros são participações
              nas reservas; a mesma pessoa em viagens diferentes é contada em
              cada contratação.
            </p>
            {!data.summary.commercial_trips && !data.summary.displacements && (
              <div className="empty-state">
                <h2>Sem viagens neste período</h2>
                <p>
                  Altere as datas ou os filtros para consultar sua operação.
                </p>
              </div>
            )}
            <div className="manager-grid">
              <DailyChart data={data.daily} />
              <section className="manager-panel">
                <h2>Ocupação por veículo</h2>
                <p className="muted">
                  Pico confirmado por deslocamento dividido pela capacidade
                  registrada. Consolidação ponderada pela capacidade; canceladas
                  excluídas.
                </p>
                {!data.vehicles.length ? (
                  <p>Sem veículos com deslocamentos neste período.</p>
                ) : (
                  data.vehicles.map((v) => (
                    <div className="manager-bar-row" key={v.vehicle_id}>
                      <div>
                        <span>
                          {v.name} · {v.plate}
                        </span>
                        <strong>{percent(v.occupancy_pct)}</strong>
                      </div>
                      <div
                        className="manager-track"
                        role="meter"
                        aria-label={`Ocupação de ${v.name}`}
                        aria-valuenow={v.occupancy_pct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <span
                          style={{
                            width: `${Math.min(100, v.occupancy_pct)}%`,
                          }}
                        />
                      </div>
                      <small>
                        {v.displacements} deslocamentos · soma dos picos:{" "}
                        {number(v.confirmed_peak_sum)} /{" "}
                        {number(v.capacity_sum)} lugares · pico temporário
                        acumulado: {number(v.held_peak_sum)}
                      </small>
                    </div>
                  ))
                )}
              </section>
              <Distribution
                title="Viagens por situação"
                items={data.trip_statuses}
              />
              <Distribution
                title="Reservas por situação"
                items={data.reservation_statuses}
              />
              <section className="manager-panel">
                <h2>Destinos e pacotes mais vendidos</h2>
                <p className="muted">
                  Até 10 produtos por passageiros confirmados. O valor do pacote
                  não é dividido entre destinos.
                </p>
                {!data.ranking.length ? (
                  <p>Sem reservas confirmadas no período.</p>
                ) : (
                  <div className="reports-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Destino / produto</th>
                          <th>Passageiros</th>
                          <th>Valor confirmado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.ranking.map((r) => (
                          <tr key={`${r.product_key}:${r.name}`}>
                            <td>{r.name}</td>
                            <td>{number(r.passengers)}</td>
                            <td>{money(r.value_cents)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
              <section className="manager-panel manager-wide">
                <h2>Próximas saídas com baixa ocupação</h2>
                <p className="muted">
                  Até 30 alocações futuras do período aplicado, com menos de 50%
                  de ocupação confirmada. Lugares disponíveis consideram também
                  bloqueios temporários válidos e o segmento mais ocupado.
                </p>
                {!data.upcoming.length ? (
                  <p>
                    Nenhuma saída futura com baixa ocupação neste período.
                    Inclua datas futuras no filtro para acompanhar próximas
                    saídas.
                  </p>
                ) : (
                  <div className="reports-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Saída</th>
                          <th>Viagem / deslocamento</th>
                          <th>Veículo</th>
                          <th>Ocupação</th>
                          <th>Disponíveis</th>
                          {onOpenTrip && <th>Ação</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {data.upcoming.map((t) => (
                          <tr key={`${t.allocation_id}:${t.leg_id}`}>
                            <td>{date(t.starts_at)}</td>
                            <td>
                              {t.trip_name} · {t.leg_position}
                              <br />
                              {t.destination}
                            </td>
                            <td>
                              {t.vehicle_name} · {t.plate}
                            </td>
                            <td>{percent(t.occupancy_pct)}</td>
                            <td>{number(t.available)}</td>
                            {onOpenTrip && (
                              <td>
                                <button
                                  className="button secondary"
                                  onClick={() => onOpenTrip(t.trip_id)}
                                >
                                  Consultar viagem
                                </button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          </>
        )
      )}
    </div>
  );
}
