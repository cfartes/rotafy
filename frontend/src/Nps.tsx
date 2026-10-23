import { DataUseNotice } from "./components/DataUseNotice";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";
import "./nps.css";
import { NpsQualityInbox } from "./NpsQuality";

type Settings = { service_enabled: boolean; trip_enabled: boolean };
type Metrics = {
  surveys: number;
  sent: number;
  responses: number;
  response_rate: number | null;
  nps: number | null;
  average: number | null;
  promoters: number;
  passives: number;
  detractors: number;
};
type Row = {
  id: string;
  kind: "service" | "trip";
  trip_name: string | null;
  contact_name: string;
  phone: string;
  status: string;
  score: number | null;
  comment: string | null;
  created_at: string;
  answered_at: string | null;
  error_code: string | null;
};
type Report = {
  summary: Metrics;
  by_kind: Record<string, Metrics>;
  evolution: (Metrics & { month: string })[];
  rows: Row[];
  total: number;
  page: number;
};
const states: Record<string, string> = {
  pending: "Na fila",
  sending: "Enviando",
  sent: "Enviada — aguardando resposta",
  uncertain: "Envio incerto",
  failed: "Falhou",
  discarded: "Descartada",
  answered: "Respondida",
  skipped: "Não participou",
  expired: "Expirada",
};
const kinds = { service: "Atendimento", trip: "Viagem" };
const dateTime = (date: string) =>
  new Date(date).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
const number = (value: number | null | undefined, suffix = "") =>
  value == null ? "—" : `${value.toLocaleString("pt-BR")}${suffix}`;
function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function Configuration({
  value,
  onSaved,
}: {
  value: Settings;
  onSaved: () => void;
}) {
  const [service, setService] = useState(value.service_enabled);
  const [trip, setTrip] = useState(value.trip_enabled);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/nps/settings", {
        method: "PUT",
        body: JSON.stringify({ service_enabled: service, trip_enabled: trip }),
      });
      onSaved();
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="panel nps-settings">
      <summary>Configurar pesquisas automáticas</summary>
      <form onSubmit={save}>
        <DataUseNotice />
        <label className="nps-toggle">
          <input
            type="checkbox"
            checked={service}
            onChange={(e) => setService(e.target.checked)}
          />{" "}
          Enviar NPS após concluir atendimento humano
        </label>
        <p>Uma pesquisa de atendimento por telefone a cada sete dias.</p>
        <label className="nps-toggle">
          <input
            type="checkbox"
            checked={trip}
            onChange={(e) => setTrip(e.target.checked)}
          />{" "}
          Enviar NPS duas horas após concluir a viagem completa
        </label>
        <p>
          Somente reservas confirmadas com embarque registrado. Pacotes são
          avaliados após a conclusão completa.
        </p>
        <p>
          As perguntas pedem uma nota de recomendação de 0 a 10 e um comentário
          opcional. O cliente tem 24 horas para responder e pode enviar PULAR ou
          ENCERRAR. Os convites respeitam uma fila com intervalo configurado pela Nexus (padrão: 30 segundos). Ativar não envia pesquisas de atendimentos ou viagens
          concluídos anteriormente.
        </p>
        {error && <Alert>{error}</Alert>}
        {saved && <p role="status">Configuração salva.</p>}
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? "Salvando…" : "Salvar configuração NPS"}
        </button>
      </form>
    </details>
  );
}

export function NpsSettings() {
  const cache = useQueryClient();
  const settings = useQuery({
    queryKey: ["nps-settings"],
    queryFn: () => api<Settings>("/nps/settings"),
  });
  if (settings.error)
    return <Alert>Não foi possível consultar as configurações do NPS.</Alert>;
  return settings.data && typeof settings.data.service_enabled === "boolean" ? (
    <Configuration
      value={settings.data}
      onSaved={() =>
        void cache.invalidateQueries({ queryKey: ["nps-settings"] })
      }
    />
  ) : null;
}

