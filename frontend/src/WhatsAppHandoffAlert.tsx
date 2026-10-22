import { MessageCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import "./whatsapp-handoff-alert.css";

export type Handoff = { chat_id: string; phone: string | null; handoff_at: string };

export function WhatsAppHandoffAlert({ onOpen }: { onOpen: (handoff: Handoff) => void }) {
  const { data } = useQuery({
    queryKey: ["whatsapp-handoffs"],
    queryFn: () => api<Handoff[]>("/whatsapp/chat/handoffs"),
    refetchInterval: 10000,
    retry: false,
  });
  if (!data?.length) return null;
  return (
    <aside className="whatsapp-handoff-alert" aria-label="Atendimentos WhatsApp pendentes">
      <MessageCircle size={22} aria-hidden="true" />
      <div>
        <p role="status"><strong>{data.length === 1 ? "1 atendimento humano pendente no WhatsApp" : `${data.length} atendimentos humanos pendentes no WhatsApp`}</strong></p>
        <p>Há clientes aguardando atendimento da equipe. Clique para abrir a conversa.</p>
        <ul>
          {data.map(handoff => <li key={handoff.chat_id}>
            <button type="button" className="button secondary" onClick={() => onOpen(handoff)}>
              Atender {handoff.phone || "cliente"}
            </button>
          </li>)}
        </ul>
      </div>
    </aside>
  );
}
