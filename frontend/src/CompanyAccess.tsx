import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Company } from "./api";
import { Alert, Modal } from "./components/ui";

export function CompanyAccess({
  company,
  onClose,
}: {
  company: Company & { admin_email?: string };
  onClose: () => void;
}) {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [sent, setSent] = useState(false);
  const keys = useRef<Record<string, string>>({});
  const query = useQuery({
    queryKey: ["company-welcome", company.id],
    queryFn: () =>
      api<
        {
          id: string;
          channel: string;
          recipient: string;
          status: string;
          created_at: string;
        }[]
      >(`/nexus/companies/${company.id}/welcome`),
    refetchInterval: 5000,
  });
  async function send(channel: string) {
    setBusy(true);
    setError("");
    setSent(false);
    keys.current[channel] ||= crypto.randomUUID();
    try {
      await api(`/nexus/companies/${company.id}/welcome`, {
        method: "POST",
        body: JSON.stringify({ channel, operation_key: keys.current[channel] }),
      });
      delete keys.current[channel];
      setSent(true);
      await cache.invalidateQueries({
        queryKey: ["company-welcome", company.id],
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível solicitar o envio.",
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
    uncertain: "Envio incerto — confira antes de enviar novamente",
    discarded: "Descartado ou link substituído",
  };
  return (
    <Modal title="Empresa cadastrada · enviar acesso" onClose={onClose} wide>
      <div className="modal-form">
        <h3>{company.trade_name}</h3>
        <p>
          Razão social: {company.corporate_name}
          <br />
          CPF/CNPJ: {company.cnpj}
          <br />
          Identificador de acesso: <strong>{company.slug}</strong>
          <br />
          Telefone/WhatsApp: {company.contact_phone}
        </p>
        {company.admin_email && (
          <p>
            E-mail de login: <strong>{company.admin_email}</strong>
          </p>
        )}
        <p>
          Envie os dados cadastrais, a página de acesso, o e-mail do primeiro
          administrador ativo e um link para definir a senha, válido por 24
          horas. A senha inicial não é enviada em texto.
        </p>
        <p className="muted">
          O WhatsApp utiliza o número da Nexus configurado para envio. Um novo
          convite invalida os links anteriores. Aceito pelo serviço não confirma
          entrega ou leitura.
        </p>
        <div className="modal-actions">
          <button
            type="button"
            className="button primary"
            disabled={busy}
            onClick={() => void send("email")}
          >
            Enviar acesso por e-mail
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => void send("whatsapp")}
          >
            Enviar acesso por WhatsApp
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => void send("both")}
          >
            Enviar pelos dois canais
          </button>
        </div>
        {sent && (
          <p role="status">
            Envio solicitado. A empresa já está cadastrada; acompanhe o
            resultado abaixo.
          </p>
        )}
        {(error || query.error) && (
          <Alert>{error || query.error?.message}</Alert>
        )}
        {query.data?.map((item) => (
          <p key={item.id}>
            {item.channel === "email" ? "E-mail" : "WhatsApp"} ·{" "}
            {item.recipient} · {labels[item.status] || item.status}
            <br />
            <small>
              {new Date(item.created_at).toLocaleString("pt-BR", {
                timeZone: "America/Sao_Paulo",
              })}
            </small>
          </p>
        ))}
        <button type="button" className="button secondary" onClick={onClose}>
          Concluir
        </button>
      </div>
    </Modal>
  );
}
