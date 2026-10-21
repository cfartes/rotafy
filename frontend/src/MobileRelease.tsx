import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";

type Release = { package_id: string; version: string; build: number; sha256: string; download_url: string; published_at: string };
export function MobileRelease() {
  const cache = useQueryClient();
  const releases = useQuery({ queryKey: ["mobile-release"], queryFn: () => api<Release[]>("/nexus/mobile-release") });
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice("");
    const file = new FormData(event.currentTarget).get("apk");
    if (!(file instanceof File) || !file.size) return;
    setBusy(true);
    try {
      const release = await api<Release>("/nexus/mobile-release", { method: "PUT", body: file, headers: { "Content-Type": "application/vnd.android.package-archive" }, signal: AbortSignal.timeout(180000) });
      setNotice(`Versão ${release.version} publicada. Aplicativos com o verificador de versão exibirão a opção de atualização quando houver uma compilação mais nova.`);
      await cache.invalidateQueries({ queryKey: ["mobile-release"] });
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível publicar o APK."); } finally { setBusy(false); }
  }
  return <section className="operation-card modal-form"><h2>Atualizações do aplicativo Android</h2><p>Publique o APK release assinado com a mesma chave do aplicativo instalado. A versão e a compilação são identificadas no arquivo. A atualização é instalada por cima, preservando os dados locais.</p>
    {error && <Alert>{error}</Alert>}{notice && <p role="status">{notice}</p>}
    {releases.data?.map?.((r) => <div key={r.package_id}><strong>Versão disponível: {r.version} · compilação {r.build}</strong><p className="muted">Publicada em {new Date(r.published_at).toLocaleString("pt-BR")}</p><a href={r.download_url} className="button secondary">Baixar APK disponível</a><p className="muted contract-hash">SHA-256: {r.sha256}</p></div>)}
    <form onSubmit={publish} className="modal-form"><Field label="Novo APK Android"><input name="apk" type="file" accept=".apk" required disabled={busy} /></Field><button className="button primary" disabled={busy}>{busy ? "Publicando APK…" : "Publicar atualização Android"}</button></form>
  </section>;
}
