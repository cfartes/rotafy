import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { PasswordInput } from "./components/PasswordInput";
import { Alert, Field } from "./components/ui";

type Configuration = { enabled: boolean; monthly_limit: number; used: number; key_configured: boolean; version: number; optimization_enabled?: boolean; routes_enabled?: boolean; routes_limit?: number; routes_used?: number; stop_minutes?: number };

export function GeocodingSettings() {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["geocoding-settings"], queryFn: () => api<Configuration>("/nexus/geocoding") });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  return <section className="operation-card modal-form"><h2>Localização automática de embarques</h2>
    <p>Converte endereços em coordenadas pelo Google Maps, em segundo plano. Use a chave de backend restrita ao IP da VPS. Habilite a Geocoding API e, para previsão de chegada, a Routes API nas restrições da chave. Não use a chave web ou Android.</p>
    {query.error && <Alert>Não foi possível carregar a configuração.</Alert>}
    {query.data && <form key={query.data.version} className="modal-form" onSubmit={async event => {
      event.preventDefault(); const form = new FormData(event.currentTarget); const key = String(form.get("api_key") || "").trim();
      setBusy(true); setError(""); setNotice("");
      try {
        await api("/nexus/geocoding", { method: "PUT", body: JSON.stringify({ expected_version: query.data!.version, enabled: form.has("enabled"), monthly_limit: Number(form.get("monthly_limit")), ...(key ? { api_key: key } : {}), clear_key: form.has("clear_key"), optimization_enabled: form.has("optimization_enabled"), routes_enabled: form.has("routes_enabled"), routes_limit: Number(form.get("routes_limit")), stop_minutes: Number(form.get("stop_minutes")) }) });
        await cache.invalidateQueries({ queryKey: ["geocoding-settings"] }); setNotice("Configuração salva. Os endereços serão processados automaticamente.");
      } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível salvar."); } finally { setBusy(false); }
    }}>
      <label><input type="checkbox" name="enabled" defaultChecked={query.data.enabled} />Ativar localização automática</label>
      <Field label="Chave Google Geocoding do backend"><PasswordInput name="api_key" autoComplete="new-password" /></Field>
      <p>{query.data.key_configured ? "Chave cadastrada. Deixe vazio para mantê-la." : "Nenhuma chave cadastrada."}</p>
      <label><input type="checkbox" name="clear_key" />Remover a chave cadastrada</label>
      <Field label="Limite mensal de consultas de todas as empresas"><input name="monthly_limit" type="number" min="1" max="1000000" step="1" required defaultValue={query.data.monthly_limit} /></Field>
      <p>Consultas neste mês: {query.data.used}. O limite é global do Rotafy e inclui tentativas com erro. Ao atingir o limite, novas consultas aguardam o próximo mês (UTC). Configure também cotas no Google Cloud; o app não contabiliza uso externo.</p>
      <h3>Previsão de chegada no aviso de proximidade</h3>
      <label><input type="checkbox" name="routes_enabled" defaultChecked={query.data.routes_enabled ?? false} />Incluir tempo estimado de chegada pelo Google Maps</label>
      <label><input type="checkbox" name="optimization_enabled" defaultChecked={query.data.optimization_enabled ?? false} />Calcular sequência otimizada dos hotéis e casas antes da viagem</label>
      <p>A otimização preserva os pontos fixos e horários cadastrados. Reorganiza somente locais personalizados dentro do mesmo segmento e da mesma operação (embarque ou desembarque), sem inverter embarque e desembarque. Usa o mesmo limite de consultas de rotas. Sincronize o APK antes de iniciar.</p>
      <Field label="Limite mensal de consultas de rotas"><input name="routes_limit" type="number" min="1" max="1000000" step="1" required defaultValue={query.data.routes_limit ?? 9000} /></Field>
      <Field label="Minutos previstos de atendimento em cada parada anterior"><input name="stop_minutes" type="number" min="0" max="30" step="1" required defaultValue={query.data.stop_minutes ?? 2} /></Field>
      <p>Consultas de rotas neste mês: {query.data.routes_used ?? 0}. Usa trânsito e a sequência de pontos do motorista. O tempo de atendimento é uma margem estimada por parada. A Routes API tem consumo próprio; configure cotas no Google Cloud. Sem uma previsão válida, o aviso de proximidade continua sem tempo estimado.</p>
      {error && <Alert>{error}</Alert>}{notice && <p role="status">{notice}</p>}
      <button className="button primary" disabled={busy}>Salvar localização automática</button>
    </form>}
  </section>;
}
