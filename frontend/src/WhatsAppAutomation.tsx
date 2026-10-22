import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Settings = {
  commands_enabled: boolean;
  tickets_enabled: boolean;
  commands: string[];
  greeting: string;
  webhook_status: string;
  webhook_error: string | null;
};
const commands: Record<string, string> = {
  qrcode: "/qrcode ou /bilhete — Bilhete de embarque",
  onibus: "/onibus — Veículo e embarque",
  dados: "/dados — Resumo da reserva",
  embarque: "/embarque — Local e horário",
  atendimento: "/atendimento — Solicitar atendimento humano",
};
const states: Record<string, string> = {
  pending: "Na fila",
  sending: "Enviando",
  sent: "Aceito pelo WhatsApp",
  failed: "Falhou",
  uncertain: "Envio incerto — confira antes de reenviar",
  discarded: "Cancelado ou expirado",
  attention: "Precisa de atenção",
};

export function WhatsAppAutomation() {
  const cache = useQueryClient();
  const config = useQuery({
    queryKey: ["whatsapp-automation"],
    queryFn: () => api<Settings>("/company/whatsapp/automation"),
    refetchInterval: 30000,
  });
  const history = useQuery({
    queryKey: ["whatsapp-automation-history"],
    queryFn: () =>
      api<
        {
          id: string;
          kind: string;
          status: string;
          error_code: string | null;
          passenger_name: string | null;
          trip_name: string | null;
        }[]
      >("/company/whatsapp/automation/history"),
    refetchInterval: 30000,
  });
  return (
    <section className="panel automation-settings">
      <div className="panel-header">
        <div>
          <h2>Atendimento e bilhetes automáticos</h2>
          <p>
            Defina como o WhatsApp atende os passageiros e entrega seus
            bilhetes.
          </p>
        </div>
      </div>
      <div className="panel-body">
        {config.error && <Alert>{(config.error as Error).message}</Alert>}
        {config.data && (
          <AutomationForm
            initial={config.data}
            onSaved={() =>
              void cache.invalidateQueries({
                queryKey: ["whatsapp-automation"],
              })
            }
          />
        )}
        <h3>Acompanhamento dos últimos envios</h3>
        {history.error && <Alert>Não foi possível carregar os envios.</Alert>}
        {history.data?.length === 0 && (
          <p className="muted">Nenhum envio automático registrado.</p>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tipo / passageiro</th>
                <th>Viagem</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {history.data?.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.kind === "ticket" ? "Bilhete" : "Comando"}
                    {row.passenger_name && (
                      <>
                        <br />
                        {row.passenger_name}
                      </>
                    )}
                  </td>
                  <td>{row.trip_name || "—"}</td>
                  <td>
                    {states[row.status] || row.status}
                    {row.error_code === "ticket_requires_reissue" && (
                      <p>
                        Bilhete antigo sem cópia recuperável. Use o envio manual
                        com o link original, ou reemita o bilhete na reserva.
                      </p>
                    )}
                    {row.error_code === "phone_unresolved" && (
                      <p>
                        Não foi possível confirmar o telefone. Confira a
                        conversa manualmente.
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function AutomationForm({
  initial,
  onSaved,
}: {
  initial: Settings;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Settings | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  const value = draft || initial;
  function change(patch: Partial<Settings>) {
    setDraft({ ...value, ...patch });
    setSaved(false);
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/company/whatsapp/automation", {
        method: "PUT",
        body: JSON.stringify({
          commands_enabled: value.commands_enabled,
          tickets_enabled: value.tickets_enabled,
          commands: value.commands,
          greeting: value.greeting,
        }),
      });
      setDraft(null);
      setSaved(true);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save}>
      <label className="check">
        <input
          type="checkbox"
          checked={value.commands_enabled}
          onChange={(e) => change({ commands_enabled: e.target.checked })}
        />
        Habilitar comandos automáticos no WhatsApp
      </label>
      <p className="muted">
        O passageiro envia /menu para ver as opções. As consultas usam o
        telefone da reserva; quando necessário, ele escolhe a reserva ou
        passageiro por número.
      </p>
      {value.commands_enabled && (
        <>
          <Field label="Mensagem do menu">
            <textarea
              maxLength={500}
              required
              value={value.greeting}
              onChange={(e) => change({ greeting: e.target.value })}
            />
          </Field>
          <fieldset>
            <legend>Comandos disponíveis</legend>
            {Object.entries(commands).map(([id, label]) => (
              <label className="check" key={id}>
                <input
                  type="checkbox"
                  checked={value.commands.includes(id)}
                  onChange={(e) =>
                    change({
                      commands: e.target.checked
                        ? [...value.commands, id]
                        : value.commands.filter((c) => c !== id),
                    })
                  }
                />
                {label}
              </label>
            ))}
          </fieldset>
          <p className="muted">
            Recebimento:{" "}
            {initial.webhook_status === "active"
              ? "configurado"
              : initial.webhook_status === "error"
                ? "indisponível — confira a conexão e as permissões do serviço"
                : "aguardando configuração automática"}
            .
          </p>
        </>
      )}
      <label className="check">
        <input
          type="checkbox"
          checked={value.tickets_enabled}
          onChange={(e) => change({ tickets_enabled: e.target.checked })}
        />
        Enviar bilhetes automaticamente 24 horas antes do primeiro embarque
      </label>
      <p className="muted">
        Uma fila única considera todas as viagens e envia um bilhete por
        passageiro, com intervalo mínimo de 3 minutos entre mensagens
        automáticas. Reservas confirmadas a menos de 24 horas entram na fila. O
        envio pode ocorrer depois quando houver fila ou indisponibilidade. O
        botão manual continua disponível.
      </p>
      <p className="muted">
        Bilhetes já emitidos não são substituídos automaticamente. Se um bilhete
        antigo precisar de atenção, ele será indicado no acompanhamento.
      </p>
      {error && <Alert>{error}</Alert>}
      {saved && <p role="status">Configuração salva.</p>}
      <button className="button primary" disabled={busy}>
        {busy ? "Salvando…" : "Salvar automações"}
      </button>
    </form>
  );
}
