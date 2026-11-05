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
  const cards = data
    ? [
        ["Viagens concluídas", number(data.summary.completed_trips)],
        ["Viagens em andamento", number(data.summary.running_trips)],
        ["Viagens agendadas", number(data.summary.scheduled_trips)],
        ["Viagens canceladas", number(data.summary.cancelled_trips)],
        ...(data.active_routes !== null
          ? [["Rotas ativas", number(data.active_routes)]]
          : []),
        ...(data.sales
          ? [
              [
                "Reservas confirmadas",
                number(data.sales.confirmed_reservations),
              ],
              ["Passageiros reservados", number(data.sales.passengers)],
              ["Valor das reservas", money(data.sales.reserved_cents)],
              ["Pagamentos registrados", money(data.sales.paid_cents)],
            ]
          : []),
      ]
    : [];
  return (
    <div className="company-dashboard">
      <section className="panel modal-form">
        <h2>Resultado da operação</h2>
        <form className="history-filters" onSubmit={search}>
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
          <button className="button secondary" disabled={query.isFetching}>
            Atualizar indicadores
          </button>
        </form>
        <p className="muted">
          Viagens pela data de saída, no horário de Brasília. Reservas e
          passageiros pertencem a essas viagens; valores não incluem reservas ou
          viagens canceladas. Rotas ativas refletem o cadastro atual. Pacotes
          contam uma viagem comercial, sem multiplicar por veículo ou trecho.
        </p>
      </section>
      {query.isPending && <p role="status">Carregando indicadores…</p>}
      {query.error && <Alert>{query.error.message}</Alert>}
      {data && (
        <>
          <div className="stats-grid">
            {cards.map(([label, value]) => (
              <article className="stat-card" key={label}>
                <small>{label}</small>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
          {data.active_routes !== null && (
            <section className="panel">
              <header className="panel-header">
                <div>
                  <h2>Rotas mais usadas</h2>
                  <p className="muted">
                    Até 20 rotas, por viagens concluídas no período. Excluídas
                    do catálogo continuam no histórico.
                  </p>
                </div>
              </header>
              {data.ranking.length ? (
                <div className="table-scroll">
                  <PaginatedTable>
                    <thead>
                      <tr>
                        <th>Rota</th>
                        <th>Viagens concluídas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.ranking.map((r) => (
                        <tr key={r.id}>
                          <td>
                            {r.name}
                            {r.removed ? " · Excluída do catálogo" : ""}
                          </td>
                          <td>{number(r.completed_trips)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </PaginatedTable>
                </div>
              ) : (
                <p className="empty-state">
                  Nenhuma viagem concluída com rota vinculada neste período.
                </p>
              )}
            </section>
          )}
          <section className="panel">
            <header className="panel-header">
              <div>
                <h2>Próximas saídas</h2>
                <p className="muted">
                  Até 20 viagens futuras, independentemente do filtro do
                  período.
                </p>
              </div>
            </header>
            {data.upcoming.length ? (
              <div className="table-scroll">
                <PaginatedTable>
                  <thead>
                    <tr>
                      <th>Viagem</th>
                      <th>Destino</th>
                      <th>Saída · Brasília</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.upcoming.map((t) => (
                      <tr key={t.id}>
                        <td>{t.name}</td>
                        <td>{t.destination}</td>
                        <td>{date(t.starts_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </PaginatedTable>
              </div>
            ) : (
              <p className="empty-state">Nenhuma próxima saída agendada.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
