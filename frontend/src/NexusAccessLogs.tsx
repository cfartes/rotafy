import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type User } from "./api";
import { Alert, Field } from "./components/ui";

type Access = {
  id: string;
  created_at: string;
  action: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
};
export function NexusAccessLogs({ users }: { users: User[] }) {
  const [person, setPerson] = useState("");
  const [event, setEvent] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const params = new URLSearchParams();
  if (person) params.set("user_id", person);
  if (event) params.set("event", event);
  const validDate = (value: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number(value.slice(0, 4)) >= 1900 &&
    Number.isFinite(Date.parse(`${value}T00:00:00-03:00`));
  if (validDate(start)) params.set("starts_at", `${start}T00:00:00-03:00`);
  if (validDate(end))
    params.set(
      "ends_at",
      new Date(
        new Date(`${end}T00:00:00-03:00`).getTime() + 86400000,
      ).toISOString(),
    );
  const logs = useQuery({
    queryKey: ["nexus-access-logs", person, event, start, end],
    queryFn: () => api<Access[]>(`/nexus/users/access-logs?${params}`),
    refetchInterval: 30000,
  });
  return (
    <section className="operation-card modal-form">
      <h3>Log de acesso dos colaboradores Nexus</h3>
      <p>
        Entradas autenticadas e saídas pelo botão Sair. São exibidos até 200
        registros por consulta, incluindo o histórico disponível. Horários de
        Brasília. Fechar o navegador ou expirar a sessão não registra uma saída.
      </p>
      <div className="form-grid">
        <Field label="Colaborador no log de acesso">
          <select value={person} onChange={(e) => setPerson(e.target.value)}>
            <option value="">Todos</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} · {u.email}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Evento de acesso">
          <select value={event} onChange={(e) => setEvent(e.target.value)}>
            <option value="">Entradas e saídas</option>
            <option value="auth.login">Entrada</option>
            <option value="auth.logout">Saída</option>
          </select>
        </Field>
        <Field label="Acessos a partir de">
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </Field>
        <Field label="Acessos até">
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </Field>
      </div>
      <button
        type="button"
        className="button secondary"
        disabled={logs.isFetching}
        onClick={() => void logs.refetch()}
      >
        Atualizar log de acesso
      </button>
      {logs.error && <Alert>{logs.error.message}</Alert>}
      {logs.isPending ? (
        <p>Carregando acessos…</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Data e hora</th>
                <th>Colaborador</th>
                <th>E-mail</th>
                <th>Evento</th>
              </tr>
            </thead>
            <tbody>
              {logs.data?.map((row) => (
                <tr key={row.id}>
                  <td>
                    {new Date(row.created_at).toLocaleString("pt-BR", {
                      timeZone: "America/Sao_Paulo",
                    })}
                  </td>
                  <td>{row.full_name}</td>
                  <td>{row.email}</td>
                  <td>{row.action === "auth.login" ? "Entrada" : "Saída"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.data?.length === 0 && (
            <p>Nenhum acesso encontrado neste período.</p>
          )}
        </div>
      )}
    </section>
  );
}
