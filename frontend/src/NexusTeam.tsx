import { DataUseNotice } from "./components/DataUseNotice";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, roleName, type User } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { PasswordInput } from "./components/PasswordInput";
import { NexusAccessLogs } from "./NexusAccessLogs";

export function NexusTeam({ currentUserId }: { currentUserId: string }) {
  const cache = useQueryClient();
  const users = useQuery({
    queryKey: ["nexus-team"],
    queryFn: () => api<User[]>("/nexus/users"),
  });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "nexus_staff",
  });
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/nexus/users", { method: "POST", body: JSON.stringify(form) });
      await cache.invalidateQueries({ queryKey: ["nexus-team"] });
      setCreating(false);
      setForm({ full_name: "", email: "", password: "", role: "nexus_staff" });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Falha ao cadastrar usuário.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function update(
    user: User,
    changes: { role: string; is_active: boolean },
  ) {
    if (
      !window.confirm(
        `Alterar o acesso de ${user.full_name}?${user.id === currentUserId ? " Seu acesso atual será encerrado." : ""}`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`/nexus/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      if (user.id === currentUserId) {
        window.location.assign("/nexus");
        return;
      }
      await cache.invalidateQueries({ queryKey: ["nexus-team"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao alterar acesso.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Equipe Nexus</h2>
          <p>
            Equipe Nexus gerencia empresas. O administrador completo também
            acessa configurações, financeiro e gestão de usuários internos.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setError("");
            setCreating(true);
          }}
        >
          Adicionar usuário Nexus
        </button>
      </header>
      {!creating && (error || users.error) && (
        <Alert>{error || users.error?.message}</Alert>
      )}
      {users.isPending ? (
        <p>Carregando equipe…</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nome / e-mail</th>
                <th>Perfil</th>
                <th>Situação</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.data?.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.full_name}</strong>
                    <br />
                    {user.email}
                    {user.id === currentUserId && " · você"}
                  </td>
                  <td>
                    <select
                      aria-label={`Perfil de ${user.full_name}`}
                      value={user.role}
                      disabled={busy}
                      onChange={(e) =>
                        void update(user, {
                          role: e.target.value,
                          is_active: user.is_active,
                        })
                      }
                    >
                      <option value="nexus_staff">
                        Equipe Nexus · restrito
                      </option>
                      <option value="nexus">
                        Administrador Nexus · completo
                      </option>
                    </select>
                    <small className="muted">{roleName[user.role]}</small>
                  </td>
                  <td>{user.is_active ? "Ativo" : "Suspenso"}</td>
                  <td>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() =>
                        void update(user, {
                          role: user.role,
                          is_active: !user.is_active,
                        })
                      }
                    >
                      {user.is_active ? "Suspender" : "Ativar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <NexusAccessLogs users={users.data || []} />
      {creating && (
        <Modal
          title="Adicionar usuário Nexus"
          onClose={() => {
            if (!busy) setCreating(false);
          }}
        >
          <form className="modal-form" onSubmit={create}>
            <DataUseNotice purpose="administrar os cadastros e acessos dos colaboradores Nexus" />
            <Field label="Nome completo">
              <input
                required
                minLength={2}
                maxLength={150}
                value={form.full_name}
                onChange={(e) =>
                  setForm({ ...form, full_name: e.target.value })
                }
              />
            </Field>
            <Field label="E-mail">
              <input
                type="email"
                autoComplete="off"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            <Field label="Senha inicial">
              <PasswordInput
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={128}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </Field>
            <small className="muted">
              Mínimo de 8 caracteres, uma letra maiúscula e um caractere
              especial. Compartilhe o acesso por um canal seguro.
            </small>
            <Field label="Perfil de acesso Nexus">
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                <option value="nexus_staff">
                  Equipe Nexus · sem configurações e financeiro
                </option>
                <option value="nexus">
                  Administrador Nexus · acesso completo
                </option>
              </select>
            </Field>
            <p>O acesso é feito em /nexus, com e-mail e senha próprios.</p>
            {error && <Alert>{error}</Alert>}
            <button className="button primary" disabled={busy}>
              Cadastrar usuário Nexus
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
