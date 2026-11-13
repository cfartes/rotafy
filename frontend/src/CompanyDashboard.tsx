import {
  BusFront,
  CalendarDays,
  CheckCheck,
  CircleOff,
  Ticket,
  Users,
  Wallet,
  ReceiptText,
  Route as RouteIcon,
  CalendarClock,
  Info,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import "./company-dashboard.css";
import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type User } from "./api";
import { hasModule } from "./modules";
import { Alert, Field } from "./components/ui";
import { PaginatedTable } from "./components/PaginatedTable";
import { localToday, money } from "./billing/types";

type Overview = {
  summary: {
    completed_trips: number;
    running_trips: number;
    scheduled_trips: number;
    cancelled_trips: number;
  };
  active_routes: number | null;
  sales: {
    confirmed_reservations: number;
    passengers: number;
    reserved_cents: number;
    paid_cents: number;
  } | null;
  ranking: {
    id: string;
    name: string;
    removed: boolean;
    completed_trips: number;
  }[];
  upcoming: {
    id: string;
    name: string;
    starts_at: string;
    destination: string;
  }[];
};
const number = (n: number) => n.toLocaleString("pt-BR");
const date = (value: string) =>
  new Date(value).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "short",
  });

export function CompanyDashboard({ user }: { user: User }) {
  const [period, setPeriod] = useState(() => ({
    start: localToday().slice(0, 8) + "01",
    end: localToday(),
  }));
  const query = useQuery({
    queryKey: ["company-dashboard", period],
    queryFn: async () => {
      const result = await api<Overview>(
        `/dashboard?start=${period.start}&end=${period.end}`,
      );
      if (!result.summary)
        throw new Error(
          "Não foi possível obter os indicadores. Tente atualizar novamente.",
        );
      return result;
    },
    enabled: hasModule(user, "trips"),
  });
  function search(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const next = {
      start: String(form.get("start")),
      end: String(form.get("end")),
    };
    if (next.start === period.start && next.end === period.end)
      void query.refetch();
    else setPeriod(next);
  }
  if (!hasModule(user, "trips"))
    return (
      <section className="panel modal-form">
        <h2>Bem-vindo à sua operação</h2>
        <p>Utilize o menu lateral para acessar os módulos contratados.</p>
      </section>
    );
  const data = query.data;
  const operation = data
    ? [
        {
          label: "Viagens em andamento",
          value: number(data.summary.running_trips),
          icon: BusFront,
          tone: "active",
          description: "Operação em curso",
        },
        {
          label: "Viagens agendadas",
          value: number(data.summary.scheduled_trips),
          icon: CalendarDays,
          tone: "planned",
          description: "Saídas programadas",
        },
        {
          label: "Viagens concluídas",
          value: number(data.summary.completed_trips),
          icon: CheckCheck,
          tone: "complete",
          description: "Viagens realizadas",
        },
        {
          label: "Viagens canceladas",
          value: number(data.summary.cancelled_trips),
          icon: CircleOff,
          tone: "cancelled",
          description: "Cancelamentos no período",
        },
      ]
    : [];
  return (
    <div className="company-dashboard" aria-busy={query.isFetching}>
      <section
        className="panel overview-period"
        aria-labelledby="overview-period-title"
      >
        <div className="overview-period-heading">
          <span className="overview-eyebrow">PAINEL GERENCIAL</span>
          <h2 id="overview-period-title">Resultado da operação</h2>
          <p>Escolha o período para acompanhar viagens, reservas e valores.</p>
        </div>
        <form className="overview-filters" onSubmit={search}>
          <Field label="Início do período">
            <input
              type="date"
              name="start"
              defaultValue={period.start}
              required
            />
          </Field>
          <Field label="Fim do período">
            <input type="date" name="end" defaultValue={period.end} required />
          </Field>
          <button className="button primary" disabled={query.isFetching}>
            <RefreshCw size={16} aria-hidden="true" />
            Atualizar indicadores
          </button>
        </form>
        <details className="overview-methodology">
          <summary>
            <Info size={16} aria-hidden="true" />
            Como os indicadores são calculados
          </summary>
          <p>
            Viagens pela data de saída, no horário de Brasília. Reservas e
            passageiros pertencem a essas viagens; valores não incluem reservas
            ou viagens canceladas. Rotas ativas refletem o cadastro atual.
            Pacotes contam uma viagem comercial, sem multiplicar por veículo ou
            trecho. As próximas saídas são futuras e não dependem do período
            selecionado.
          </p>
        </details>
      </section>
      {query.isPending && (
        <div className="overview-loading">
          <p role="status">Carregando indicadores…</p>
          <div className="overview-metrics" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="overview-placeholder" />
            ))}
          </div>
        </div>
      )}
      {query.error && <Alert>{query.error.message}</Alert>}
      {data && (
        <>
          <section
            className="overview-section"
            aria-labelledby="overview-operation-title"
          >
            <header className="overview-section-heading">
              <div>
                <h2 id="overview-operation-title">Operação no período</h2>
                <p>Da programação à conclusão de cada viagem.</p>
              </div>
              <span className="overview-period-label">
                {period.start.split("-").reverse().join("/")} —{" "}
                {period.end.split("-").reverse().join("/")}
              </span>
            </header>
            <div className="overview-metrics">
              {operation.map((card) => (
                <OverviewMetric key={card.label} {...card} />
              ))}
            </div>
          </section>
          {data.sales && (
            <section
              className="overview-section"
              aria-labelledby="overview-sales-title"
            >
              <header className="overview-section-heading">
                <div>
                  <h2 id="overview-sales-title">Reservas e valores</h2>
                  <p>Movimento das viagens com saída no período selecionado.</p>
                </div>
              </header>
              <div className="overview-metrics overview-sales">
                <OverviewMetric
                  label="Reservas confirmadas"
                  value={number(data.sales.confirmed_reservations)}
                  icon={Ticket}
                  description="Famílias e grupos confirmados"
                />
                <OverviewMetric
                  label="Passageiros reservados"
                  value={number(data.sales.passengers)}
                  icon={Users}
                  description="Nas reservas confirmadas"
                />
                <OverviewMetric
                  label="Valor das reservas"
                  value={money(data.sales.reserved_cents)}
                  icon={Wallet}
                  tone="money"
                  description="Valor reservado no período"
                />
                <OverviewMetric
                  label="Pagamentos registrados"
                  value={money(data.sales.paid_cents)}
                  icon={ReceiptText}
                  tone="money"
                  description="Recebimentos informados no app"
                />
              </div>
            </section>
          )}
          <div
            className={`overview-bottom${data.active_routes === null ? " overview-bottom-single" : ""}`}
          >
            <section
              className="panel overview-list"
              aria-labelledby="overview-departures-title"
            >
              <header className="panel-header">
                <div className="overview-list-title">
                  <span className="overview-section-icon">
                    <CalendarClock size={20} aria-hidden="true" />
                  </span>
                  <div>
                    <h2 id="overview-departures-title">Próximas saídas</h2>
                    <p>Até 20 viagens futuras · horário de Brasília.</p>
                  </div>
                </div>
                <span className="overview-tag">Agenda</span>
              </header>
              {data.upcoming.length ? (
                <div className="table-scroll">
                  <PaginatedTable aria-labelledby="overview-departures-title">
                    <thead>
                      <tr>
                        <th scope="col">Viagem</th>
                        <th scope="col">Destino</th>
                        <th scope="col">Saída · Brasília</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.upcoming.map((t) => (
                        <tr key={t.id}>
                          <td className="overview-name">{t.name}</td>
                          <td>{t.destination}</td>
                          <td className="overview-date">{date(t.starts_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </PaginatedTable>
                </div>
              ) : (
                <div className="overview-empty">
                  <CalendarClock size={26} aria-hidden="true" />
                  <h3>Nenhuma próxima saída agendada</h3>
                  <p>
                    As próximas viagens aparecerão aqui quando forem
                    cadastradas.
                  </p>
                </div>
              )}
            </section>
            {data.active_routes !== null && (
              <section
                className="panel overview-list"
                aria-labelledby="overview-routes-title"
              >
                <header className="panel-header">
                  <div className="overview-list-title">
                    <span className="overview-section-icon">
                      <RouteIcon size={20} aria-hidden="true" />
                    </span>
                    <div>
                      <h2 id="overview-routes-title">Rotas mais usadas</h2>
                      <p>Por viagens concluídas no período · até 20 rotas.</p>
                    </div>
                  </div>
                  <span className="overview-tag">
                    <strong>{number(data.active_routes)}</strong> Rotas ativas
                  </span>
                </header>
                {data.ranking.length ? (
                  <div className="table-scroll">
                    <PaginatedTable aria-labelledby="overview-routes-title">
                      <thead>
                        <tr>
                          <th scope="col">Rota</th>
                          <th scope="col">Viagens concluídas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.ranking.map((r, i) => (
                          <tr key={r.id}>
                            <td>
                              <div className="overview-route-name">
                                <span
                                  className="overview-rank"
                                  aria-hidden="true"
                                >
                                  {String(i + 1).padStart(2, "0")}
                                </span>
                                <div>
                                  <span className="overview-name">
                                    {r.name}
                                  </span>
                                  {r.removed && (
                                    <small className="overview-removed">
                                      Excluída do catálogo
                                    </small>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="overview-count">
                              {number(r.completed_trips)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </PaginatedTable>
                  </div>
                ) : (
                  <div className="overview-empty">
                    <RouteIcon size={26} aria-hidden="true" />
                    <h3>Ainda sem viagens concluídas</h3>
                    <p>
                      Nenhuma viagem concluída com rota vinculada neste período.
                    </p>
                  </div>
                )}
              </section>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function OverviewMetric({
  label,
  value,
  icon: Icon,
  tone = "neutral",
  description,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: string;
  description: string;
}) {
  return (
    <article className="stat-card overview-metric" data-tone={tone}>
      <div className="overview-metric-heading">
        <h3>{label}</h3>
        <span className="overview-metric-icon">
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
      <strong>{value}</strong>
      <p>{description}</p>
    </article>
  );
}
