import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Connection = {
  phone: string | null;
  status: string;
  error_code?: string | null;
  send_enabled: boolean;
  next_attempt_at?: string | null;
  connect_requested?: boolean;
  disconnect_requested?: boolean;
};

const labels: Record<string, string> = {
  not_started: "Aguardando conexão",
  pending: "Preparando conexão",
  created: "Aguardando conexão",
  starting: "Iniciando WhatsApp",
  qr_ready: "Escaneie o QR Code",
  connected: "Conectado",
  disconnecting: "Desconectando WhatsApp",
  disconnected: "Desconectado",
  managed: "Configuração gerenciada pela Nexus",
  wrong_number: "Número conectado diferente do informado",
  conflict: "Conexão precisa de conferência",
  unavailable: "Conexão indisponível",
  paused: "Tentativas interrompidas",
  phone_changed: "Telefone cadastral atualizado",
};

function connectionError(code?: string | null) {
  if (
    code === "not_configured" ||
    code?.endsWith("http_401") ||
    code?.endsWith("http_403")
  )
    return "A Nexus precisa conferir a chave e a permissão do serviço de WhatsApp. Seu cadastro está preservado.";
  if (code === "status_http_404" || code === "start_http_404")
    return "A sessão vinculada não foi encontrada no serviço de WhatsApp. Solicite à Nexus a conferência do vínculo antes de tentar novamente.";
  if (code === "start_http_400" || code === "start_http_409")
    return "O serviço recusou iniciar a sessão. A Nexus deve conferir se ela já está em execução ou se o limite de sessões foi atingido.";
  if (code === "create_http_400" || code === "create_http_409")
    return "O serviço recusou criar a sessão. A Nexus deve conferir a configuração e se já existe uma sessão com o mesmo nome.";
  if (code?.endsWith("http_429"))
    return "O serviço limitou as solicitações. Aguarde a próxima tentativa automática.";
  if (code?.endsWith("timeout") || code?.endsWith("http_504"))
    return "O serviço demorou além do prazo para responder. A conexão será conferida novamente automaticamente.";
  if (code?.endsWith("invalid_response"))
    return "O serviço retornou uma resposta inesperada. A Nexus precisa conferir a compatibilidade da integração.";
  return "Não foi possível concluir a conexão. O sistema tentará consultar o serviço novamente.";
}

