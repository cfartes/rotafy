import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, type User } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { PhoneInput } from "./components/PhoneInput";

export function InvitationModal({
  user,
  onClose,
  onSent,
}: {
  user: User;
  onClose: () => void;
  onSent: () => void;
}) {
  const [channel, setChannel] = useState("email");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await post(`/users/${user.id}/invitation`, {
        channel,
        contact_phone: String(data.get("contact_phone") || "").trim() || null,
      });
      onSent();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível enviar o convite.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Enviar convite" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        <p>
          <strong>{user.full_name}</strong>
          <br />
          {user.email}
        </p>
        <Field label="Enviar convite por">
          <select
            value={channel}
            onChange={(event) => setChannel(event.target.value)}
          >
            <option value="email">E-mail</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="both">E-mail e WhatsApp</option>
          </select>
        </Field>
        <Field label="Telefone/WhatsApp do colaborador">
          <PhoneInput
            initialValue={user.contact_phone || ""}
            required={channel !== "email"}
          />
        </Field>
        <p className="muted">
          Convite válido por 24 horas. O novo convite substitui os links
          anteriores. O colaborador define sua própria senha e entra com o
          e-mail cadastrado.
        </p>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button" disabled={pending}>
            {pending ? "Enviando…" : "Enviar convite"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

export function ForgotPassword({
  nexus,
  onClose,
}: {
  nexus: boolean;
  onClose: () => void;
}) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      const result = await post<{ message: string }>("/auth/forgot-password", {
        email: data.get("email"),
        company: nexus ? null : data.get("company"),
        nexus,
      });
      setMessage(result.message);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível solicitar o link.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Recuperar acesso" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        {!nexus && (
          <Field label="Identificador da empresa">
            <input
              name="company"
              required
              maxLength={50}
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
            />
          </Field>
        )}
        <Field label="E-mail cadastrado">
          <input
            name="email"
            type="email"
            required
            maxLength={254}
            autoComplete="email"
          />
        </Field>
        {message && <p role="status">{message}</p>}
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Fechar
          </button>
          <button className="button primary" disabled={pending || !!message}>
            {pending ? "Solicitando…" : "Enviar link de recuperação"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

type Delivery = {
  id: string;
  recipient: string;
  status: string;
  attempts: number;
  created_at: string;
  sent_at: string | null;
  error_code?: string | null;
};

const whatsappReasons: Record<string, string> = {
  recipient_lookup_failed:
    "Não foi possível confirmar o identificador do destinatário. O envio aguarda nova consulta, sem mensagem enviada nesta tentativa.",
  recipient_not_registered:
    "O serviço informou que o telefone não está registrado no WhatsApp. Confira o número antes de gerar outro convite.",
  send_timeout: "O serviço de WhatsApp não respondeu ao envio dentro do prazo.",
  tls_error: "Falha na conexão segura com o serviço de WhatsApp.",
  invalid_response:
    "O serviço respondeu ao envio em um formato que não pôde ser lido.",
  connection_error:
    "A conexão com o serviço de WhatsApp falhou durante o envio.",
  acceptance_unknown:
    "Registro antigo: a falha de comunicação não teve sua causa detalhada. A atualização não modifica este histórico.",
  unrecognized_response:
    "A resposta do serviço não confirmou a aceitação da mensagem.",
  provider_error:
    "O serviço de WhatsApp retornou um erro interno durante o envio.",
  worker_interrupted:
    "O processamento foi interrompido antes de registrar o resultado do envio.",
  session_not_ready:
    "A sessão da empresa não está conectada. O envio aguarda conexão.",
  rate_limited:
    "O serviço limitou os envios. Aguarde a próxima tentativa programada.",
  http_401: "O serviço recusou a chave de acesso configurada.",
  http_403: "A chave configurada não possui permissão para este envio.",
  http_404: "O serviço não encontrou a sessão ou o destino solicitado.",
};
export function EmailDeliveries({ onClose }: { onClose: () => void }) {
  const whatsapp = useQuery({
    queryKey: ["whatsapp-invitations"],
    queryFn: () => api<Delivery[]>("/users/invitations/whatsapp/status"),
    refetchInterval: 5000,
  });
  const result = useQuery({
    queryKey: ["emails"],
    queryFn: () => api<Delivery[]>("/emails/status"),
    refetchInterval: 5000,
  });
  const labels: Record<string, string> = {
    pending: "Na fila",
    sent: "Aceito pelo Resend",
    failed: "Falhou — reenvie o convite",
    discarded: "Link substituído, utilizado ou expirado",
  };
  return (
    <Modal title="E-mails de acesso" onClose={onClose}>
      <div className="modal-form">
        <p className="muted">
          Aceito pelo Resend indica envio ao provedor. Confira também a caixa de
          spam; a entrega na caixa de entrada depende do destinatário.
        </p>
        {result.error && <Alert>{result.error.message}</Alert>}
        {whatsapp.error && <Alert>{whatsapp.error.message}</Alert>}
        {!!whatsapp.data?.length && (
          <section>
            <h3>Convites por WhatsApp</h3>
            <p className="muted">
              Aceito pelo OpenWA não confirma entrega ou leitura.
            </p>
            {whatsapp.data.map((row) => (
              <div className="operation-card" key={row.id}>
                <strong>{row.recipient}</strong>
                {row.created_at && (
                  <p className="muted">
                    Solicitado em{" "}
                    {new Date(row.created_at).toLocaleString("pt-BR")}
                  </p>
                )}
                <p>
                  {
                    (
                      {
                        pending: "Na fila",
                        sending: "Enviando",
                        sent: "Aceito pelo OpenWA",
                        failed: "Falhou — reenvie o convite",
                        uncertain: "Envio incerto — confira antes de reenviar",
                        discarded: "Link substituído, utilizado ou expirado",
                      } as Record<string, string>
                    )[row.status]
                  }{" "}
                  · {row.attempts} tentativa(s)
                </p>
                {row.error_code && (
                  <p>
                    <strong>Motivo:</strong>{" "}
                    {whatsappReasons[row.error_code] ||
                      "O serviço não confirmou o envio. Solicite suporte para conferir este registro."}
                  </p>
                )}
                {row.status === "uncertain" && (
                  <p className="muted">
                    Confira o recebimento e o histórico do serviço antes de
                    gerar outro convite. Um novo convite substitui o link
                    anterior.
                  </p>
                )}
              </div>
            ))}
          </section>
        )}
        {result.isPending ? (
          <p>Carregando…</p>
        ) : !result.data?.length ? (
          <p>Nenhum envio registrado.</p>
        ) : (
          result.data.map((row) => (
            <div className="operation-card" key={row.id}>
              <strong>{row.recipient}</strong>
              <p>
                {labels[row.status]} · {row.attempts} tentativa(s)
              </p>
            </div>
          ))
        )}
      </div>
    </Modal>
  );
}
