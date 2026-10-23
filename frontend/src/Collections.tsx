import { DataUseNotice } from "./components/DataUseNotice";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import QRCode from "qrcode";
import { BillingUpcoming } from "./BillingUpcoming";
import { moneyInput, parseMoney } from "./billing/types";

type Settings = {
  version: number;
  enabled: boolean;
  pix_key: string;
  pix_copy_paste?: string;
  receiver_name: string;
  nexus_session_id: string | null;
  infinitepay_enabled?: boolean;
  infinitepay_handle?: string;
  setup_cents?: number;
  trial_days?: number;
};
type Invoice = {
  invoice_kind?: "subscription" | "setup";
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
  pix_copy_paste?: string;
  receiver_name: string;
  paid_at: string | null;
  confirmed_at: string | null;
  payment_note: string;
  payment_provider?: string;
  payment_url?: string;
  payment_error?: string | null;
  setup_cents?: number;
  receipt_url?: string;
  transaction_nsu?: string | null;
  extras_starts_at?: string | null;
  extras_ends_at?: string | null;
};
const money = (n: number) =>
  (n / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const date = (s: string) =>
  new Date(s).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
const due = (s: string) => s.split("-").reverse().join("/");
const noticeErrors: Record<string, string> = {
  billing_terms_changed:
    "Aviso substituído pela regra de setup separado e mensalidade após 30 dias.",
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

function BillingDeliveryTests() {
  const cache = useQueryClient();
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [queued, setQueued] = useState(false);
  const keys = useRef<Record<string, string>>({});
  const results = useQuery({
    queryKey: ["billing-delivery-tests"],
    queryFn: () =>
      api<
        {
          id: string;
          kind: string;
          channel: string;
          recipient: string;
          status: string;
          error_code: string | null;
          created_at: string;
        }[]
      >("/nexus/billing/notifications"),
    refetchInterval: 5000,
  });
  async function send(channel: "email" | "whatsapp") {
    setBusy(true);
    setError("");
    setQueued(false);
    keys.current[channel] ||= crypto.randomUUID();
    try {
      await api("/nexus/billing/test-delivery", {
        method: "POST",
        body: JSON.stringify({
          channel,
          recipient: channel === "email" ? email : phone,
          operation_key: keys.current[channel],
        }),
      });
      delete keys.current[channel];
      setQueued(true);
      await cache.invalidateQueries({ queryKey: ["billing-delivery-tests"] });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Falha ao solicitar teste.",
      );
    } finally {
      setBusy(false);
    }
  }
  const labels: Record<string, string> = {
    pending: "Aguardando envio",
    sending: "Enviando",
    sent: "Aceito pelo serviço",
    failed: "Falha",
    uncertain:
      "Envio incerto — confira o recebimento antes de testar novamente",
    discarded: "Descartado",
  };
  return (
    <section className="operation-card modal-form">
      <h3>Testar envio de cobrança</h3>
      <p>
        Utiliza a configuração salva de e-mail e o WhatsApp de cobrança da
        Nexus, mesmo com a cobrança automática desativada. Salve as alterações
        antes de testar. Usa o modelo real com valores ilustrativos, link ou QR
        Code conforme a configuração e aviso de NÃO PAGAR. Não cria cobrança nem
        altera assinaturas.
      </p>
      <div className="pix-preview-field">
        <Field label="E-mail para teste de cobrança">
          <input
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              delete keys.current.email;
            }}
          />
        </Field>
        <button
          type="button"
          className="button secondary"
          disabled={busy || !email.trim()}
          onClick={() => void send("email")}
        >
          Testar e-mail de cobrança
        </button>
      </div>
      <div className="pix-preview-field">
        <Field label="WhatsApp para teste de cobrança">
          <input
            type="tel"
            placeholder="+55 47 99999-9999"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
              delete keys.current.whatsapp;
            }}
          />
        </Field>
        <button
          type="button"
          className="button secondary"
          disabled={busy || !phone.trim()}
          onClick={() => void send("whatsapp")}
        >
          Testar WhatsApp de cobrança
        </button>
      </div>
      {queued && (
        <p role="status">
          Teste solicitado. O resultado será atualizado automaticamente abaixo.
        </p>
      )}
      {(error || results.error) && (
        <Alert>{error || results.error?.message}</Alert>
      )}
      <small className="muted">
        Aceito pelo serviço não confirma entrega ou leitura. Confira o
        destinatário informado.
      </small>
      {results.data
        ?.filter((n) => n.kind === "test")
        .slice(0, 10)
        .map((n) => (
          <p key={n.id}>
            {n.channel === "email" ? "E-mail" : "WhatsApp"} · {n.recipient} ·{" "}
            {labels[n.status] || n.status}
            <br />
            <small>
              {new Date(n.created_at).toLocaleString("pt-BR", {
                timeZone: "America/Sao_Paulo",
              })}
              {n.error_code &&
                ` · ${noticeErrors[n.error_code] || "Falha no serviço. Confira a configuração."}`}
            </small>
          </p>
        ))}
    </section>
  );
}

