import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { Alert, Field } from "./components/ui";
import { publishApk } from "./mobileReleaseUpload";

type Release = { package_id: string; version: string; build: number; sha256: string; download_url: string; published_at: string };
export function MobileRelease() {
  const cache = useQueryClient();
  const releases = useQuery({ queryKey: ["mobile-release"], queryFn: () => api<Release[]>("/nexus/mobile-release") });
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [progress, setProgress] = useState(0);
  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice("");
    const file = new FormData(event.currentTarget).get("apk");
    if (!(file instanceof File) || !file.size) return;
    setBusy(true); setProgress(0);
    try {
      const release = await publishApk<Release>(file, setProgress);
      setNotice(`Versão ${release.version} publicada. Aplicativos com o verificador de versão exibirão a opção de atualização quando houver uma compilação mais nova.`);
      await cache.invalidateQueries({ queryKey: ["mobile-release"] });
    } catch (e) { setError((e instanceof Error ? e.message : "Não foi possível publicar o APK.") + (e instanceof ApiError ? ` [HTTP ${e.status}${e.requestId ? ` · referência ${e.requestId}` : ""}]` : "")); } finally { setBusy(false); await cache.invalidateQueries({ queryKey: ["mobile-release"] }); }
  }
  return <section className="operation-card modal-form"><h2>Atualizações do aplicativo Android</h2><p>Publique o APK release assinado com a mesma chave do aplicativo instalado. A versão e a compilação são identificadas no arquivo. A atualização é instalada por cima, preservando os dados locais.</p>
    {error && <Alert>{error}</Alert>}{notice && <p role="status">{notice}</p>}
    {busy && <div role="status"><progress value={progress} max={100} aria-label="Envio do APK" /><p>{progress === 100 ? "Arquivo enviado. Validando e publicando a versão…" : `Enviando APK: ${progress}%`}</p><small>Mantenha esta página aberta até a confirmação da publicação.</small></div>}
    {releases.data?.map?.((r) => <div key={r.package_id}><strong>Versão disponível: {r.version} · compilação {r.build}</strong><p className="muted">Publicada em {new Date(r.published_at).toLocaleString("pt-BR")}</p><a href={r.download_url} className="button secondary">Baixar APK disponível</a><p className="muted contract-hash">SHA-256: {r.sha256}</p></div>)}
    <form onSubmit={publish} className="modal-form"><Field label="Novo APK Android"><input name="apk" type="file" accept=".apk" required disabled={busy} /></Field><button className="button primary" disabled={busy}>{busy ? "Publicando APK…" : "Publicar atualização Android"}</button></form>
  </section>;
}
