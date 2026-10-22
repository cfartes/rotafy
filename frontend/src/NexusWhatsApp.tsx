import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert, Modal } from "./components/ui";

type Connection = {
  id: string;
  trade_name: string;
  slug: string;
  contact_phone: string | null;
  is_active: boolean;
  session_id: string | null;
  enabled: boolean;
  module_enabled: boolean;
  status: string | null;
  error_code: string | null;
  last_checked_at: string | null;
  next_attempt_at: string | null;
  disconnect_requested: boolean;
  restart_requested: boolean;
  send_enabled: boolean;
  provider_status: string;
  provider_phone: string | null;
  phone_matches: boolean | null;
};
const states: Record<string, string> = {
  connected: "Conectado",
  ready: "Conectado",
  pending: "Preparando conexão",
  starting: "Iniciando",
  qr_ready: "Aguardando QR Code",
  created: "Sessão criada",
  managed: "Gerenciada pela Nexus",
  paused: "Tentativas pausadas",
  unavailable: "Indisponível",
  disconnected: "Desconectado",
  disconnecting: "Desconectando",
  stopped: "Parado",
  missing: "Sessão não encontrada",
  unknown: "Sem confirmação",
  wrong_number: "Número divergente",
  conflict: "Conferir conexão",
};
export function NexusWhatsApp() {
  const cache = useQueryClient();
  const [search, setSearch] = useState(""),
    [problemOnly, setProblemOnly] = useState(false);
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [flags, setFlags] = useState<Record<string, boolean>>({}),
    [qr, setQr] = useState<Connection | null>(null);
  const result = useQuery({
    queryKey: ["nexus-whatsapp-connections"],
    queryFn: () =>
      api<{
        service: { status: string; checked_at: string };
        companies: Connection[];
      }>("/nexus/whatsapp/connections"),
    refetchInterval: 30000,
    retry: false,
  });
  const online = result.data?.service.status === "available";
  const ready = (row: Connection) =>
    ["ready", "connected"].includes(row.provider_status) &&
    row.phone_matches !== false;
  const rows =
    result.data?.companies.filter(
      (c) =>
        `${c.trade_name} ${c.slug} ${c.contact_phone || ""}`
          .toLocaleLowerCase("pt-BR")
          .includes(search.toLocaleLowerCase("pt-BR")) &&
        (!problemOnly || (c.is_active && c.module_enabled && !ready(c))),
    ) || [];
  async function action(
    company: Connection,
    value: "reconnect" | "restart" | "disconnect",
  ) {
    if (
      value !== "reconnect" &&
      !window.confirm(
        `${value === "restart" ? "Reiniciar a sessão de" : "Desconectar"} ${company.trade_name}? Os envios serão interrompidos durante a operação. Pode ser necessário ler o QR Code novamente.`,
      )
    )
      return;
    setBusy(company.id);
    setError("");
    setNotice("");
    try {
      await post(`/nexus/whatsapp/connections/${company.id}/action`, {
        action: value,
        enable_sends: flags[company.id] ?? company.enabled ?? false,
      });
      setNotice(
        `Solicitação registrada para ${company.trade_name}. O processamento é automático; acompanhe a situação abaixo.`,
      );
      await cache.invalidateQueries({
        queryKey: ["nexus-whatsapp-connections"],
      });
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Não foi possível registrar a operação.",
      );
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="modal-form">
      <section className="panel modal-form">
        <div className="chat-toolbar">
          <div>
            <h2>Conexões WhatsApp das empresas</h2>
            <p>
              Consulte o serviço e administre cada sessão sem acessar a conta do
              cliente.
            </p>
          </div>
          <button
            className="button secondary"
            disabled={result.isFetching}
            onClick={() => void result.refetch()}
          >
            {result.isFetching
              ? "Consultando serviço…"
              : "Verificar conexões agora"}
          </button>
        </div>
        {(error || result.error) && (
          <Alert>{error || String(result.error)}</Alert>
        )}
        {notice && <p role="status">{notice}</p>}
        {result.data && (
          <div className="operation-card">
            <strong>
              {online
                ? "Serviço OpenWA acessível"
                : result.data.service.status === "not_configured"
                  ? "Chave do serviço não configurada"
                  : "Serviço OpenWA indisponível"}
            </strong>
            <p>
              {online
                ? "A consulta foi respondida. Confira a situação de cada empresa abaixo."
                : "Confira a configuração da integração e a disponibilidade da API na VPS. Solicitações de conexão só serão executadas quando o serviço responder."}
            </p>
            <small>
              Última consulta:{" "}
              {new Date(result.data.service.checked_at).toLocaleString("pt-BR")}{" "}
              · Atualização automática a cada 30 segundos
            </small>
          </div>
        )}
        <div className="form-grid">
          <label className="field">
            <span>Pesquisar empresa ou telefone</span>
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={problemOnly}
              onChange={(e) => setProblemOnly(e.target.checked)}
            />
            Somente conexões que precisam de atenção
          </label>
        </div>
      </section>
      {result.isPending && <p role="status">Consultando conexões…</p>}
      {rows.map((row) => (
        <section className="panel modal-form" key={row.id}>
          <div className="chat-toolbar">
            <div>
              <h3>{row.trade_name}</h3>
              <p>
                {row.slug} · {row.contact_phone || "Sem telefone cadastrado"}
              </p>
            </div>
            <strong>
              {!row.is_active
                ? "Empresa desabilitada"
                : !row.module_enabled
                  ? "Módulo WhatsApp desabilitado"
                  : row.disconnect_requested
                    ? row.restart_requested
                      ? "Reiniciando sessão"
                      : "Desconectando"
                    : online
                      ? states[row.provider_status] || "Sem confirmação"
                      : states[row.status || "unknown"] || "Sem confirmação"}
            </strong>
          </div>
          {row.phone_matches === false && (
            <Alert>
              O número conectado difere do cadastro da empresa. Confira o
              vínculo antes de habilitar envios.
            </Alert>
          )}
          <p>
            Conexão no app:{" "}
            {states[row.status || "unknown"] || row.status || "Não iniciada"} ·
            Envios {row.enabled ? "habilitados" : "desabilitados"}
          </p>
          {row.error_code && (
            <p>
              Diagnóstico: <code>{row.error_code}</code>. Confira o serviço e
              tente retomar ou reiniciar a sessão.
            </p>
          )}
          {row.last_checked_at && (
            <small>
              Última verificação pelo app:{" "}
              {new Date(row.last_checked_at).toLocaleString("pt-BR")}
            </small>
          )}
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={flags[row.id] ?? row.enabled ?? false}
              disabled={!row.is_active || !row.module_enabled || !!busy}
              onChange={(e) =>
                setFlags((previous) => ({
                  ...previous,
                  [row.id]: e.target.checked,
                }))
              }
            />
            Permitir envios após conectar e conferir o número
          </label>
          <div className="modal-actions">
            <button
              className="button primary"
              disabled={
                !!busy ||
                !row.is_active ||
                !row.module_enabled ||
                row.disconnect_requested
              }
              onClick={() => void action(row, "reconnect")}
            >
              {busy === row.id ? "Aguarde…" : "Retomar conexão"}
            </button>
            <button
              className="button secondary"
              disabled={
                !!busy ||
                !row.session_id ||
                !row.is_active ||
                !row.module_enabled ||
                row.disconnect_requested
              }
              onClick={() => void action(row, "restart")}
            >
              Reiniciar sessão
            </button>
            <button
              className="button secondary"
              disabled={!!busy || !row.session_id || row.disconnect_requested}
              onClick={() => void action(row, "disconnect")}
            >
              Desconectar
            </button>
            {row.is_active &&
              row.module_enabled &&
              !row.disconnect_requested &&
              ["qr_ready", "starting", "pending", "created"].includes(
                row.status || "",
              ) && (
                <button className="button secondary" onClick={() => setQr(row)}>
                  Exibir QR Code
                </button>
              )}
          </div>
        </section>
      ))}
      {!result.isPending && result.data && !rows.length && (
        <p>Nenhuma empresa encontrada para os filtros selecionados.</p>
      )}
      {qr && <NexusQr company={qr} onClose={() => setQr(null)} />}
    </div>
  );
}

function NexusQr({
  company,
  onClose,
}: {
  company: Connection;
  onClose: () => void;
}) {
  const result = useQuery({
    queryKey: ["nexus-whatsapp-qr", company.id],
    queryFn: () =>
      api<{ qr_code: string | null }>(
        `/nexus/whatsapp/connections/${company.id}/qr`,
      ),
    refetchInterval: 5000,
    retry: false,
  });
  return (
    <Modal
      title={`Conectar WhatsApp · ${company.trade_name}`}
      onClose={onClose}
    >
      <div className="modal-form">
        <p>
          No telefone da empresa, abra WhatsApp → Aparelhos conectados →
          Conectar um aparelho.
        </p>
        {result.error && <Alert>{String(result.error)}</Alert>}
        {result.data?.qr_code ? (
          <img
            src={result.data.qr_code}
            alt={`QR Code do WhatsApp de ${company.trade_name}`}
            style={{ maxWidth: 320, width: "100%", alignSelf: "center" }}
          />
        ) : (
          <p role="status">
            Aguardando QR Code. Ele aparece quando o serviço preparar a sessão e
            deixa de estar disponível após a conexão.
          </p>
        )}
      </div>
    </Modal>
  );
}
