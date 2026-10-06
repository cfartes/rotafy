import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Company, type User } from "./api";
import { Alert, Field } from "./components/ui";
import "./reports.css";

type Row = Record<string, string | number | boolean>;
type OperationsReport = {
  generated_at: string;
  trips: Row[];
  occupancy: Row[];
  reservations: Row[];
  presence: Row[];
};
type ConsumptionReport = { periods: Row[]; generated_at: string };
type Category = "occupancy" | "reservations" | "presence" | "consumption";
const labels: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmada",
  cancelled: "Cancelada",
  expired: "Expirada",
};
const columns: Record<Category, [string, string][]> = {
  occupancy: [
    ["trip_name", "Viagem"],
    ["vehicle_name", "Veículo"],
    ["leg_position", "Trecho"],
    ["origin", "De"],
    ["destination", "Até"],
    ["capacity", "Capacidade"],
    ["confirmed", "Confirmados"],
    ["held", "Bloqueados"],
    ["available", "Disponíveis"],
  ],
  reservations: [
    ["trip_name", "Viagem"],
    ["contact_name", "Responsável"],
    ["vehicle_name", "Veículo"],
    ["passenger_count", "Passageiros"],
    ["status", "Reserva"],
    ["is_paid", "Pagamento manual"],
    ["total_cents", "Valor do pacote"],
  ],
  presence: [
    ["trip_name", "Viagem"],
    ["vehicle_name", "Veículo"],
    ["leg_position", "Trecho"],
    ["origin", "Origem"],
    ["destination", "Destino"],
    ["waiting", "Aguardando"],
    ["onboard", "A bordo"],
    ["alighted", "Desembarcados"],
  ],
  consumption: [
    ["company_name", "Empresa"],
    ["plan_name", "Plano"],
    ["starts_at", "Início do ciclo"],
    ["ends_at", "Fim do ciclo"],
    ["included_trips", "Franquia"],
    ["used_trips", "Viagens usadas"],
    ["remaining_trips", "Restantes"],
    ["extra_trips", "Extras"],
    ["estimated_total_cents", "Valor estimado"],
  ],
};
const dateInput = (date: Date) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
const money = (value: number) =>
  (value / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
function display(key: string, value: Row[string]) {
  if (key.endsWith("_cents")) return money(Number(value));
  if (key.endsWith("_at"))
    return new Date(String(value)).toLocaleDateString("pt-BR", {
      timeZone: "America/Sao_Paulo",
    });
  if (key === "is_paid") return value ? "PAGO" : "NÃO PAGO";
  if (key === "status") return labels[String(value)] || String(value);
  return String(value);
}
export function Reports({
  user,
  companies,
}: {
  user: User;
  companies: Company[];
}) {
  const isNexus = user.role === "nexus";
  const [category, setCategory] = useState<Category>(
    isNexus ? "consumption" : "occupancy",
  );
  const [filters, setFilters] = useState({
    start: dateInput(new Date(Date.now() - 30 * 86400000)),
    end: dateInput(new Date()),
    company_id: "",
    trip_id: "",
  });
  const [submitted, setSubmitted] = useState(filters);
  const [payment, setPayment] = useState("all");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const params = new URLSearchParams({
    start: submitted.start,
    end: submitted.end,
  });
  if (submitted.trip_id && category !== "consumption")
    params.set("trip_id", submitted.trip_id);
  if (isNexus && submitted.company_id)
    params.set("company_id", submitted.company_id);
  const url = `/reports/${category === "consumption" ? "consumption" : "operations"}?${params}`;
  const report = useQuery({
    queryKey: ["reports", url],
    queryFn: () => api<OperationsReport | ConsumptionReport>(url),
    retry: false,
  });
  const data = report.data;
  const allRows = data
    ? "periods" in data
      ? data.periods
      : data[category as Exclude<Category, "consumption">]
    : [];
  const rows =
    category === "reservations" && payment !== "all"
      ? allRows.filter((r) => r.is_paid === (payment === "paid"))
      : allRows;
  function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitted({ ...filters });
    setExportError("");
  }
  async function download() {
    setExporting(true);
    setExportError("");
    try {
      const query = new URLSearchParams(params);
      query.set("category", category);
      const response = await fetch(`/api/v1/reports/export?${query}`, {
        credentials: "same-origin",
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Não foi possível exportar.");
      }
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = `rotafy-${category}-${submitted.start}-${submitted.end}.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
    } catch (e) {
      setExportError(
        e instanceof Error ? e.message : "Não foi possível exportar.",
      );
    } finally {
      setExporting(false);
    }
  }
  return (
    <section className="reports-page">
      <div className="reports-tabs" role="group" aria-label="Tipo de relatório">
        {(
          [
            ["occupancy", "Ocupação"],
            ["reservations", "Reservas e pagamentos"],
            ["presence", "Presença"],
            ["consumption", "Consumo da franquia"],
          ] as [Category, string][]
        )
          .filter(([id]) =>
            isNexus
              ? id === "consumption"
              : id !== "consumption" || user.role === "admin",
          )
          .map(([id, label]) => (
            <button
              key={id}
              className={`button ${category === id ? "primary" : "secondary"}`}
              aria-pressed={category === id}
              onClick={() => {
                setCategory(id);
                setExportError("");
              }}
            >
              {label}
            </button>
          ))}
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
        {isNexus && (
          <Field label="Empresa do relatório">
            <select
              value={filters.company_id}
              onChange={(e) =>
                setFilters({ ...filters, company_id: e.target.value })
              }
            >
              <option value="">Todas as empresas</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.trade_name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {!isNexus && category !== "consumption" && (
          <Field label="Viagem do relatório">
            <select
              value={filters.trip_id}
              onChange={(e) =>
                setFilters({ ...filters, trip_id: e.target.value })
              }
            >
              <option value="">Todas no período</option>
              {data &&
                "trips" in data &&
                data.trips.map((t) => (
                  <option key={String(t.id)} value={String(t.id)}>
                    {String(t.name)}
                  </option>
                ))}
            </select>
          </Field>
        )}
        <button className="button primary" disabled={report.isFetching}>
          Aplicar filtros
        </button>
      </form>
      <p className="muted">
        {category === "consumption"
          ? "Ciclos iniciados no período selecionado. Valores estimados do plano e extras; nenhum pagamento é processado."
          : "Viagens com partida no período, considerando as datas de Brasília. Presença inclui apenas registros aceitos pelo servidor; ações offline pendentes não aparecem."}
      </p>
      {category === "occupancy" && (
        <p className="muted">
          Cada linha representa um segmento do trecho. Bloqueios vencidos não
          ocupam vagas; contagens de segmentos e ida/volta não devem ser somadas
          como passageiros únicos.
        </p>
      )}
      {category === "reservations" && (
        <Field label="Mostrar pagamento">
          <select value={payment} onChange={(e) => setPayment(e.target.value)}>
            <option value="all">Todos</option>
            <option value="paid">PAGO</option>
            <option value="unpaid">NÃO PAGO</option>
          </select>
        </Field>
      )}
      {(report.error || exportError) && (
        <Alert>
          {exportError ||
            (report.error instanceof Error
              ? report.error.message
              : "Não foi possível carregar.")}
        </Alert>
      )}
      {report.isPending ? (
        <p role="status">Carregando relatório…</p>
      ) : (
        !report.error && (
          <>
            <div className="reports-summary">
              <span role="status">{rows.length} registros exibidos</span>
              {data && (
                <span className="muted">
                  Atualizado em{" "}
                  {new Date(data.generated_at).toLocaleString("pt-BR", {
                    timeZone: "America/Sao_Paulo",
                  })}
                </span>
              )}
              <button
                className="button secondary"
                onClick={() => void download()}
                disabled={exporting || !allRows.length}
              >
                {exporting ? "Exportando…" : "Exportar CSV completo"}
              </button>
              <button
                className="button secondary"
                onClick={() => void report.refetch()}
                disabled={report.isFetching}
              >
                Atualizar relatório
              </button>
            </div>
            {category === "reservations" && payment !== "all" && (
              <p className="muted">
                A exportação contém todos os pagamentos no período aplicado. O
                filtro PAGO/NÃO PAGO é uma visualização da tabela.
              </p>
            )}
            {!rows.length ? (
              <div className="empty-state">
                <h2>Sem registros neste período</h2>
                <p>
                  Altere as datas e aplique os filtros para consultar outras
                  viagens ou ciclos.
                </p>
              </div>
            ) : (
              <div
                className="reports-table"
                tabIndex={0}
                aria-label="Tabela do relatório com rolagem horizontal"
                role="region"
              >
                <table>
                  <caption>
                    {category === "consumption"
                      ? "Consumo por empresa e ciclo"
                      : category === "occupancy"
                        ? "Ocupação por veículo e segmento"
                        : category === "presence"
                          ? "Presença por veículo e trecho"
                          : "Reservas familiares e pagamento manual"}
                  </caption>
                  <thead>
                    <tr>
                      {columns[category].map(([key, title]) => (
                        <th scope="col" key={key}>
                          {title}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i}>
                        {columns[category].map(([key]) => (
                          <td key={key}>{display(key, row[key])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )
      )}
    </section>
  );
}