export function Nps({ canConfigure }: { canConfigure: boolean }) {
  const cache = useQueryClient();
  const initialEnd = today();
  const initial = {
    start: initialEnd.slice(0, 8) + "01",
    end: initialEnd,
    kind: "",
    trip_id: "",
    classification: "",
    status: "",
  };
  const [draft, setDraft] = useState(initial),
    [filters, setFilters] = useState(initial),
    [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false),
    [error, setError] = useState("");
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, value]) => value),
  );
  const query = useQuery({
    queryKey: ["nps-report", filters, page],
    queryFn: () => api<Report>(`/nps/report?${params}&page=${page}`),
    refetchInterval: 30000,
  });
  const settings = useQuery({
    queryKey: ["nps-settings"],
    queryFn: () => api<Settings>("/nps/settings"),
  });
  const trips = useQuery({
    queryKey: ["nps-trips"],
    queryFn: () => api<{ id: string; name: string }[]>("/nps/trips"),
  });
  async function download(format: "csv" | "pdf") {
    setExporting(true);
    setError("");
    try {
      const response = await fetch(
        `/api/v1/nps/report?${params}&output=${format}`,
        { credentials: "same-origin", signal: AbortSignal.timeout(60000) },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Não foi possível emitir o relatório.",
        );
      }
      const url = URL.createObjectURL(await response.blob()),
        link = document.createElement("a");
      link.href = url;
      link.download = `nps-${filters.start}-${filters.end}.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível emitir o relatório.",
      );
    } finally {
      setExporting(false);
    }
  }
  const m = query.data?.summary;
  const cards = [
    ["NPS", number(m?.nps)],
    ["Taxa de resposta", number(m?.response_rate, "%")],
    ["Nota média", number(m?.average)],
    ["Promotores (9–10)", number(m?.promoters)],
    ["Neutros (7–8)", number(m?.passives)],
    ["Detratores (0–6)", number(m?.detractors)],
  ];
  return (
    <div className="nps-page">
      <NpsQualityInbox />
      {canConfigure && settings.data && (
        <Configuration
          value={settings.data}
          onSaved={() =>
            void cache.invalidateQueries({ queryKey: ["nps-settings"] })
          }
        />
      )}
      {settings.error && (
        <Alert>Não foi possível consultar a configuração das pesquisas.</Alert>
      )}
      <section className="panel">
        <div className="panel-header">
          <h2>NPS e satisfação</h2>
          <p>
            Acompanhe a recomendação dos clientes após o atendimento e a viagem.
          </p>
        </div>
        <form
          className="nps-filters"
          onSubmit={(e) => {
            e.preventDefault();
            setFilters({ ...draft });
            setPage(1);
          }}
        >
          <DataUseNotice />
          <Field label="Data inicial">
            <input
              type="date"
              value={draft.start}
              required
              onChange={(e) => setDraft({ ...draft, start: e.target.value })}
            />
          </Field>
          <Field label="Data final">
            <input
              type="date"
              min={draft.start}
              value={draft.end}
              required
              onChange={(e) => setDraft({ ...draft, end: e.target.value })}
            />
          </Field>
          <Field label="Tipo de pesquisa">
            <select
              value={draft.kind}
              onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
            >
              <option value="">Todos</option>
              <option value="service">Atendimento</option>
              <option value="trip">Viagem</option>
            </select>
          </Field>
          <Field label="Viagem ou pacote">
            <select
              value={draft.trip_id}
              onChange={(e) => setDraft({ ...draft, trip_id: e.target.value })}
            >
              <option value="">Todas</option>
              {trips.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Classificação">
            <select
              value={draft.classification}
              onChange={(e) =>
                setDraft({ ...draft, classification: e.target.value })
              }
            >
              <option value="">Todas</option>
              <option value="promoter">Promotores</option>
              <option value="passive">Neutros</option>
              <option value="detractor">Detratores</option>
              <option value="unanswered">Sem nota</option>
            </select>
          </Field>
          <Field label="Situação">
            <select
              value={draft.status}
              onChange={(e) => setDraft({ ...draft, status: e.target.value })}
            >
              <option value="">Todas</option>
              {Object.entries(states).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <button type="submit" className="button primary">
            Consultar NPS
          </button>
        </form>
        <p className="nps-explanation">
          Período de criação das pesquisas, no horário de Brasília, limitado a
          366 dias. NPS = % de promotores − % de detratores. Taxa de resposta =
          notas recebidas ÷ pesquisas enviadas. Sem respostas, os indicadores
          mostram “—”.
        </p>
      </section>
      {(error || query.error) && (
        <Alert>
          {error ||
            (query.error instanceof Error
              ? query.error.message
              : "Não foi possível consultar.")}
        </Alert>
      )}
      {query.isPending && <p role="status">Carregando avaliações…</p>}
      {query.data && (
        <>
          <div className="nps-cards">
            {cards.map(([label, value]) => (
              <article className="nps-card" key={label}>
                <h3>{label}</h3>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
          <p>
            {m?.responses} respostas · {m?.sent} pesquisas enviadas ·{" "}
            {query.data.total} pesquisas no filtro.
          </p>
          {!filters.kind && (
            <div className="nps-comparison">
              {Object.entries(query.data.by_kind).map(([kind, metrics]) => (
                <article className="panel" key={kind}>
                  <h3>{kinds[kind as keyof typeof kinds]}</h3>
                  <p>
                    NPS: <strong>{number(metrics.nps)}</strong> ·{" "}
                    {metrics.responses} respostas · taxa:{" "}
                    {number(metrics.response_rate, "%")}
                  </p>
                </article>
              ))}
            </div>
          )}
          <section className="panel">
            <div className="panel-header">
              <h2>Evolução por mês</h2>
            </div>
            <div className="nps-table">
              <table>
                <thead>
                  <tr>
                    <th>Mês de criação</th>
                    <th>NPS</th>
                    <th>Respostas</th>
                    <th>Taxa de resposta</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.evolution.map((row) => (
                    <tr key={row.month}>
                      <td>{row.month.split("-").reverse().join("/")}</td>
                      <td>{number(row.nps)}</td>
                      <td>{row.responses}</td>
                      <td>{number(row.response_rate, "%")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel">
            <div className="panel-header">
              <h2>Avaliações dos clientes</h2>
              <div className="nps-actions">
                <button
                  className="button secondary"
                  disabled={exporting}
                  onClick={() => void download("csv")}
                >
                  Exportar CSV
                </button>
                <button
                  className="button secondary"
                  disabled={exporting}
                  onClick={() => void download("pdf")}
                >
                  Emitir PDF
                </button>
              </div>
            </div>
            {!query.data.total ? (
              <p className="nps-explanation">
                Nenhuma pesquisa encontrada para este filtro.
              </p>
            ) : (
              <div className="nps-table">
                <table>
                  <thead>
                    <tr>
                      <th>Cliente / tipo</th>
                      <th>Viagem</th>
                      <th>Situação</th>
                      <th>Nota</th>
                      <th>Comentário</th>
                      <th>Datas (Brasília)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          {row.contact_name || "Cliente"}
                          <br />
                          {row.phone}
                          <br />
                          {kinds[row.kind]}
                        </td>
                        <td>{row.trip_name || "—"}</td>
                        <td>
                          {states[row.status] || row.status}
                          {row.error_code && (
                            <small> · Confira a conexão e a conversa.</small>
                          )}
                        </td>
                        <td>{row.score ?? "—"}</td>
                        <td>{row.comment || "—"}</td>
                        <td>
                          Criada: {dateTime(row.created_at)}
                          {row.answered_at && (
                            <>
                              <br />
                              Nota: {dateTime(row.answered_at)}
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="nps-pagination">
              <button
                className="button secondary"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span>
                Página {page} de {Math.max(1, Math.ceil(query.data.total / 50))}
              </span>
              <button
                className="button secondary"
                disabled={page * 50 >= query.data.total}
                onClick={() => setPage(page + 1)}
              >
                Próxima
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
