import { api, ApiError } from "./api";

async function retry<T>(path: string, options: RequestInit): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try { return await api<T>(path, { ...options, signal: AbortSignal.timeout(45000) }); }
    catch (error) {
      if (!(error instanceof ApiError) || attempt >= 2 || ![0,408,500,502,503,504].includes(error.status)) throw error;
      await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
    }
  }
}

export async function publishApk<T>(file: File, progress: (percent: number) => void): Promise<T> {
  if (!file.size || file.size > 150 * 1024 * 1024) throw new Error("Selecione um APK de até 150 MB.");
  const upload = await api<{ id: string; chunk_bytes: number }>("/nexus/mobile-release/uploads", { method: "POST", body: JSON.stringify({ size_bytes: file.size }) });
  if (!/^[a-f0-9-]{36}$/.test(upload.id) || !Number.isInteger(upload.chunk_bytes) || upload.chunk_bytes < 1 || upload.chunk_bytes > 512 * 1024) throw new Error("O servidor não preparou o envio corretamente. Atualize a página e tente novamente.");
  let offset = 0;
  while (offset < file.size) {
    const end = Math.min(file.size, offset + upload.chunk_bytes);
    const result = await retry<{ offset: number }>(`/nexus/mobile-release/uploads/${upload.id}?offset=${offset}`, {
      method: "PUT", body: file.slice(offset, end), headers: { "Content-Type": "application/octet-stream" },
    });
    if (result.offset !== end) throw new Error("O servidor recebeu uma quantidade inesperada de dados. Reinicie a publicação.");
    offset = result.offset;
    progress(Math.floor(offset * 100 / file.size));
  }
  return retry<T>(`/nexus/mobile-release/uploads/${upload.id}/complete`, { method: "POST" });
}
