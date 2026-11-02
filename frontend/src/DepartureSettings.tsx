import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Policy = { early_start_enabled: boolean; early_start_minutes: number };

function Form({ initial }: { initial: Policy }) {
  const cache = useQueryClient();
  const [policy, setPolicy] = useState(initial), [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setSaved(false);
    try { await api("/company/operation-settings", { method: "PUT", body: JSON.stringify(policy) }); await cache.invalidateQueries({ queryKey: ["departure-settings"] }); setSaved(true); }
    catch (e) { setError(e instanceof Error ? e.message : "Não foi possível salvar."); }
    finally { setBusy(false); }
  }
  return <form className="operation-card modal-form" onSubmit={save}>
    <h2>Início das viagens</h2>
    <label><input type="checkbox" checked={policy.early_start_enabled} onChange={e => setPolicy({ ...policy, early_start_enabled: e.target.checked, early_start_minutes: Number.isInteger(policy.early_start_minutes) && policy.early_start_minutes >= 1 && policy.early_start_minutes <= 1440 ? policy.early_start_minutes : initial.early_start_minutes })} />Iniciar viagem antecipada</label>
    <Field label="Antecedência máxima para iniciar (minutos)"><input type="number" min="1" max="1440" step="1" required disabled={!policy.early_start_enabled} value={policy.early_start_minutes} onChange={e => setPolicy({ ...policy, early_start_minutes: Number(e.target.value) })} /></Field>
    <p>{policy.early_start_enabled ? `Motoristas e guias poderão iniciar o trecho até ${policy.early_start_minutes} minutos antes da saída prevista.` : "Motoristas e guias só poderão iniciar no horário previsto da saída."} O manifesto continua disponível para consulta. No APK, sincronize para atualizar essa regra. A agenda do motorista continua restrita ao dia da viagem.</p>
    {error && <Alert>{error}</Alert>}{saved && <p role="status">Regra de início salva.</p>}
    <button className="button primary" disabled={busy}>Salvar regra de início</button>
  </form>;
}

export function DepartureSettings() {
  const query = useQuery({ queryKey: ["departure-settings"], queryFn: () => api<Policy>("/company/operation-settings") });
  return <>{query.error && <Alert>Não foi possível carregar a regra de início.</Alert>}{query.data && <Form initial={query.data} />}</>;
}
