import { DataUseNotice } from "./components/DataUseNotice";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, type User } from "./api";
import { Alert, Field } from "./components/ui";

type Scope = { id: string; name: string };
type Key = {
  id: string;
  name: string;
  user_name: string;
  is_active: boolean;
  expires_at: string;
  scopes: string[];
};
export function PartnerIntegration() {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const keys = useQuery({
    queryKey: ["service-keys"],
    queryFn: () => api<Key[]>("/integrations/service-keys"),
  });
  const scopes = useQuery({
    queryKey: ["service-scopes"],
    queryFn: () => api<Scope[]>("/integrations/service-keys/scopes"),
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api<User[]>("/users"),
  });
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setSecret("");
    try {
      const result = await post<{ token: string }>(
        "/integrations/service-keys",
        {
          name: data.get("name"),
          user_id: data.get("user_id"),
          valid_days: Number(data.get("days")),
          scopes: selected,
        },
      );
      setSecret(result.token);
      await cache.invalidateQueries({ queryKey: ["service-keys"] });
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível criar a chave.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function revoke(key: Key) {
    if (
      !window.confirm(
        `Revogar a chave ${key.name}? O parceiro perderá o acesso por esta chave.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await post(`/integrations/service-keys/${key.id}/revoke`, {});
      await cache.invalidateQueries({ queryKey: ["service-keys"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível revogar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-form">
      <section className="panel modal-form">
        <h2>Integração com sistema parceiro</h2>
        <p>
          Crie uma chave para o servidor do parceiro sincronizar viagens,
          reservas e bilhetes. Escolha apenas as permissões necessárias. O
          embarque e desembarque continuam sendo feitos por motorista/guia
          identificado no APK.
        </p>
        {(error || keys.error || scopes.error || users.error) && (
          <Alert>
            {error || String(keys.error || scopes.error || users.error)}
          </Alert>
        )}
        {secret && (
          <div className="operation-card">
            <Field label="Chave criada — copie agora; não será exibida novamente">
              <textarea
                readOnly
                rows={3}
                value={secret}
                onFocus={(e) => e.currentTarget.select()}
              />
            </Field>
            <p>
              Entregue por um canal seguro. Não coloque esta chave no aplicativo
              do passageiro.
            </p>
            <button className="button secondary" onClick={() => setSecret("")}>
              Ocultar chave
            </button>
          </div>
        )}
        <form className="modal-form" onSubmit={(e) => void create(e)}>
          <DataUseNotice />
          <Field label="Nome da integração">
            <input
              name="name"
              required
              minLength={2}
              maxLength={100}
              placeholder="Ex.: Sistema parceiro"
            />
          </Field>
          <div className="form-grid">
            <Field label="Usuário técnico (atendente)">
              <select name="user_id" required defaultValue="">
                <option value="" disabled>
                  Selecione um atendente ativo
                </option>
                {users.data
                  ?.filter((u) => u.is_active && u.role === "attendant")
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} · {u.email}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Validade em dias">
              <input
                name="days"
                type="number"
                min={1}
                max={365}
                defaultValue={90}
                required
              />
            </Field>
          </div>
          <p className="muted">
            Cadastre uma conta dedicada na Equipe. Suspender essa conta ou
            alterar sua função também interrompe o acesso da integração.
          </p>
          <fieldset>
            <legend>Permissões da chave</legend>
            <div className="modules-grid">
              {scopes.data?.map((s) => (
                <label className="module-option" key={s.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(s.id)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, s.id]
                          : selected.filter((id) => id !== s.id),
                      )
                    }
                  />
                  <span>
                    <strong>{s.name}</strong>
                    <small>{s.id}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="modal-actions">
            <button
              className="button primary"
              disabled={busy || !selected.length || !scopes.data}
            >
              {busy ? "Aguarde…" : "Criar chave de integração"}
            </button>
          </div>
        </form>
      </section>
      <section className="panel modal-form">
        <h2>Chaves emitidas</h2>
        {keys.data?.length === 0 && <p>Nenhuma chave emitida.</p>}
        {keys.data?.map((k) => (
          <article className="operation-card" key={k.id}>
            <h3>{k.name}</h3>
            <p>
              {k.user_name} ·{" "}
              {k.is_active && new Date(k.expires_at).getTime() > Date.now()
                ? "Ativa"
                : "Revogada ou expirada"}{" "}
              · expira em {new Date(k.expires_at).toLocaleDateString("pt-BR")}
            </p>
            <p className="muted">
              {k.scopes
                .map((id) => scopes.data?.find((s) => s.id === id)?.name || id)
                .join("; ")}
            </p>
            {k.is_active && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => void revoke(k)}
              >
                Revogar chave
              </button>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
