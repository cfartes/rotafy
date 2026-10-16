import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";
import { PhoneInput } from "./components/PhoneInput";

type Connection = {
  phone: string | null;
  status: string;
  error_code?: string | null;
  send_enabled: boolean;
};

const labels: Record<string, string> = {
  not_started: "Aguardando conexão",
  pending: "Preparando conexão",
  created: "Aguardando conexão",
  starting: "Iniciando WhatsApp",
  qr_ready: "Escaneie o QR Code",
  connected: "Conectado",
  disconnected: "Desconectado",
  managed: "Configuração gerenciada pela Nexus",
  wrong_number: "Número conectado diferente do informado",
  conflict: "Conexão precisa de conferência",
  unavailable: "Conexão indisponível",
};

export function CompanyWhatsApp() {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requested, setRequested] = useState(false);
  const state = useQuery({
    queryKey: ["company-whatsapp"],
    queryFn: () => api<Connection>("/company/whatsapp"),
    refetchInterval: 5000,
  });
  const pairing = ["qr_ready", "starting"].includes(state.data?.status || "");
  const qr = useQuery({
    queryKey: ["company-whatsapp-qr"],
    queryFn: () => api<{ qr_code: string | null }>("/company/whatsapp/qr"),
    enabled: pairing,
    refetchInterval: 15000,
    gcTime: 0,
    retry: false,
  });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setRequested(false);
    try {
      await api("/company/whatsapp/connect", {
        method: "POST",
        body: JSON.stringify({
          contact_phone: form.get("contact_phone"),
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
          {state.data.status === "unavailable" && (
            <Alert>
              {state.data.error_code === "not_configured" ||
              ["http_401", "http_403"].includes(state.data.error_code || "")
                ? "A Nexus precisa conferir a configuração e a permissão do serviço de WhatsApp. Seu cadastro está preservado."
                : "O serviço não respondeu. A conexão será consultada novamente automaticamente."}
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
              O WhatsApp perdeu a conexão. Clique em Conectar WhatsApp para
              tentar novamente.
            </p>
          )}
          <form
            onSubmit={submit}
            className="modal-form"
            key={state.data.phone || "new"}
          >
            <Field label="WhatsApp de envio da empresa">
              <PhoneInput initialValue={state.data.phone || ""} required />
            </Field>
            <label>
              <input
                type="checkbox"
                name="enabled"
                defaultChecked={state.data.send_enabled}
              />{" "}
              Habilitar envios após conectar e conferir o número
            </label>
            <div>
              <button className="primary" disabled={busy} type="submit">
                {busy ? "Solicitando…" : "Conectar WhatsApp"}
              </button>
            </div>
          </form>
          {requested && (
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