export function CollectionSettings() {
  const [preview, setPreview] = useState<{
    image: string;
    payload: string;
    key: string;
    source: string;
  } | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  async function showPix(fromCopy: boolean) {
    setPreviewBusy(true);
    setError("");
    try {
      const result = await api<{ payload: string; key: string }>(
        "/nexus/billing/pix-preview",
        {
          method: "POST",
          body: JSON.stringify({
            pix_key: values.pix_key,
            receiver_name: values.receiver_name,
            pix_copy_paste: values.pix_copy_paste,
            from_copy_paste: fromCopy,
          }),
        },
      );
      const image = await QRCode.toDataURL(result.payload, {
        width: 360,
        margin: 4,
        errorCorrectionLevel: "M",
      });
      setPreview({
        ...result,
        image,
        source: fromCopy ? "Pix Copia e Cola" : "Chave Pix",
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível gerar o QR Code.",
      );
    } finally {
      setPreviewBusy(false);
    }
  }
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
    pix_copy_paste: "",
    receiver_name: "",
    nexus_session_id: "",
    infinitepay_enabled: false,
    infinitepay_handle: "",
    setup_value: "0,00",
    trial_days: 7,
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    if (query.data)
      setValues({
        enabled: query.data.enabled ?? false,
        pix_key: query.data.pix_key ?? "",
        pix_copy_paste: query.data.pix_copy_paste ?? "",
        receiver_name: query.data.receiver_name ?? "",
        nexus_session_id: query.data.nexus_session_id ?? "",
        infinitepay_enabled: query.data.infinitepay_enabled ?? false,
        infinitepay_handle: query.data.infinitepay_handle ?? "",
        setup_value: moneyInput(query.data.setup_cents ?? 0),
        trial_days: query.data.trial_days ?? 7,
      });
  }, [query.data?.version]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const { setup_value, ...configuration } = values;
      await api("/nexus/billing/settings", {
        method: "PUT",
        body: JSON.stringify({
          ...configuration,
          setup_cents: parseMoney(setup_value),
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
    <>
      <form className="operation-card modal-form" onSubmit={save}>
        <DataUseNotice />
        <h2>Cobrança e período de teste</h2>
        <p>
          Configure a cobrança das empresas assinantes. As condições de setup e
          teste serão aplicadas às novas contratações.
        </p>
        <fieldset className="operation-card package-route-card">
          <legend>Pagamento automático · InfinitePay</legend>
          <label className="operation-checkbox">
            <input
              type="checkbox"
              checked={values.infinitepay_enabled}
              onChange={(e) => {
                setSaved(false);
                setValues({ ...values, infinitepay_enabled: e.target.checked });
              }}
            />
            Usar InfinitePay nas novas cobranças
          </label>
          <div className="form-grid">
            <Field label="Identificador InfinitePay (InfiniteTag)">
              <input
                value={values.infinitepay_handle}
                required={values.infinitepay_enabled}
                maxLength={101}
                placeholder="sua-tag (sem $)"
                onChange={(e) => {
                  setSaved(false);
                  setValues({ ...values, infinitepay_handle: e.target.value });
                }}
              />
            </Field>
            <Field label="Taxa de setup (R$)">
              <input
                required
                inputMode="decimal"
                value={values.setup_value}
                onChange={(e) => {
                  setSaved(false);
                  setValues({ ...values, setup_value: e.target.value });
                }}
              />
            </Field>
            <Field label="Prazo de teste (dias)">
              <input
                required
                type="number"
                min={0}
                max={365}
                value={values.trial_days}
                onChange={(e) => {
                  setSaved(false);
                  setValues({ ...values, trial_days: Number(e.target.value) });
                }}
              />
            </Field>
          </div>
          <p className="muted">
            Contratação em 10/10 com 7 dias de teste: somente setup em 17/10. A
            primeira mensalidade e seus excedentes são cobrados em 16/11, após
            30 dias de uso, por e-mail e WhatsApp. A franquia começa em 17/10 e
            se renova a cada 30 dias. Durante o teste não há cobrança de
            excedentes; a utilização respeita a franquia do plano.
          </p>
          <p className="muted">
            Nos novos contratos: ciclos de 30 dias, com mensalidade e excedentes
            do próprio período cobrados no fechamento. A confirmação dos
            pagamentos é automática. Contratos anteriores mantêm seus ciclos;
            cobranças já emitidas não são alteradas.
          </p>
          <p className="muted">
            Contratos antecipados existentes continuam nesse modelo. Para pausar
            novas cobranças e envios, desative a automação geral abaixo.
          </p>
        </fieldset>
        <details open={!values.infinitepay_enabled}>
          <summary>Pix manual · configuração para cobranças manuais</summary>
          <div className="pix-preview-field">
            <Field label="Chave Pix da Nexus">
              <input
                required={values.enabled && !values.infinitepay_enabled}
                maxLength={140}
                value={values.pix_key}
                onChange={(e) => {
                  setSaved(false);
                  setValues({ ...values, pix_key: e.target.value });
                }}
              />
            </Field>
            <button
              type="button"
              className="button secondary"
              disabled={previewBusy || !values.pix_key.trim()}
              onClick={() => void showPix(false)}
            >
              Ver QR Code da chave Pix
            </button>
          </div>
          <div className="pix-preview-field">
            <Field label="Pix Copia e Cola sem valor definido (opcional)">
              <textarea
                rows={4}
                maxLength={1024}
                value={values.pix_copy_paste}
                onChange={(e) => {
                  setSaved(false);
                  setValues({ ...values, pix_copy_paste: e.target.value });
                }}
                placeholder="Cole o código completo gerado pelo seu banco"
              />
            </Field>
            <button
              type="button"
              className="button secondary"
              disabled={previewBusy || !values.pix_copy_paste.trim()}
              onClick={() => void showPix(true)}
            >
              Ver QR Code do Copia e Cola
            </button>
          </div>
          {preview && (
            <Modal
              title={`QR Code · ${preview.source}`}
              onClose={() => setPreview(null)}
            >
              <div className="modal-form">
                <p>
                  Leia com o aplicativo do banco e confira a chave e o
                  favorecido. QR Code sem valor definido.
                </p>
                <img
                  src={preview.image}
                  alt="QR Code Pix para conferência"
                  width={360}
                  height={360}
                  style={{
                    maxWidth: "100%",
                    height: "auto",
                    alignSelf: "center",
                  }}
                />
                <p>
                  Chave Pix: <strong>{preview.key}</strong>
                </p>
                <Field label="Pix Copia e Cola do QR Code">
                  <textarea rows={4} value={preview.payload} readOnly />
                </Field>
                <p className="muted">
                  A visualização usa os campos preenchidos, sem salvar
                  alterações nem consultar sua conta bancária.
                </p>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setPreview(null)}
                >
                  Fechar QR Code
                </button>
              </div>
            </Modal>
          )}
          <p className="muted">
            Utilize um código estático, sem valor, da mesma chave Pix acima. O
            código será incluído no e-mail, no WhatsApp e no demonstrativo das
            novas cobranças. A cobrança definitiva também envia o QR Code no
            e-mail e como imagem no WhatsApp. Sem Copia e Cola, o QR é gerado a
            partir da chave e do favorecido. O cliente informa o total no banco.
          </p>
          <Field label="Nome do favorecido do Pix">
            <input
              required={values.enabled && !values.infinitepay_enabled}
              maxLength={150}
              value={values.receiver_name}
              onChange={(e) => {
                setSaved(false);
                setValues({ ...values, receiver_name: e.target.value });
              }}
            />
          </Field>
        </details>
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
      <BillingDeliveryTests />
    </>
  );
}

function PaymentEvents() {
  const events = useQuery({
    queryKey: ["payment-events"],
    queryFn: () =>
      api<
        Array<{
          id: string;
          company_name: string;
          transaction_nsu: string;
          status: string;
          attempts: number;
          error_code: string | null;
        }>
      >("/nexus/billing/payment-events"),
    refetchInterval: 30000,
  });
  return (
    <section className="operation-card modal-form">
      <h3>Confirmações automáticas de pagamento</h3>
      {events.error && <Alert>{events.error.message}</Alert>}
      {!events.data?.length && <p>Nenhuma confirmação recebida.</p>}
      {events.data?.map((e) => (
        <p key={e.id}>
          <strong>{e.company_name}</strong> ·{" "}
          {
            (
              {
                pending: "Aguardando verificação",
                verifying: "Conferindo pagamento",
                verified: "Confirmado",
                rejected: "Não confirmado",
                review: "Requer conferência da Nexus",
              } as Record<string, string>
            )[e.status]
          }{" "}
          · {e.attempts} tentativa(s)
          <br />
          <small>Transação: {e.transaction_nsu}</small>
        </p>
      ))}
    </section>
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
          invoice_id: string | null;
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
  async function retryLink(i: Invoice) {
    setBusy(true);
    setError("");
    try {
      await api(nexus ? `/nexus/billing/invoices/${i.id}/retry-checkout` : `/company/invoices/${i.id}/payment-link`, {
        method: "POST",
      });
      await cache.invalidateQueries({ queryKey: ["collection-invoices"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao solicitar o link.");
    } finally {
      setBusy(false);
    }
  }
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
          Consulte setup, mensalidades e excedentes. Cobranças com link de
          pagamento têm confirmação automática; pagamentos manuais dependem da
          conferência da Nexus.
        </p>
        {!nexus && <BillingUpcoming />}
        {blocked && (
          <Alert>
            Há cobrança vencida aguardando confirmação. Regularize a fatura pendente para liberar o acesso. Motorista e guia mantêm acesso às viagens já vendidas.
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
        .sort((a, b) => blocked ? Number(b.overdue) - Number(a.overdue) : 0)
        .map((i) => (
          <article
            className="operation-card package-route-card modal-form"
            key={i.id}
          >
            <h3>
              {i.company_name || "Sua empresa"} · {i.plan_name}
              {i.invoice_kind === "setup" && " · Setup"}
            </h3>
            <p>
              {i.invoice_kind === "setup"
                ? `Setup em ${date(i.starts_at)}`
                : `${date(i.starts_at)} até ${date(i.ends_at)} (fim exclusivo)`}{" "}
              ·{" "}
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
            {i.invoice_kind !== "setup" && (
              <p>
                Mensalidade: <strong>{money(i.price_cents)}</strong> · Franquia:{" "}
                {i.included_trips} · Utilizadas: {i.used_trips}
              </p>
            )}
            {i.invoice_kind !== "setup" && (
              <p>
                Excedentes: {i.extra_trips} × {money(i.extra_trip_cents)}
              </p>
            )}
            {!!i.setup_cents && (
              <p>
                Setup (cobrança única): <strong>{money(i.setup_cents)}</strong>
              </p>
            )}
            {i.extras_starts_at && i.extras_ends_at && (
              <p>
                Excedentes referentes ao período de {date(i.extras_starts_at)}{" "}
                até {date(i.extras_ends_at)}.
              </p>
            )}
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
            {i.status === "open" && i.payment_provider === "infinitepay" && (
              <div className="reservation-suggestion">
                {i.payment_error === "payment_requires_review" ? (
                  <p>
                    Pagamento em conferência. Aguarde a orientação da Nexus
                    antes de pagar novamente.
                  </p>
                ) : i.payment_url ? (
                  <>
                    <a
                      className="button primary"
                      href={i.payment_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Pagar agora
                    </a>
                    <p>
                      O pagamento será confirmado automaticamente após
                      aprovação.
                    </p>
                  </>
                ) : (
                  <p>
                    {i.payment_error
                      ? "Link de pagamento indisponível no momento. A Nexus pode consultar a situação desta cobrança."
                      : "Preparando link de pagamento. Esta tela será atualizada automaticamente."}
                  </p>
                )}
                {!i.payment_url && i.payment_error !== "payment_requires_review" && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void retryLink(i)}
                  >
                    {nexus ? "Tentar gerar link novamente" : "Gerar link para pagamento"}
                  </button>
                )}
              </div>
            )}
            {i.payment_error === "payment_requires_review" && (
              <Alert>
                Pagamento recebido com divergência ou após baixa/cancelamento. A
                conferência da Nexus é necessária.
              </Alert>
            )}
            {i.status === "open" && i.payment_provider !== "infinitepay" && (
              <>
                <p>
                  Pix: <strong>{i.pix_key}</strong>
                  <br />
                  Favorecido: {i.receiver_name}
                </p>
                {i.pix_copy_paste && (
                  <Field label="Pix Copia e Cola desta cobrança">
                    <textarea rows={4} value={i.pix_copy_paste} readOnly />
                    <small>
                      Copie o código e informe no banco o valor total da
                      cobrança.
                    </small>
                  </Field>
                )}
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
            {i.receipt_url && (
              <p>
                <a
                  href={i.receipt_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Consultar comprovante
                </a>
              </p>
            )}
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
                    {i.payment_provider === "infinitepay"
                      ? "Baixa manual excepcional"
                      : "Confirmar recebimento do Pix"}
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
                    test: "Teste de cobrança",
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
              {n.invoice_id && <small>Cobrança: {n.invoice_id}</small>}
            </p>
          ))}
        </section>
      )}
      {nexus && <PaymentEvents />}
      {selected && (
        <Modal
          title="Confirmar recebimento do Pix"
          onClose={() => !busy && setSelected(null)}
        >
          <form className="modal-form" onSubmit={pay}>
            <DataUseNotice />
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
