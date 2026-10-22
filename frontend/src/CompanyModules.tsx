import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Company } from "./api";
import { Alert, Field } from "./components/ui";

type Module = {
  id: string;
  name: string;
  description: string;
  requires: string[];
};
type Configuration = { enabled_modules: string[]; version: number };
type Catalog = { modules: Module[]; presets: Record<string, string[]> };

export function CompanyModules({ companies }: { companies: Company[] }) {
  const cache = useQueryClient();
  const [companyId, setCompanyId] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const catalog = useQuery({
    queryKey: ["module-catalog"],
    queryFn: () => api<Catalog>("/nexus/modules"),
  });
  const config = useQuery({
    queryKey: ["company-modules", companyId],
    queryFn: () => api<Configuration>(`/nexus/companies/${companyId}/modules`),
    enabled: !!companyId,
  });
  useEffect(() => {
    if (config.data) {
      setChosen(config.data.enabled_modules);
      setVersion(config.data.version);
    }
    setError("");
  }, [config.data, companyId]);
  function toggle(id: string, active: boolean) {
    const next = new Set(chosen);
    const modules = catalog.data?.modules || [];
    function enable(key: string) {
      if (next.has(key)) return;
      next.add(key);
      modules.find((m) => m.id === key)?.requires.forEach(enable);
    }
    if (active) enable(id);
    else {
      next.delete(id);
      for (let pass = 0; pass < modules.length; pass++)
        modules.forEach((m) => {
          if (m.requires.some((r) => !next.has(r))) next.delete(m.id);
        });
    }
    setChosen([...next]);
    setSaved(false);
  }
  async function save() {
    if (
      !window.confirm(
        "Aplicar os módulos selecionados? Áreas desabilitadas deixarão de funcionar também pela API. Desabilitar WhatsApp desconecta o número e descarta mensagens operacionais pendentes. O histórico será preservado.",
      )
    )
      return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const result = await api<Configuration>(
        `/nexus/companies/${companyId}/modules`,
        {
          method: "PUT",
          body: JSON.stringify({
            expected_version: version,
            enabled_modules: chosen,
          }),
        },
      );
      setVersion(result.version);
      setChosen(result.enabled_modules);
      setSaved(true);
      await cache.invalidateQueries({
        queryKey: ["company-modules", companyId],
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel modal-form">
      <h2>Módulos por empresa</h2>
      <p>
        Configure o que cada empresa utiliza. Perfis de usuário e
        Turismo/Regular continuam limitando as funções permitidas. Financeiro da
        assinatura, contrato, acesso e ajuda permanecem disponíveis.
      </p>
      <Field label="Empresa">
        <select
          value={companyId}
          onChange={(e) => {
            setCompanyId(e.target.value);
            setSaved(false);
          }}
          disabled={busy}
        >
          <option value="">Selecione uma empresa</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.trade_name} · {c.slug}
            </option>
          ))}
        </select>
      </Field>
      {(error || catalog.error || config.error) && (
        <Alert>{error || String(catalog.error || config.error)}</Alert>
      )}
      {companyId && config.isPending && (
        <p role="status">Carregando módulos…</p>
      )}
      {companyId && config.data && catalog.data && (
        <>
          <div className="modal-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setChosen(catalog.data!.presets.full);
                setSaved(false);
              }}
            >
              Sistema completo
            </button>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setChosen(catalog.data!.presets.integrated);
                setSaved(false);
              }}
            >
              WhatsApp e embarque integrado
            </button>
          </div>
          <p className="muted">
            O perfil integrado mantém equipe, veículos e viagens como base
            operacional dos dados recebidos do parceiro. A venda continua no
            sistema dele. Dependências são ajustadas ao marcar ou desmarcar um
            módulo.
          </p>
          <div className="modules-grid">
            {catalog.data.modules.map((m) => (
              <label className="module-option" key={m.id}>
                <input
                  type="checkbox"
                  checked={chosen.includes(m.id)}
                  onChange={(e) => toggle(m.id, e.target.checked)}
                  disabled={busy}
                />
                <span>
                  <strong>{m.name}</strong>
                  <small>{m.description}</small>
                  {m.requires.length > 0 && (
                    <small>
                      Requer:{" "}
                      {m.requires
                        .map(
                          (id) =>
                            catalog.data!.modules.find((x) => x.id === id)
                              ?.name,
                        )
                        .join(", ")}
                      .
                    </small>
                  )}
                </span>
              </label>
            ))}
          </div>
          {saved && (
            <p role="status">
              Módulos atualizados. A empresa receberá as permissões na próxima
              consulta de sessão.
            </p>
          )}
          <div className="modal-actions">
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void save()}
            >
              {busy ? "Salvando…" : "Salvar módulos"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
