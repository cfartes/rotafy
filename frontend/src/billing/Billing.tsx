import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CalendarDays,
  Check,
  Clock3,
  Layers3,
  Plus,
  Route,
  Wallet,
} from "lucide-react";
import { api, ApiError, patch, post, type Company } from "../api";
import { Alert, Field, Modal } from "../components/ui";
import {
  dateOnly,
  localToday,
  money,
  moneyInput,
  parseMoney,
  type Period,
  type Plan,
  type PlanVersion,
  type Report,
  type SubscriptionRow,
} from "./types";

const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";

function PlanEditor({
  plan,
  onClose,
}: {
  plan: Plan | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const data = {
        name: form.get("name"),
        included_trips: Number(form.get("included_trips")),
        price_cents: parseMoney(form.get("price")),
        extra_trip_cents: parseMoney(form.get("extra")),
      };
      await post(plan ? `/nexus/plans/${plan.id}/versions` : "/nexus/plans", {
        ...data,
        ...(plan ? {} : { code: form.get("code") }),
      });
      await client.invalidateQueries({ queryKey: ["billing"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal
      title={plan ? `Condições do plano ${plan.name}` : "Cadastrar plano"}
      onClose={onClose}
    >
      <form className="modal-form" onSubmit={submit}>
        <p className="muted">
          Defina a franquia mensal e os valores. Ciclos já iniciados mantêm as
          condições contratadas.
        </p>
        <Field label="Nome do plano">
          <input
            name="name"
            defaultValue={plan?.name}
            required
            minLength={2}
            maxLength={100}
          />
        </Field>
        {!plan && (
          <Field label="Identificador do plano">
            <input
              name="code"
              placeholder="plano-especial"
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              required
              minLength={2}
              maxLength={50}
            />
          </Field>
        )}
        <Field label="Viagens incluídas por mês">
          <input
            name="included_trips"
            type="number"
            min={0}
            max={1000000}
            step={1}
            required
            defaultValue={plan?.included_trips ?? ""}
          />
        </Field>
        <div className="form-grid">
          <Field label="Valor mensal do plano (R$)">
            <input
              name="price"
              inputMode="decimal"
              placeholder="199,90"
              defaultValue={moneyInput(plan?.price_cents ?? null)}
              required
              maxLength={15}
            />
          </Field>
          <Field label="Valor por viagem extra (R$)">
            <input
              name="extra"
              inputMode="decimal"
              placeholder="15,00"
              defaultValue={moneyInput(plan?.extra_trip_cents ?? null)}
              required
              maxLength={15}
            />
          </Field>
        </div>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar condições"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function PlanHistory({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const history = useQuery({
    queryKey: ["billing", "versions", plan.id],
    queryFn: () => api<PlanVersion[]>(`/nexus/plans/${plan.id}/versions`),
  });
  return (
    <Modal title={`Histórico do plano ${plan.name}`} onClose={onClose}>
      <div className="modal-form">
        <p className="muted">
          Cada versão preserva os valores e a franquia definidos na publicação.
        </p>
        {history.error && <Alert>{message(history.error)}</Alert>}
        {history.isPending ? (
          <p className="muted">Carregando…</p>
        ) : (
          <div className="version-list">
            {history.data?.map((version) => (
              <article key={version.id}>
                <header>
                  <strong>
                    Versão {version.version} · {version.name}
                  </strong>
                  <small>{dateOnly(version.created_at)}</small>
                </header>
                <p>
                  {version.included_trips} viagens/mês ·{" "}
                  {money(version.price_cents)}
                </p>
                <small>Viagem extra: {money(version.extra_trip_cents)}</small>
              </article>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

function SubscribeForm({
  companyId,
  plans,
}: {
  companyId: string;
  plans: Plan[];
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const available = plans.filter((plan) => plan.is_active && plan.version_id);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await post(
        `/nexus/companies/${companyId}/subscription`,
        Object.fromEntries(new FormData(event.currentTarget)),
      );
      await client.invalidateQueries({ queryKey: ["billing"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <form className="subscription-form" onSubmit={submit}>
      <h3>Definir assinatura</h3>
      <p className="muted">
        Vincule um plano para iniciar os ciclos mensais desta empresa.
      </p>
      {available.length === 0 ? (
        <Alert>Configure e ative um plano antes de definir a assinatura.</Alert>
      ) : (
        <>
          <div className="form-grid">
            <Field label="Plano da assinatura">
              <select name="plan_id" required defaultValue="">
                <option value="" disabled>
                  Selecione um plano
                </option>
                {available.map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.name} · {money(plan.price_cents!)} ·{" "}
                    {plan.included_trips} viagens/mês
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Data de início">
              <input
                name="starts_on"
                type="date"
                min={localToday()}
                defaultValue={localToday()}
                required
              />
            </Field>
          </div>
          {error && <Alert>{error}</Alert>}
          <button className="button primary" disabled={pending}>
            {pending ? "Vinculando…" : "Vincular assinatura"}
            <ArrowRight size={16} />
          </button>
        </>
      )}
    </form>
  );
}

function PeriodSummary({ period }: { period: Period }) {
  return (
    <>
      <div className="subscription-banner">
        <span className="subscription-emblem">
          <Layers3 size={27} />
        </span>
        <div>
          <span className="section-kicker">PLANO DO CICLO</span>
          <h2>{period.plan_name}</h2>
          <p>
            {dateOnly(period.starts_at)} até {dateOnly(period.ends_at)}{" "}
            <span className="muted">· início do próximo ciclo</span>
          </p>
        </div>
        <div className="subscription-value">
          <strong>{money(period.price_cents)}</strong>
          <small>mensalidade · versão {period.version}</small>
        </div>
      </div>
      <div className="billing-metrics">
        <div>
          <Route size={19} />
          <small>Viagens utilizadas</small>
          <strong>
            {period.used_trips}
            <span> / {period.included_trips}</span>
          </strong>
        </div>
        <div>
          <Check size={19} />
          <small>Disponíveis na franquia</small>
          <strong>{period.remaining_trips}</strong>
        </div>
        <div>
          <Plus size={19} />
          <small>Viagens extras</small>
          <strong>{period.extra_trips}</strong>
        </div>
        <div>
          <Wallet size={19} />
          <small>Total do ciclo</small>
          <strong>{money(period.total_cents)}</strong>
        </div>
      </div>
      <div className="usage-bar-section">
        <div>
          <span>Franquia mensal</span>
          <span>
            {period.included_trips === 0
              ? "Cobrança por viagem extra"
              : `${period.used_trips} de ${period.included_trips} viagens`}
          </span>
        </div>
        <div
          className="usage-track"
          role="progressbar"
          aria-label="Uso da franquia mensal"
          aria-valuemin={0}
          aria-valuemax={Math.max(period.included_trips, 1)}
          aria-valuenow={Math.min(
            period.used_trips,
            Math.max(period.included_trips, 1),
          )}
        >
          <span
            style={{
              width: `${period.included_trips ? Math.min(100, (period.used_trips / period.included_trips) * 100) : 0}%`,
            }}
          />
        </div>
        <p>
          Viagem extra: {money(period.extra_trip_cents)} · Extras neste ciclo:{" "}
          {money(period.extras_cents)}
        </p>
      </div>
    </>
  );
}

function SubscriptionDetails({
  companyId,
  plans,
  report,
  isNexus,
}: {
  companyId: string;
  plans: Plan[];
  report: Report;
  isNexus: boolean;
}) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const sub = report.subscription;
  async function mutate(
    kind: "plan" | "cancel" | "unschedule",
    data: unknown = {},
  ) {
    if (
      kind === "cancel" &&
      !window.confirm(
        "Encerrar a assinatura desta empresa? Novas viagens serão bloqueadas e o histórico será preservado.",
      )
    )
      return;
    setPending(true);
    setError("");
    try {
      const base = `/nexus/companies/${companyId}/subscription`;
      if (kind === "plan") await patch(`${base}/plan`, data);
      else
        await post(
          kind === "cancel" ? `${base}/cancel` : `${base}/plan/cancel`,
          {},
        );
      await client.invalidateQueries({ queryKey: ["billing"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  if (!sub)
    return isNexus ? (
      <SubscribeForm companyId={companyId} plans={plans} />
    ) : (
      <div className="empty-state">
        <Layers3 size={34} />
        <h3>Sua empresa ainda não possui uma assinatura</h3>
        <p>Entre em contato com a Nexus para definir o plano da empresa.</p>
      </div>
    );
  return (
    <div className="subscription-details">
      <div className="subscription-status">
        <span
          className={`status-badge ${sub.status === "active" ? "active" : "inactive"}`}
        >
          {sub.status === "active"
            ? report.upcoming_period
              ? "Início agendado"
              : "Assinatura ativa"
            : "Assinatura encerrada"}
        </span>
        <small>
          Início: {dateOnly(sub.starts_on)} · ciclo mensal por aniversário
        </small>
      </div>
      {report.current_period ? (
        <PeriodSummary period={report.current_period} />
      ) : report.upcoming_period ? (
        <div className="billing-notice">
          <CalendarDays size={20} />
          <div>
            <strong>
              Início em {dateOnly(report.upcoming_period.starts_at)}
            </strong>
            <p>
              {report.upcoming_period.plan_name} ·{" "}
              {report.upcoming_period.included_trips} viagens/mês ·{" "}
              {money(report.upcoming_period.price_cents)}
            </p>
          </div>
        </div>
      ) : (
        <p className="muted">
          Consulte abaixo os ciclos anteriores da empresa.
        </p>
      )}
      {sub.pending_effective_at && (
        <div className="billing-notice">
          <Clock3 size={20} />
          <div>
            <strong>Próximo plano: {sub.pending_plan_name}</strong>
            <p>
              A partir de {dateOnly(sub.pending_effective_at)} ·{" "}
              {sub.pending_included_trips} viagens/mês ·{" "}
              {money(sub.pending_price_cents!)} · extra{" "}
              {money(sub.pending_extra_trip_cents!)}
            </p>
            {isNexus && (
              <button
                className="text-button"
                disabled={pending}
                onClick={() => mutate("unschedule")}
              >
                Cancelar alteração agendada
              </button>
            )}
          </div>
        </div>
      )}
      {error && <Alert>{error}</Alert>}
      {isNexus && sub.status === "active" && (
        <div className="subscription-controls">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              mutate(
                "plan",
                Object.fromEntries(new FormData(event.currentTarget)),
              );
            }}
          >
            <Field label="Plano para o próximo ciclo">
              <select name="plan_id" required defaultValue="">
                <option value="" disabled>
                  Selecione um plano
                </option>
                {plans
                  .filter((plan) => plan.is_active && plan.version_id)
                  .map((plan) => (
                    <option key={plan.id} value={plan.id}>
                      {plan.name} · {money(plan.price_cents!)}
                    </option>
                  ))}
              </select>
            </Field>
            <button
              className="button secondary"
              disabled={pending || !report.current_period}
            >
              Agendar alteração
            </button>
          </form>
          <button
            className="text-button danger-text"
            disabled={pending}
            onClick={() => mutate("cancel")}
          >
            Encerrar assinatura
          </button>
        </div>
      )}
      <section className="period-history">
        <h3>Demonstrativos mensais</h3>
        <p className="muted">
          Valores calculados por ciclo, com cobrança administrada pela Nexus.
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Ciclo</th>
                <th>Plano</th>
                <th>Viagens</th>
                <th>Extras</th>
                <th className="text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {report.periods.map((period) => (
                <tr key={period.id}>
                  <td>
                    {dateOnly(period.starts_at)} — {dateOnly(period.ends_at)}
                  </td>
                  <td>
                    {period.plan_name}
                    <small className="cell-note">Versão {period.version}</small>
                  </td>
                  <td>
                    {period.used_trips} / {period.included_trips}
                  </td>
                  <td>
                    {period.extra_trips} · {money(period.extras_cents)}
                  </td>
                  <td className="text-right">{money(period.total_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {isNexus && sub.status === "cancelled" && (
        <SubscribeForm companyId={companyId} plans={plans} />
      )}
    </div>
  );
}

export function Billing({
  isNexus,
  onLogout,
  initialCompanyId = "",
  companyOnly = false,
}: {
  isNexus: boolean;
  onLogout: () => void;
  initialCompanyId?: string;
  companyOnly?: boolean;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const [history, setHistory] = useState<Plan | null>(null);
  const [selectedCompany, setSelectedCompany] = useState(initialCompanyId);
  const [error, setError] = useState("");
  const [busyPlan, setBusyPlan] = useState("");
  const plans = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: () => api<Plan[]>("/nexus/plans"),
    enabled: isNexus,
  });
  const subscriptions = useQuery({
    queryKey: ["billing", "subscriptions"],
    queryFn: () => api<SubscriptionRow[]>("/nexus/subscriptions"),
    enabled: isNexus,
  });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => api<Company[]>("/nexus/companies"),
    enabled: isNexus,
  });
  const report = useQuery({
    queryKey: ["billing", "report", isNexus ? selectedCompany : "own"],
    queryFn: () =>
      api<Report>(
        isNexus
          ? `/nexus/companies/${selectedCompany}/subscription`
          : "/company/subscription",
      ),
    enabled: !isNexus || !!selectedCompany,
  });
  const queryError =
    plans.error || subscriptions.error || companies.error || report.error;
  useEffect(() => {
    if (queryError instanceof ApiError && queryError.status === 401) onLogout();
  }, [queryError, onLogout]);
  async function togglePlan(plan: Plan) {
    if (
      plan.is_active &&
      !window.confirm(
        `Arquivar o plano ${plan.name}? Isso bloqueará novas contratações desse plano.`,
      )
    )
      return;
    setBusyPlan(plan.id);
    setError("");
    try {
      await patch(`/nexus/plans/${plan.id}`, { is_active: !plan.is_active });
      await client.invalidateQueries({ queryKey: ["billing"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
    } catch (err) {
      setError(message(err));
    } finally {
      setBusyPlan("");
    }
  }
  return (
    <div className="billing-page">
      {(error || queryError) && <Alert>{error || message(queryError)}</Alert>}
      {isNexus && !companyOnly && (
        <>
          <div className="billing-heading">
            <div>
              <h2>Catálogo de planos</h2>
              <p className="muted">
                Franquia mensal e valores configuráveis para cada plano.
              </p>
            </div>
            <button
              className="button primary"
              onClick={() => setEditing("new")}
            >
              <Plus size={17} />
              Novo plano
            </button>
          </div>
          {plans.isPending ? (
            <div className="empty-state">Carregando planos…</div>
          ) : (
            <div className="plan-grid">
              {plans.data?.map((plan) => (
                <article
                  className="plan-card"
                  data-plan-code={plan.code}
                  key={plan.id}
                >
                  <header>
                    <span className="plan-icon">
                      <Layers3 size={22} />
                    </span>
                    <span
                      className={`status-badge ${plan.is_active ? "active" : "inactive"}`}
                    >
                      {!plan.version_id
                        ? "Configurar"
                        : plan.is_active
                          ? "Ativo"
                          : "Arquivado"}
                    </span>
                  </header>
                  <h3>{plan.name}</h3>
                  <div className="plan-price">
                    {plan.price_cents === null ? (
                      <strong className="unconfigured">
                        Valores não definidos
                      </strong>
                    ) : (
                      <>
                        <strong>{money(plan.price_cents)}</strong>
                        <span>/ mês</span>
                      </>
                    )}
                  </div>
                  <div className="plan-features">
                    <p>
                      <Route size={16} />
                      {plan.included_trips === null
                        ? "Defina a franquia mensal"
                        : `${plan.included_trips} viagens incluídas por mês`}
                    </p>
                    <p>
                      <Wallet size={16} />
                      {plan.extra_trip_cents === null
                        ? "Defina o valor da viagem extra"
                        : `${money(plan.extra_trip_cents)} por viagem extra`}
                    </p>
                  </div>
                  <button
                    className="button secondary full"
                    onClick={() => setEditing(plan)}
                  >
                    {plan.version_id ? "Editar condições" : "Configurar plano"}
                  </button>
                  {plan.version_id && (
                    <footer>
                      <button
                        className="text-button"
                        onClick={() => setHistory(plan)}
                        aria-label={`Ver histórico do plano ${plan.name}`}
                      >
                        <Clock3 size={14} />
                        Histórico · v{plan.version}
                      </button>
                      <button
                        className="text-button"
                        disabled={busyPlan === plan.id}
                        onClick={() => togglePlan(plan)}
                      >
                        {busyPlan === plan.id
                          ? "Aguarde…"
                          : plan.is_active
                            ? "Arquivar"
                            : "Ativar"}
                      </button>
                    </footer>
                  )}
                </article>
              ))}
            </div>
          )}
          <section className="panel subscription-directory">
            <header className="panel-header">
              <div>
                <h2>Assinaturas das empresas</h2>
                <p className="muted">
                  {subscriptions.data?.filter((sub) => sub.status === "active")
                    .length || 0}{" "}
                  assinaturas ativas
                </p>
              </div>
              <Building2 size={20} />
            </header>
            {subscriptions.isPending ? (
              <div className="empty-state">Carregando…</div>
            ) : subscriptions.data?.length === 0 ? (
              <div className="empty-state">
                <h3>Defina o plano da primeira empresa</h3>
                <p>
                  Selecione uma empresa abaixo para vincular sua assinatura.
                </p>
              </div>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Plano</th>
                      <th>Situação</th>
                      <th className="text-right">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptions.data?.map((sub) => (
                      <tr key={sub.id}>
                        <td>
                          <strong>{sub.company_name}</strong>
                          <small className="cell-note">
                            Início: {dateOnly(sub.starts_on)}
                          </small>
                        </td>
                        <td>
                          {sub.plan_name}
                          {sub.pending_plan_name && (
                            <small className="cell-note">
                              Próximo: {sub.pending_plan_name}
                            </small>
                          )}
                        </td>
                        <td>
                          <span
                            className={`status-badge ${sub.status === "active" ? "active" : "inactive"}`}
                          >
                            {sub.status === "active" ? "Ativa" : "Encerrada"}
                          </span>
                        </td>
                        <td className="text-right">
                          <button
                            className="text-button"
                            onClick={() => {
                              setSelectedCompany(sub.company_id);
                              document
                                .getElementById("subscription-report")
                                ?.scrollIntoView({ block: "start" });
                            }}
                          >
                            Ver assinatura
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      <section className="panel" id="subscription-report">
        <header className="panel-header">
          <div>
            <h2>
              {isNexus && !companyOnly
                ? "Assinatura e consumo"
                : "Plano e consumo da empresa"}
            </h2>
            <p className="muted">
              Franquia por viagem, com vários veículos na mesma operação.
            </p>
          </div>
          {isNexus && (
            <select
              className="company-select"
              aria-label="Empresa da assinatura"
              value={selectedCompany}
              onChange={(event) => setSelectedCompany(event.target.value)}
            >
              <option value="">Selecione uma empresa</option>
              {companies.data?.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.trade_name} ({company.slug})
                </option>
              ))}
            </select>
          )}
        </header>
        {isNexus && !selectedCompany ? (
          <div className="empty-state">
            <CalendarDays size={30} />
            <p>Selecione a empresa para consultar ou definir sua assinatura.</p>
          </div>
        ) : report.isPending ? (
          <div className="empty-state">Carregando demonstrativo…</div>
        ) : (
          report.data && (
            <SubscriptionDetails
              key={selectedCompany || "own"}
              companyId={selectedCompany}
              plans={plans.data || []}
              report={report.data}
              isNexus={isNexus}
            />
          )
        )}
      </section>
      {editing && (
        <PlanEditor
          plan={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      {history && (
        <PlanHistory plan={history} onClose={() => setHistory(null)} />
      )}
    </div>
  );
}