export function CompanyWhatsApp() {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requested, setRequested] = useState(false);
  const [now, setNow] = useState(Date.now());
  const state = useQuery({
    queryKey: ["company-whatsapp"],
    queryFn: () => api<Connection>("/company/whatsapp"),
    refetchInterval: (query) =>
      ["paused", "disconnected"].includes(query.state.data?.status || "")
        ? false
        : query.state.data?.status === "connected" ? 60000 : 5000,
  });
  const connected = state.data?.status === "connected";
  const disconnecting = state.data?.disconnect_requested || state.data?.status === "disconnecting";
  useEffect(() => {
    if (connected || ["paused", "disconnected"].includes(state.data?.status || "")) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [connected, state.data?.status]);
  const pairing = ["qr_ready", "starting"].includes(state.data?.status || "");
  const qr = useQuery({
    queryKey: ["company-whatsapp-qr"],
    queryFn: () => api<{ qr_code: string | null }>("/company/whatsapp/qr"),
    enabled: pairing,
    refetchInterval: 15000,
    gcTime: 0,
    retry: false,
  });
  const remaining = state.data?.next_attempt_at
    ? Math.max(
        0,
        Math.ceil((Date.parse(state.data.next_attempt_at) - now) / 1000),
      )
    : null;
  const refreshRemaining = Math.max(
    0,
    Math.ceil((state.dataUpdatedAt + 5000 - now) / 1000),
  );
  async function pause() {
    setBusy(true);
    setError("");
    setRequested(false);
    try {
      await api("/company/whatsapp/pause", { method: "POST" });
      cache.setQueryData<Connection>(["company-whatsapp"], (old) =>
        old ? { ...old, status: "paused", connect_requested: false } : old,
      );
      cache.removeQueries({ queryKey: ["company-whatsapp-qr"] });
      await cache.invalidateQueries({ queryKey: ["company-whatsapp"] });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Não foi possível interromper.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function disconnect() {
    setBusy(true);
    setError("");
    setRequested(false);
    try {
      await api("/company/whatsapp/disconnect", { method: "POST" });
      cache.setQueryData<Connection>(["company-whatsapp"], (old) => old ? { ...old, status: "disconnecting", disconnect_requested: true, connect_requested: false } : old);
      cache.removeQueries({ queryKey: ["company-whatsapp-qr"] });
      await cache.invalidateQueries({ queryKey: ["company-whatsapp"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível solicitar a desconexão.");
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (connected || disconnecting) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setRequested(false);
    try {
      await api("/company/whatsapp/connect", {
        method: "POST",
        body: JSON.stringify({
          enabled: form.get("enabled") === "on",
        }),
      });
      cache.removeQueries({ queryKey: ["company-whatsapp-qr"] });
      await cache.invalidateQueries({ queryKey: ["company-whatsapp"] });
      setRequested(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Não foi possível conectar.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="operation-card modal-form">
      <h2>WhatsApp da empresa</h2>
      <p>
        Conecte o número que enviará confirmações de reserva, avisos de
        pagamento, cancelamentos, convites e bilhetes aos seus clientes e
        colaboradores.
      </p>
      {(error || state.error) && <Alert>{error || state.error?.message}</Alert>}
      {state.isPending && <p role="status">Consultando conexão…</p>}
      {state.data && (
        <>
          <p role="status">
            <strong>{labels[state.data.status] || "Aguardando conexão"}</strong>
          </p>
          {state.data.status === "paused" ? (
            <p>
              As tentativas automáticas estão pausadas. Clique em Retomar
              conexão quando desejar continuar.
            </p>
          ) : !connected && state.data.status !== "disconnected" && (
            <div className="muted" aria-live="off">
              {state.data.connect_requested !== false &&
                !["connected", "managed", "created", "not_started"].includes(
                  state.data.status,
                ) &&
                remaining !== null && (
                  <p>
                    {remaining > 0
                      ? `Próxima tentativa automática em ${remaining} s.`
                      : "Aguardando o processamento da próxima tentativa…"}
                  </p>
                )}
              <p>Atualização desta tela em {refreshRemaining} s.</p>
            </div>
          )}
          {(state.data.status === "unavailable" || (disconnecting && state.data.error_code)) && (
            <Alert>
              {disconnecting ? "Envios suspensos. A desconexão ainda não foi confirmada pelo serviço e será tentada novamente automaticamente." : connectionError(state.data.error_code)}
              {state.data.error_code && (
                <p>Código de suporte: {state.data.error_code}</p>
              )}
            </Alert>
          )}
          {state.data.status === "wrong_number" && (
            <Alert>
              Os envios estão suspensos. Confira o telefone informado. Se
              escaneou com outro WhatsApp, desconecte o dispositivo no celular e
              conecte o número correto.
            </Alert>
          )}
          {state.data.status === "conflict" && (
            <Alert>
              Solicite à Nexus a conferência do vínculo. Não é permitido
              compartilhar a sessão entre empresas.
            </Alert>
          )}
          {state.data.status === "disconnected" && (
            <p>
              O WhatsApp está desconectado. Clique em Conectar WhatsApp para
              tentar novamente.
            </p>
          )}
          <form
            onSubmit={submit}
            className="modal-form"
            key={state.data.phone || "new"}
          >
            <Field label="WhatsApp de envio da empresa">
              <input type="tel" value={state.data.phone || ""} readOnly />
            </Field>
            <p className="muted">Telefone obtido do cadastro da empresa. Para alterar, clique no logo ou nome da empresa no menu lateral.</p>
            {!state.data.phone && <Alert>Informe o telefone no cadastro da empresa antes de conectar o WhatsApp.</Alert>}
            {state.data.status === "phone_changed" && <Alert>O telefone cadastrado foi alterado. Conecte o WhatsApp correspondente ao número exibido.</Alert>}
            <label className="operation-checkbox">
              <input
                type="checkbox"
                style={{
                  width: 18,
                  height: 18,
                  minHeight: 18,
                  padding: 0,
                  flex: "0 0 18px",
                }}
                name="enabled"
                disabled={connected || disconnecting}
                defaultChecked={state.data.send_enabled}
              />{" "}
              Habilitar envios após conectar e conferir o número
            </label>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {connected ? (
                <button className="button secondary" type="button" onClick={disconnect} disabled={busy}>
                  {busy ? "Solicitando…" : "Desconectar WhatsApp"}
                </button>
              ) : <button className="button primary" disabled={busy || !state.data.phone || disconnecting} type="submit">
                {busy
                  ? "Solicitando…"
                  : disconnecting ? "Desconectando…"
                  : state.data.status === "paused"
                    ? "Retomar conexão"
                    : "Conectar WhatsApp"}
              </button>}
              {![
                "connected",
                "managed",
                "created",
                "not_started",
                "paused",
                "disconnecting",
                "disconnected",
              ].includes(state.data.status) && (
                <button
                  className="button secondary"
                  type="button"
                  onClick={pause}
                  disabled={busy}
                >
                  Interromper tentativas
                </button>
              )}
            </div>
          </form>
          {requested && !connected && !disconnecting && state.data.connect_requested !== false && (
            <p role="status">
              Solicitação registrada. Aguarde a preparação do QR Code; a tela
              atualiza automaticamente.
            </p>
          )}
          {pairing && (
            <div className="reservation-suggestion">
              <h3>Autorize a conexão no celular</h3>
              <ol>
                <li>Abra o WhatsApp do número informado.</li>
                <li>Entre em Aparelhos conectados → Conectar aparelho.</li>
                <li>
                  Escaneie o QR Code exibido abaixo e aguarde a confirmação.
                </li>
              </ol>
              {qr.data?.qr_code ? (
                <img
                  src={qr.data.qr_code}
                  alt="QR Code para conectar o WhatsApp da empresa"
                  width={280}
                  height={280}
                  style={{ maxWidth: "100%", height: "auto" }}
                />
              ) : (
                <p>
                  Preparando QR Code. Ele será atualizado automaticamente
                  enquanto aguarda a leitura.
                </p>
              )}
              {qr.error && (
                <p>
                  QR Code ainda indisponível. A consulta será repetida
                  automaticamente.
                </p>
              )}
              <p className="muted">
                Este QR Code autoriza acesso ao WhatsApp. Não compartilhe sua
                imagem. Abra esta tela em outro aparelho ou computador para
                escanear com o celular.
              </p>
            </div>
          )}
          {state.data.status === "connected" && (
            <p>
              Número conferido: <strong>{state.data.phone}</strong>.{" "}
              {state.data.send_enabled
                ? "Envios habilitados."
                : "Envios desabilitados."}
            </p>
          )}
        </>
      )}
    </section>
  );
}
