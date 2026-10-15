import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field, Modal } from "./components/ui";

type Settings = {
  version: number;
  enabled: boolean;
  pix_key: string;
  receiver_name: string;
  nexus_session_id: string | null;
};
type Invoice = {
  id: string;
  company_name?: string;
  plan_name: string;
  starts_at: string;
  ends_at: string;
  status: string;
  overdue: boolean;
  price_cents: number;
  extra_trip_cents: number;
  extra_trips: number;
  included_trips: number;
  used_trips: number;
  total_cents: number;
  due_on: string;
  pix_key: string;
  receiver_name: string;
  paid_at: string | null;
  confirmed_at: string | null;
  payment_note: string;
};
const money = (n: number) =>
  (n / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const date = (s: string) =>
  new Date(s).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
const due = (s: string) => s.split("-").reverse().join("/");
const noticeErrors: Record<string, string> = {
  whatsapp_precheck_failed:
    "Confira a conexão do WhatsApp da Nexus e o telefone da empresa.",
  email_configuration_unavailable:
    "Confira o remetente e a configuração de e-mail da Nexus.",
  email_provider_error: "O serviço de e-mail recusou ou não confirmou o envio.",
  protection_unavailable:
    "A proteção das mensagens está indisponível. Solicite suporte.",
  decryption_failed:
    "Não foi possível abrir a mensagem protegida. Solicite suporte.",
  send_timeout: "O serviço de WhatsApp não respondeu ao envio dentro do prazo.",
  connection_error:
    "A conexão falhou durante o envio; confira o recebimento antes de repetir.",
  tls_error: "Falha na conexão segura com o serviço de mensagens.",
  invalid_response: "Não foi possível ler a confirmação do serviço.",
  unrecognized_response: "A resposta do serviço não confirmou a aceitação.",
  worker_interrupted:
    "O processamento foi interrompido antes de registrar o resultado.",
  http_401: "A chave de acesso ao WhatsApp foi recusada.",
  http_403: "A chave de acesso não permite este envio.",
  http_429: "O serviço limitou os envios. Aguarde a próxima tentativa.",
};

export function CollectionSettings() {
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ["collection-settings"],
    queryFn: () => api<Settings>("/nexus/billing/settings"),
  });
  const sessions = useQuery({
    queryKey: ["integration-sessions"],
    queryFn: () =>
      api<{ id: string; name: string; status: string }[]>(
        "/nexus/integrations/sessions",
      ),
    enabled: false,
    retry: false,
  });
  const [values, setValues] = useState({
    enabled: false,
    pix_key: "",
    receiver_name: "",
    nexus_session_id: "",
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    if (query.data)
      setValues({
        enabled: query.data.enabled ?? false,
        pix_key: query.data.pix_key ?? "",
        receiver_name: query.data.receiver_name ?? "",
        nexus_session_id: query.data.nexus_session_id ?? "",
      });
  }, [query.data?.version]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/nexus/billing/settings", {
        method: "PUT",
        body: JSON.stringify({
          ...values,
          nexus_session_id: values.nexus_session_id || null,
          expected_version: query.data?.version,
        }),
      });
      await cache.invalidateQueries({ queryKey: ["collection-settings"] });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    } finally {
      setBusy(false);
    }
  }
  if (query.isPending) return <p>Carregando configuração financeira…</p>;
  if (query.error) return <Alert>{query.error.message}</Alert>;
  return (
    <form className="operation-card modal-form" onSubmit={save}>
      <h2>Cobrança mensal da Nexus · Pix manual</h2>
      <p>
        Configure os dados que serão enviados às empresas. O recebimento do Pix
        precisa ser confirmado pelo superadmin em Financeiro e cobranças.
      </p>
      <Field label="Chave Pix da Nexus">
        <input
          required={values.enabled}
          maxLength={140}
          value={values.pix_key}
          onChange={(e) => {
            setSaved(false);
            setValues({ ...values, pix_key: e.target.value });
          }}
        />
      </Field>
      <Field label="Nome do favorecido do Pix">
        <input
          required={values.enabled}
          maxLength={150}
          value={values.receiver_name}
          onChange={(e) => {
            setSaved(false);
            setValues({ ...values, receiver_name: e.target.value });
          }}
        />
      </Field>
      <Field label="ID da sessão WhatsApp de cobrança da Nexus">
        <input
          required={values.enabled}
          value={values.nexus_session_id}
          pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
          onChange={(e) => {
            setSaved(false);
            setValues({ ...values, nexus_session_id: e.target.value });
          }}
        />
      </Field>
      <button
        type="button"
        className="button secondary"
        disabled={sessions.isFetching}
        onClick={() => void sessions.refetch()}
      >
        Listar sessões de envio da Nexus
      </button>
      {sessions.error && <Alert>{sessions.error.message}</Alert>}
      {!!sessions.data?.length && (
        <Field label="Selecionar sessão da Nexus">
          <select
            value={values.nexus_session_id}
            onChange={(e) => {
              setSaved(false);
              setValues({ ...values, nexus_session_id: e.target.value });
            }}
          >
            <option value="">Escolha o número de envio</option>
            {sessions.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.status} · {s.id}
              </option>
            ))}
          </select>
        </Field>
      )}
      <label className="operation-checkbox">
        <input
          type="checkbox"
          checked={values.enabled}
          onChange={(e) => {
            setSaved(false);
            setValues({ ...values, enabled: e.target.checked });
          }}
        />
        Ativar avisos e cobranças mensais automáticas
      </label>
      <p className="muted">
        Aviso parcial um dia antes do fechamento; cobrança definitiva no
        fechamento. Prazo de dois dias úteis a partir do dia seguinte, no
        horário de Brasília, excluindo fins de semana e feriados do calendário
        nacional, incluindo Sexta-feira da Paixão. Não inclui pontos
        facultativos nem feriados estaduais e municipais.
      </p>
      <p className="muted">
        A ativação considera os ciclos que fecharem depois dela, sem cobrar
        ciclos antigos retroativamente. Desativar pausa os envios e novos
        fechamentos; não cancela cobranças já abertas. Alterar o Pix não
        reescreve cobranças fechadas.
      </p>
      {error && <Alert>{error}</Alert>}
      {saved && <p role="status">Configuração financeira salva.</p>}
      <button className="button primary" disabled={busy}>
        Salvar configuração de cobrança
      </button>
    </form>
  );
}

