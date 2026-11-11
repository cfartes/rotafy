import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";
import { PasswordInput } from "./components/PasswordInput";

type Config = {
  enabled: boolean;
  daily_limit: number;
  version: number;
  key_configured: boolean;
  captcha_configured: boolean;
};
type Lead = {
  id: string;
  company_name: string;
  name: string;
  phone: string;
  marketing_consent: boolean;
  created_at: string;
  source: string;
  campaign: Record<string, string>;
  city: string;
  state: string;
  browser: string;
  os: string;
  language: string;
  timezone: string;
  status: string;
  stage: string;
  error_code: string | null;
};
const stages: Record<string, string> = {
  new: "Novo",
  contacted: "Contatado",
  interested: "Interessado",
  converted: "Convertido",
};
const deliveries: Record<string, string> = {
  pending: "Na fila",
  sending: "Enviando",
  sent: "Aceito pelo serviço",
  failed: "Falhou",
  uncertain: "Envio incerto — confira antes de reenviar",
  expired: "Expirado",
};
export function DemoLeads() {
  const cache = useQueryClient();
  const [page, setPage] = useState(1),
    [stage, setStage] = useState(""),
    [marketing, setMarketing] = useState("");
  const [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [secret, setSecret] = useState(""),
    [siteKey, setSiteKey] = useState(""),
    [busy, setBusy] = useState(false);
  const config = useQuery({
    queryKey: ["demo-settings"],
    queryFn: () => api<Config>("/nexus/demo-settings"),
  });
  const leads = useQuery({
    queryKey: ["demo-leads", page, stage, marketing],
    queryFn: () =>
      api<{ items: Lead[]; total: number }>(
        `/nexus/demo-leads?page=${page}${stage ? `&stage=${stage}` : ""}${marketing ? `&marketing=${marketing}` : ""}`,
      ),
  });
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!config.data) return;
    const form = new FormData(e.currentTarget);
    const captcha = String(form.get("demo_captcha_secret") || "").trim();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api<Config>("/nexus/demo-settings", {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: config.data.version,
          enabled: form.get("enabled") === "on",
          daily_limit: Number(form.get("limit")),
          ...(captcha ? { captcha_secret: captcha } : {}),
        }),
      });
      cache.setQueryData(["demo-settings"], updated);
      setSecret("");
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar.");
    } finally {
      setBusy(false);
    }
  }
  async function rotate() {
    if (
      !window.confirm(
        "Gerar uma nova credencial? A integração do site precisará ser atualizada e a credencial anterior deixará de funcionar.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ site_key: string }>(
        "/nexus/demo-settings/rotate-key",
        { method: "POST" },
      );
      setSiteKey(result.site_key);
      await cache.invalidateQueries({ queryKey: ["demo-settings"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gerar credencial.");
    } finally {
      setBusy(false);
    }
  }
  async function update(lead: Lead, value: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/nexus/demo-leads/${lead.id}`, {
        method: "PATCH",
        body: JSON.stringify({ stage: value }),
      });
      await cache.invalidateQueries({ queryKey: ["demo-leads"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Leads da demonstração</h2>
          <p>
            Contatos dos últimos 90 dias. A demonstração não cria reservas nem
            autoriza embarques.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => cache.invalidateQueries({ queryKey: ["demo-leads"] })}
        >
          Atualizar contatos
        </button>
      </header>
      <div className="modal-form">
        {(error || leads.error || config.error) && (
          <Alert>
            {error ||
              "Não foi possível carregar os contatos ou as configurações."}
          </Alert>
        )}
        <details>
          <summary>Configurar demonstração do site</summary>
          {error && <Alert>{error}</Alert>}
          {saved && (
            <p role="status">
              Configuração salva com sucesso. Por segurança, a chave não é
              exibida novamente.
            </p>
          )}
          {config.data && (
            <form
              onSubmit={save}
              key={config.data.version}
              className="modal-form"
            >
              <label>
                <input
                  type="checkbox"
                  name="enabled"
                  defaultChecked={config.data.enabled}
                />{" "}
                Habilitar demonstração pública
              </label>
              <Field label="Limite diário de demonstrações">
                <input
                  name="limit"
                  type="number"
                  min="1"
                  max="1000"
                  required
                  defaultValue={config.data.daily_limit}
                />
              </Field>
              <Field label="Chave secreta do CAPTCHA Turnstile">
                <PasswordInput
                  name="demo_captcha_secret"
                  autoComplete="new-password"
                  value={secret}
                  onChange={(e) => {
                    setSecret(e.target.value);
                    setSaved(false);
                  }}
                  placeholder={
                    config.data.captcha_configured
                      ? "Já configurada; deixe vazio para manter"
                      : "Informe a chave secreta"
                  }
                />
              </Field>
              <p role="status">
                CAPTCHA:{" "}
                {config.data.captcha_configured
                  ? "chave cadastrada"
                  : "chave ainda não cadastrada"}
                . Credencial do site:{" "}
                {config.data.key_configured
                  ? "cadastrada"
                  : "ainda não cadastrada"}
                .
              </p>
              <p>
                Deixe a chave vazia para manter a que já está cadastrada. Se a
                ativação for recusada por falta de configuração, desmarque
                “Habilitar demonstração pública”, salve os dados e conclua a
                configuração antes de ativar.
              </p>
              <p>
                O site deve usar o CAPTCHA com ação demo-ticket. Os envios usam
                o WhatsApp da Nexus configurado no financeiro e o intervalo da
                fila. A credencial abaixo é exclusiva do servidor do site; nunca
                inclua no JavaScript público.
              </p>
              <div className="modal-actions">
                <button
                  type="submit"
                  className="button primary"
                  disabled={busy}
                >
                  {busy ? "Salvando…" : "Salvar configuração"}
                </button>
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy}
                  onClick={rotate}
                >
                  {config.data.key_configured
                    ? "Renovar credencial do site"
                    : "Gerar credencial do site"}
                </button>
              </div>
            </form>
          )}
          {siteKey && (
            <Field label="Nova credencial — copie agora e guarde no servidor do site">
              <PasswordInput readOnly value={siteKey} />
            </Field>
          )}
        </details>
        <div className="form-grid">
          <Field label="Situação comercial">
            <select
              value={stage}
              onChange={(e) => {
                setStage(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Todas</option>
              {Object.entries(stages).map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Autorização comercial">
            <select
              value={marketing}
              onChange={(e) => {
                setMarketing(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos os contatos</option>
              <option value="true">Autorizou contato comercial</option>
              <option value="false">Somente demonstração</option>
            </select>
          </Field>
        </div>
        <a
          className="button secondary"
          href={`/api/v1/nexus/demo-leads/export.csv${stage ? `?stage=${stage}` : ""}`}
        >
          Exportar contatos com autorização comercial (CSV)
        </a>
        <p>
          {leads.data?.total ?? 0} contato(s) no filtro. Aceito pelo serviço não
          confirma entrega ou leitura.
        </p>
        {leads.isPending && <p role="status">Carregando contatos…</p>}
        <div className="table-scroll">
          <table>
            <caption>Contatos da demonstração — até 20 por página</caption>
            <thead>
              <tr>
                <th>Data</th>
                <th>Empresa e passageiro</th>
                <th>WhatsApp</th>
                <th>Consentimento comercial</th>
                <th>Envio</th>
                <th>Prospecção</th>
                <th>Origem e contexto</th>
              </tr>
            </thead>
            <tbody>
              {leads.data?.items.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    {new Date(lead.created_at).toLocaleString("pt-BR", {
                      timeZone: "America/Sao_Paulo",
                    })}
                  </td>
                  <td>
                    <strong>{lead.company_name}</strong>
                    <br />
                    {lead.name}
                  </td>
                  <td>{lead.phone}</td>
                  <td>
                    {lead.marketing_consent
                      ? "Autorizado"
                      : "Somente demonstração"}
                  </td>
                  <td>
                    {deliveries[lead.status] || lead.status}
                    {lead.error_code && <small>{lead.error_code}</small>}
                  </td>
                  <td>
                    <select
                      aria-label={`Situação de ${lead.name}`}
                      disabled={busy || !lead.marketing_consent}
                      value={lead.stage}
                      onChange={(e) => update(lead, e.target.value)}
                    >
                      {Object.entries(stages).map(([v, n]) => (
                        <option key={v} value={v}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <details>
                      <summary>Ver contexto</summary>
                      <p>
                        {lead.source}
                        <br />
                        {lead.city} {lead.state}
                        <br />
                        {lead.browser} · {lead.os}
                        <br />
                        {lead.language} · {lead.timezone}
                      </p>
                      <p>
                        {Object.entries(lead.campaign)
                          .filter(([, v]) => v)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(" · ")}
                      </p>
                      <p>
                        Dados de contexto informados pelo navegador, sem
                        confirmação de localização.
                      </p>
                    </details>
                  </td>
                </tr>
              ))}
              {leads.data?.total === 0 && (
                <tr>
                  <td colSpan={7}>Nenhum contato encontrado.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="modal-actions">
          <button
            className="button secondary"
            disabled={page === 1 || leads.isFetching}
            onClick={() => setPage(page - 1)}
          >
            Página anterior
          </button>
          <span role="status">Página {page}</span>
          <button
            className="button secondary"
            disabled={leads.isFetching || page * 20 >= (leads.data?.total ?? 0)}
            onClick={() => setPage(page + 1)}
          >
            Próxima página
          </button>
        </div>
      </div>
    </section>
  );
}
