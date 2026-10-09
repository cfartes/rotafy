import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert } from "./components/ui";

type Delivery = {
  id: string;
  kind: string;
  status: string;
  attempts: number;
  error_code: string | null;
  created_at: string;
  sent_at: string | null;
};
const labels: Record<string, string> = {
  pending: "Aguardando envio",
  sending: "Enviando",
  sent: "Aceita pelo OpenWA",
  failed: "Falha no envio",
  uncertain: "Envio incerto · confira antes de reenviar",
  discarded: "Descartada",
};
const kinds: Record<string, string> = {
  confirmed: "Confirmação",
  cancelled: "Cancelamento",
  paid: "PAGO",
  manual: "Resumo manual",
};
export function ReservationWhatsApp({
  reservationId,
}: {
  reservationId: string;
}) {
  const messages = useQuery({
    queryKey: ["whatsapp-history", reservationId],
    queryFn: () => api<Delivery[]>(`/reservations/${reservationId}/whatsapp`),
    refetchInterval: 15000,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [queued, setQueued] = useState(false);
  const [operationKey, setOperationKey] = useState(() => crypto.randomUUID());
  async function send() {
    setBusy(true);
    setError("");
    setQueued(false);
    try {
      await post(`/reservations/${reservationId}/whatsapp`, {
        operation_key: operationKey,
      });
      setOperationKey(crypto.randomUUID());
      setQueued(true);
      await messages.refetch();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível enfileirar a mensagem.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="operation-card">
      <h3>WhatsApp da reserva</h3>
      <p className="muted">
        Confirmação, cancelamento e marcação PAGO são enviados quando a
        integração da empresa está habilitada. A aceitação pelo gateway não
        confirma a leitura pelo cliente.
      </p>
      <button
        className="button secondary"
        disabled={busy}
        onClick={() => void send()}
      >
        Enviar resumo pelo WhatsApp
      </button>
      {queued && <p role="status">Mensagem adicionada à fila.</p>}
      {error && <Alert>{error}</Alert>}
      {messages.error && <Alert>Não foi possível consultar os envios.</Alert>}
      {messages.data?.length === 0 && (
        <p>Nenhuma mensagem registrada para esta reserva.</p>
      )}
      {messages.data?.map((message) => (
        <p key={message.id}>
          <strong>{kinds[message.kind] || message.kind}</strong> ·{" "}
          {labels[message.status] || message.status}
          <br />
          {new Date(message.created_at).toLocaleString("pt-BR", {
            timeZone: "America/Sao_Paulo",
          })}
          {message.error_code === "session_not_ready" &&
            " · sessão aguardando conexão"}
        </p>
      ))}
    </section>
  );
}
