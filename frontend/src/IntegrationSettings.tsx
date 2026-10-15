import { CollectionSettings } from "./Collections";
import { PasswordInput } from "./components/PasswordInput";
import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Configuration = {
  version: number;
  openwa_base_url: string;
  openwa_key_configured: boolean;
  resend_key_configured: boolean;
  email_from: string;
};
type Session = { id: string; name: string; status: string; phone?: string };
type CompanySession = {
  id: string;
  trade_name: string;
  slug: string;
  is_active: boolean;
  session_id: string | null;
  enabled: boolean;
  contact_phone?: string | null;
};

function CompanyBinding({
  company,
  sessions,
  onSaved,
}: {
  company: CompanySession;
  sessions: Session[];
  onSaved: () => Promise<void>;
}) {
  const [session, setSession] = useState(company.session_id || "");
  const [enabled, setEnabled] = useState(company.enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [phone, setPhone] = useState(company.contact_phone || "");
  const [searching, setSearching] = useState(false);
  const [found, setFound] = useState<Session | null>(null);
  async function findSession() {
    setSearching(true);
    setError("");
    setSaved(false);
    setFound(null);
    try {
      const result = await api<Session>(
        `/nexus/integrations/companies/${company.id}/find-session`,
        {
          method: "POST",
          body: JSON.stringify({ phone }),
        },
      );
      setSession(result.id);
      setFound(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível localizar a sessão.",
      );
    } finally {
      setSearching(false);
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api(`/nexus/integrations/companies/${company.id}`, {
        method: "PUT",
        body: JSON.stringify({ session_id: session, enabled }),
      });
      await onSaved();
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      className="operation-card package-route-card modal-form"
      onSubmit={submit}
    >
      <h3>{company.trade_name}</h3>
      <p className="muted">
        {company.slug}
        {!company.is_active && " · empresa suspensa"}
      </p>
      <Field label={`WhatsApp de envio de ${company.trade_name}`}>
        <input
          type="tel"
          value={phone}
          maxLength={50}
          disabled={searching || busy}
          placeholder="+55 47 99999-9999"
          onChange={(e) => {
            setPhone(e.target.value);
            if (found) setSession(company.session_id || "");
            setFound(null);
          }}
        />
      </Field>
      <small className="muted">
        Confira o número conectado que enviará as mensagens. O telefone de
        contato da empresa é sugerido e pode ser diferente do número de envio.
        Use + e DDI para números internacionais.
      </small>
      <button
        type="button"
        className="button secondary"
        disabled={searching || busy || !phone.trim()}
        onClick={() => void findSession()}
      >
        {searching
          ? "Buscando sessão…"
          : `Buscar sessão pelo telefone de ${company.trade_name}`}
      </button>
      {found && (
        <p role="status">
          Sessão encontrada: {found.name} · {found.phone} · {found.status}.
          Confira o ID e clique em Salvar sessão para confirmar o vínculo.
        </p>
      )}
      {sessions.length > 0 && (
        <Field label={`Sessão OpenWA de ${company.trade_name}`}>
          <select
            disabled={searching || busy}
            value={session}
            onChange={(e) => {
              setSession(e.target.value);
              setFound(null);
              setSaved(false);
            }}
          >
            <option value="">Selecione a sessão desta empresa</option>
            {session && !sessions.some((s) => s.id === session) && (
              <option value={session}>Sessão salva · {session}</option>
            )}
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.status} · {s.id}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field label={`ID da sessão de ${company.trade_name}`}>
        <input
          required
          disabled={searching || busy}
          value={session}
          placeholder="UUID da sessão conectada no OpenWA"
          pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
          onChange={(e) => {
            setSession(e.target.value.trim());
            setFound(null);
            setSaved(false);
          }}
        />
      </Field>
      <label className="operation-checkbox">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => {
            setEnabled(e.target.checked);
            setSaved(false);
          }}
        />
        Habilitar envios para {company.trade_name}
      </label>
      {error && <Alert>{error}</Alert>}
      {saved && <p role="status">Sessão da empresa salva.</p>}
      <button className="button secondary" disabled={busy || searching}>
        Salvar sessão de {company.trade_name}
      </button>
    </form>
  );
}

export function IntegrationSettings() {
  const cache = useQueryClient();
  const config = useQuery({
    queryKey: ["integration-settings"],
    queryFn: () => api<Configuration>("/nexus/integrations"),
    retry: false,
  });
  const companies = useQuery({
    queryKey: ["integration-companies"],
    queryFn: () => api<CompanySession[]>("/nexus/integrations/companies"),
  });
  const sessions = useQuery({
    queryKey: ["integration-sessions"],
    queryFn: () => api<Session[]>("/nexus/integrations/sessions"),
    enabled: false,
    retry: false,
  });
  const [openwaKey, setOpenwaKey] = useState("");
  const [resendKey, setResendKey] = useState("");
  const [email, setEmail] = useState("");
  const [clearOpenwa, setClearOpenwa] = useState(false);
  const [clearResend, setClearResend] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (config.data)
      setEmail(
        config.data.email_from.match(/<([^>]+)>/)?.[1] ||
          config.data.email_from,
      );
  }, [config.data?.version]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!config.data) return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/nexus/integrations", {
        method: "PUT",
        body: JSON.stringify({
          expected_version: config.data.version,
          openwa_api_key: openwaKey || undefined,
          resend_api_key: resendKey || undefined,
          email_from: email || undefined,
          clear_openwa_key: clearOpenwa,
          clear_resend_key: clearResend,
        }),
      });
      setOpenwaKey("");
      setResendKey("");
      setClearOpenwa(false);
      setClearResend(false);
      await cache.invalidateQueries({ queryKey: ["integration-settings"] });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  if (config.isPending) return <p>Carregando configurações…</p>;
  if (config.error) return <Alert>{config.error.message}</Alert>;
  return (
    <div className="reservation-workspace">
      <CollectionSettings />
      <form className="operation-card modal-form" onSubmit={submit}>
        <h2>Mensagens e e-mails</h2>
        <p>
          Configuração exclusiva da Nexus. As chaves salvas ficam protegidas e
          não são exibidas novamente. Alterações passam a valer sem editar
          arquivos ou reiniciar os serviços.
        </p>
        <h3>WhatsApp · OpenWA</h3>
        <p className="muted">Gateway: {config.data.openwa_base_url}</p>
        <Field label="API_KEY do OpenWA">
          <PasswordInput
            autoComplete="new-password"
            value={openwaKey}
            maxLength={4096}
            placeholder={
              config.data.openwa_key_configured
                ? "Chave cadastrada · deixe vazio para manter"
                : "Informe a chave do OpenWA"
            }
            onChange={(e) => setOpenwaKey(e.target.value)}
          />
        </Field>
        <p>
          {config.data.openwa_key_configured
            ? "Chave OpenWA cadastrada."
            : "OpenWA ainda não configurado."}
        </p>
        {config.data.openwa_key_configured && (
          <label className="operation-checkbox">
            <input
              type="checkbox"
              checked={clearOpenwa}
              onChange={(e) => setClearOpenwa(e.target.checked)}
            />
            Remover chave OpenWA ao salvar
          </label>
        )}
        <h3>E-mails · Resend</h3>
        <div className="form-grid">
          <Field label="API_KEY do Resend">
            <PasswordInput
              autoComplete="new-password"
              value={resendKey}
              maxLength={4096}
              placeholder={
                config.data.resend_key_configured
                  ? "Chave cadastrada · deixe vazio para manter"
                  : "Informe a chave do Resend"
              }
              onChange={(e) => setResendKey(e.target.value)}
            />
          </Field>
          <Field label="E-mail remetente do Resend">
            <input
              type="email"
              value={email}
              maxLength={254}
              placeholder="acesso@seudominio.com.br"
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
        </div>
        <p className="muted">
          Use um remetente do domínio verificado na sua conta Resend. Esta
          configuração atende convites e recuperação de senha.
        </p>
        <p>
          {config.data.resend_key_configured
            ? "Chave Resend cadastrada."
            : "Resend ainda não configurado."}
        </p>
        {config.data.resend_key_configured && (
          <label className="operation-checkbox">
            <input
              type="checkbox"
              checked={clearResend}
              onChange={(e) => setClearResend(e.target.checked)}
            />
            Remover chave Resend ao salvar
          </label>
        )}
        {error && <Alert>{error}</Alert>}
        {saved && <p role="status">Configuração salva.</p>}
        <button className="button primary" disabled={busy}>
          Salvar configurações
        </button>
      </form>
      <section className="operation-card modal-form">
        <h2>WhatsApp de cada empresa</h2>
        <p>
          Cada empresa utiliza seu próprio número e sessão. Crie a sessão e leia
          o QR no painel OpenWA; depois associe seu ID aqui. Uma sessão não pode
          ser compartilhada entre empresas.
        </p>
        <button
          className="button secondary"
          disabled={sessions.isFetching || !config.data.openwa_key_configured}
          onClick={() => void sessions.refetch()}
        >
          Consultar sessões OpenWA
        </button>
        {sessions.error && <Alert>{sessions.error.message}</Alert>}
        {sessions.isSuccess && sessions.data.length === 0 && (
          <p>Nenhuma sessão encontrada.</p>
        )}
        {companies.error && <Alert>{companies.error.message}</Alert>}
        {companies.isPending && <p>Carregando empresas…</p>}
        {companies.data?.length === 0 && <p>Nenhuma empresa cadastrada.</p>}
        {companies.data?.map((company) => (
          <CompanyBinding
            key={company.id}
            company={company}
            sessions={sessions.data || []}
            onSaved={async () => {
              await cache.invalidateQueries({
                queryKey: ["integration-companies"],
              });
            }}
          />
        ))}
      </section>
    </div>
  );
}
