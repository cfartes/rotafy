import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, patch, post, type Company } from "./api";
import { Alert, Field } from "./components/ui";

type Trip = {
  id: string;
  name: string;
  is_published: boolean;
  status: string;
  package_id?: string | null;
};
type Key = { id: string; name: string; is_active: boolean; expires_at: string };
type Notice = {
  id: string;
  trip_name: string;
  group_size: number;
  source: string;
};
export function Sales({
  company,
  isAdmin,
}: {
  company: Company;
  isAdmin: boolean;
}) {
  const cache = useQueryClient();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState("");
  const [logoVersion, setLogoVersion] = useState(0);
  const trips = useQuery({
    queryKey: ["sales", "trips"],
    queryFn: () => api<Trip[]>("/trips"),
  });
  const keys = useQuery({
    queryKey: ["sales", "keys"],
    queryFn: () => api<Key[]>("/integrations/keys"),
    enabled: isAdmin,
  });
  const alerts = useQuery({
    queryKey: ["sales", "alerts"],
    queryFn: () => api<Notice[]>("/availability-alerts"),
    refetchInterval: 15000,
  });
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await cache.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  function createKey(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    void run(async () => {
      const key = await post<{ token: string }>("/integrations/keys", {
        name: data.get("name"),
        valid_days: Number(data.get("days")),
      });
      setSecret(key.token);
    });
  }
  function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    void run(async () => {
      await api("/company/logo", { method: "POST", body: data });
      setLogoVersion((v) => v + 1);
    });
  }
  return (
    <div className="modal-form">
      <h2>Página pública e integrações</h2>
      <p>
        Publique somente as viagens que deseja oferecer. Solicitações públicas
        bloqueiam lugares por 15 minutos e aguardam confirmação da agência.
      </p>
      <a
        className="button secondary"
        href={`/comprar/${company.slug}`}
        target="_blank"
        rel="noreferrer"
      >
        Abrir página pública
      </a>
      {(error || trips.error || keys.error || alerts.error) && (
        <Alert>
          {error || String(trips.error || keys.error || alerts.error)}
        </Alert>
      )}
      {isAdmin && (
        <section className="operation-card">
          <h3>Logo da agência</h3>
          <p>
            PNG ou JPEG, até 512 KB. A imagem será preparada para publicação.
          </p>
          <img
            key={logoVersion}
            src={`/api/v1/public/${company.slug}/logo?v=${logoVersion}`}
            alt="Logo da empresa"
            width="96"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <form onSubmit={upload}>
            <Field label="Arquivo do logo">
              <input
                type="file"
                name="file"
                accept="image/png,image/jpeg"
                required
              />
            </Field>
            <button className="button secondary" disabled={busy}>
              Enviar logo
            </button>
          </form>
          <button
            className="button secondary"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await post("/company/logo/remove", {});
                setLogoVersion((v) => v + 1);
              })
            }
          >
            Remover logo
          </button>
        </section>
      )}
      <section className="operation-card">
        <h3>Publicação das viagens</h3>
        {trips.data?.map((t) => (
          <div className="operation-card" key={t.id}>
            <strong>{t.name}</strong>
            <p>{t.is_published ? "Publicada" : "Privada"}</p>
            <button
              className="button secondary"
              disabled={
                busy ||
                (!t.is_published &&
                  (t.status !== "scheduled" ||
                    (company.operational_profile === "regular" &&
                      !!t.package_id)))
              }
              onClick={() =>
                run(() =>
                  patch(`/trips/${t.id}/publication`, {
                    is_published: !t.is_published,
                  }),
                )
              }
            >
              {t.is_published ? "Retirar da página" : "Publicar viagem"}
            </button>
            {t.is_published && (
              <a
                className="button secondary"
                href={`/comprar/${company.slug}/${t.id}`}
                target="_blank"
                rel="noreferrer"
              >
                Abrir oferta
              </a>
            )}
          </div>
        ))}
      </section>
      <section className="operation-card">
        <h3>Alertas de disponibilidade</h3>
        <p>
          Famílias que não encontraram um veículo com lugares suficientes para
          viajar juntas.
        </p>
        {alerts.data?.length === 0 && <p>Nenhum alerta pendente.</p>}
        {alerts.data?.map((a) => (
          <div key={a.id}>
            <p>
              {a.trip_name} · {a.group_size} passageiros ·{" "}
              {a.source === "public" ? "Página pública" : "Integração"}
            </p>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() =>
                run(() => post(`/availability-alerts/${a.id}/acknowledge`, {}))
              }
            >
              Marcar como visto
            </button>
          </div>
        ))}
      </section>
      {isAdmin && (
        <section className="operation-card">
          <h3>Integrações com sites externos</h3>
          <p>
            Use as chaves somente no servidor do site parceiro. Cada chave
            acessa apenas as reservas criadas por ela.
          </p>
          <form onSubmit={createKey}>
            <Field label="Nome da integração">
              <input name="name" required minLength={2} maxLength={100} />
            </Field>
            <Field label="Validade em dias">
              <input
                name="days"
                type="number"
                defaultValue={90}
                min={1}
                max={365}
                required
              />
            </Field>
            <button className="button primary" disabled={busy}>
              Criar chave
            </button>
          </form>
          {secret && (
            <Field label="Chave exibida uma única vez: copie e guarde com segurança">
              <textarea readOnly value={secret} />
            </Field>
          )}
          {keys.data?.map((k) => (
            <div key={k.id}>
              <p>
                {k.name} · {k.is_active ? "Ativa" : "Revogada"} · validade{" "}
                {new Date(k.expires_at).toLocaleDateString("pt-BR")}
              </p>
              {k.is_active && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm(`Revogar a chave ${k.name}?`))
                      void run(() =>
                        post(`/integrations/keys/${k.id}/revoke`, {}),
                      );
                  }}
                >
                  Revogar chave
                </button>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