export function Collections({ nexus }: { nexus: boolean }) {
  const cache = useQueryClient();
  const query = useQuery<Invoice[] | { blocked: boolean; invoices: Invoice[] }>(
    {
      queryKey: ["collection-invoices", nexus],
      queryFn: () =>
        nexus
          ? api<Invoice[]>("/nexus/billing/invoices")
          : api<{ blocked: boolean; invoices: Invoice[] }>("/company/invoices"),
      refetchInterval: 30000,
    },
  );
  const notifications = useQuery({
    queryKey: ["collection-notifications"],
    queryFn: () =>
      api<
        {
          id: string;
          invoice_id: string;
          company_name: string;
          kind: string;
          channel: string;
          status: string;
          error_code: string | null;
        }[]
      >("/nexus/billing/notifications"),
    enabled: nexus,
    refetchInterval: 30000,
  });
  const [selected, setSelected] = useState<Invoice | null>(null),
    [filter, setFilter] = useState("all"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const data = query.data;
  const rows = Array.isArray(data) ? data : data?.invoices || [];
  const blocked = !Array.isArray(data) && data?.blocked;
  async function pay(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      await api(`/nexus/billing/invoices/${selected.id}/paid`, {
        method: "POST",
        body: JSON.stringify({
          paid_at: new Date(String(form.get("paid_at"))).toISOString(),
          note: form.get("note"),
        }),
      });
      setSelected(null);
      await cache.invalidateQueries({ queryKey: ["collection-invoices"] });
      await cache.invalidateQueries({ queryKey: ["collection-notifications"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha na confirmação.");
    } finally {
      setBusy(false);
    }
  }
  async function cancel(i: Invoice) {
    if (
      !window.confirm(
        "Cancelar esta cobrança? Ela deixará de restringir a empresa. O histórico será preservado.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`/nexus/billing/invoices/${i.id}/cancel`, { method: "POST" });
      await cache.invalidateQueries({ queryKey: ["collection-invoices"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao cancelar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="reservation-workspace">
      <section className="operation-card modal-form">
        <h2>{nexus ? "Financeiro e cobranças" : "Financeiro da empresa"}</h2>
        <p>
          Mensalidade e excedentes consolidados por ciclo. A confirmação do Pix
          é manual pela Nexus.
        </p>
        {blocked && (
          <Alert>
            Há cobrança vencida aguardando confirmação. Novas operações estão
            bloqueadas. Consultas e operação das viagens já vendidas permanecem
            disponíveis.
          </Alert>
        )}
        <Field label="Situação da cobrança">
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">Todas</option>
            <option value="preview">Aviso parcial</option>
            <option value="open">Abertas</option>
            <option value="overdue">Vencidas</option>
            <option value="paid">Pagas</option>
            <option value="cancelled">Canceladas</option>
          </select>
        </Field>
        {(query.error || error) && (
          <Alert>{error || query.error?.message}</Alert>
        )}
        {query.isPending && <p>Carregando cobranças…</p>}
        {!query.isPending && rows.length === 0 && (
          <p>
            Nenhuma cobrança gerada. Os ciclos são processados automaticamente
            após a ativação pela Nexus.
          </p>
        )}
      </section>
      {rows
        .filter(
          (i) =>
            filter === "all" ||
            (filter === "overdue" ? i.overdue : i.status === filter),
        )
        .map((i) => (
          <article
            className="operation-card package-route-card modal-form"
            key={i.id}
          >
            <h3>
              {i.company_name || "Sua empresa"} · {i.plan_name}
            </h3>
            <p>
              {date(i.starts_at)} até {date(i.ends_at)} (fim exclusivo) ·{" "}
              {
                (
                  {
                    preview: "Valor parcial",
                    open: "Aberta",
                    paid: "Paga",
                    cancelled: "Cancelada",
                  } as Record<string, string>
                )[i.status]
              }
              {i.overdue && " · Vencida"}
            </p>
            <p>
              Mensalidade: <strong>{money(i.price_cents)}</strong> · Franquia:{" "}
              {i.included_trips} · Utilizadas: {i.used_trips}
            </p>
            <p>
              Excedentes: {i.extra_trips} × {money(i.extra_trip_cents)}
            </p>
            <p>
              Total: <strong>{money(i.total_cents)}</strong> · Confirmação até{" "}
              <strong>{due(i.due_on)}</strong>
            </p>
            {i.status === "preview" && (
              <p>
                O valor pode mudar até o fechamento do ciclo. Aguarde a cobrança
                definitiva.
              </p>
            )}
            {i.status === "open" && (
              <>
                <p>
                  Pix: <strong>{i.pix_key}</strong>
                  <br />
                  Favorecido: {i.receiver_name}
                </p>
                <p>
                  A baixa depende da conferência da Nexus. O envio do Pix não
                  libera automaticamente a conta.
                </p>
              </>
            )}
            {i.paid_at && (
              <p>
                Recebimento em {new Date(i.paid_at).toLocaleString("pt-BR")} ·
                confirmado em{" "}
                {i.confirmed_at &&
                  new Date(i.confirmed_at).toLocaleString("pt-BR")}
              </p>
            )}
            {nexus && i.payment_note && <p>Observação: {i.payment_note}</p>}
            <small>Referência: {i.id}</small>
            {nexus && (
              <div className="modal-actions">
                {i.status === "open" && (
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() => {
                      setError("");
                      setSelected(i);
                    }}
                  >
                    Confirmar recebimento do Pix
                  </button>
                )}
                {["preview", "open"].includes(i.status) && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void cancel(i)}
                  >
                    Cancelar cobrança
                  </button>
                )}
              </div>
            )}
          </article>
        ))}
      {nexus && (
        <section className="operation-card modal-form">
          <h3>Histórico dos envios financeiros</h3>
          {notifications.error && <Alert>{notifications.error.message}</Alert>}
          {notifications.data?.length === 0 && <p>Nenhum envio registrado.</p>}
          {notifications.data?.map((n) => (
            <p key={n.id}>
              {n.company_name} ·{" "}
              {
                (
                  {
                    preview: "Aviso prévio",
                    invoice: "Cobrança",
                    blocked: "Bloqueio",
                    paid: "Pagamento confirmado",
                  } as Record<string, string>
                )[n.kind]
              }{" "}
              · {n.channel === "email" ? "E-mail" : "WhatsApp"} ·{" "}
              {
                (
                  {
                    pending: "Aguardando envio",
                    sending: "Enviando",
                    sent: "Aceito pelo serviço",
                    uncertain: "Envio incerto — confira antes de reenviar",
                    failed: "Falha",
                    discarded: "Descartado",
                  } as Record<string, string>
                )[n.status]
              }
              {n.error_code &&
                ` · ${noticeErrors[n.error_code] || "O serviço retornou uma falha. Solicite suporte."}`}
              <br />
              <small>Cobrança: {n.invoice_id}</small>
            </p>
          ))}
        </section>
      )}
      {selected && (
        <Modal
          title="Confirmar recebimento do Pix"
          onClose={() => !busy && setSelected(null)}
        >
          <form className="modal-form" onSubmit={pay}>
            <p>
              Confirme o recebimento integral de{" "}
              <strong>{money(selected.total_cents)}</strong> para{" "}
              {selected.company_name}. A baixa será registrada com seu usuário.
            </p>
            <Field label="Data e hora do recebimento">
              <input name="paid_at" type="datetime-local" required />
            </Field>
            <Field label="Observação ou referência do Pix">
              <input name="note" maxLength={500} />
            </Field>
            {error && <Alert>{error}</Alert>}
            <button className="button primary" disabled={busy}>
              Confirmar pagamento integral
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
