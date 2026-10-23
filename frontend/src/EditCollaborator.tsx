import { DataUseNotice } from "./components/DataUseNotice";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, roleName, type User } from "./api";
import { Alert, Field, Modal } from "./components/ui";

export function EditCollaborator({
  user,
  currentUserId,
  onClose,
  onLogout,
}: {
  user: User;
  currentUserId: string;
  onClose: () => void;
  onLogout: () => void;
}) {
  const cache = useQueryClient();
  const [name, setName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email);
  const [phone, setPhone] = useState(user.contact_phone || "");
  const [role, setRole] = useState(user.role);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          full_name: name,
          email,
          contact_phone: phone.trim() || null,
          role,
        }),
      });
      if (
        user.id === currentUserId &&
        email.trim().toLowerCase() !== user.email
      ) {
        onLogout();
        return;
      }
      await cache.invalidateQueries({ queryKey: ["users"] });
      if (user.id === currentUserId)
        await cache.invalidateQueries({ queryKey: ["session"] });
      await cache.invalidateQueries({ queryKey: ["audit"] });
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível salvar o colaborador.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Editar colaborador"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form className="modal-form" onSubmit={save}>
        <DataUseNotice purpose="manter o cadastro e as permissões de acesso do colaborador" />
        <Field label="Nome completo">
          <input
            required
            minLength={2}
            maxLength={150}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="E-mail de acesso">
          <input
            type="email"
            maxLength={254}
            required
            autoComplete="off"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Telefone / WhatsApp">
          <input
            type="tel"
            maxLength={50}
            value={phone}
            placeholder="+55 47 99999-9999"
            onChange={(e) => setPhone(e.target.value)}
          />
        </Field>
        <Field label="Função do colaborador">
          <select
            value={role}
            disabled={user.id === currentUserId}
            onChange={(e) => setRole(e.target.value as User["role"])}
          >
            {(["admin", "attendant", "driver", "guide"] as const).map(
              (value) => (
                <option key={value} value={value}>
                  {roleName[value]}
                </option>
              ),
            )}
          </select>
        </Field>
        <p className="muted">
          Alterar o e-mail ou a função encerra as sessões desse colaborador. A
          alteração de e-mail também invalida os links de recuperação
          anteriores.
        </p>
        {error && <Alert>{error}</Alert>}
        <div className="modal-actions">
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancelar
          </button>
          <button className="button primary" disabled={busy}>
            Salvar colaborador
          </button>
        </div>
      </form>
    </Modal>
  );
}
