import { useEffect, useRef, useState } from "react";

declare const __APP_VERSION__: string;

export function AppUpdateNotice() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  const [latest, setLatest] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const registrationRef = useRef<ServiceWorkerRegistration | undefined>(undefined);
  useEffect(() => {
    let disposed = false;
    async function checkVersion() {
      if (!navigator.onLine) return;
      try {
        const response = await fetch(`/version.json?t=${Date.now()}`, { cache: "no-store", credentials: "omit" });
        const data = response.ok ? await response.json() : null;
        if (!disposed && typeof data?.version === "string" && /^[A-Za-z0-9._-]{1,100}$/.test(data.version)) setLatest(data.version !== __APP_VERSION__ ? data.version : "");
      } catch { /* Offline operation remains available. */ }
    }
    const tracked = new Set<ServiceWorkerRegistration>();
    const cleanups: (() => void)[] = [];
    function watch(registration: ServiceWorkerRegistration | undefined) {
      if (!registration || disposed || tracked.has(registration)) return;
      tracked.add(registration);
      registrationRef.current = registration;
      const check = () => {
        if (!disposed && registration.waiting) setWaiting(registration.waiting);
      };
      const found = () => {
        const worker = registration.installing;
        if (worker) {
          worker.addEventListener("statechange", check);
          cleanups.push(() => worker.removeEventListener("statechange", check));
        }
        check();
      };
      registration.addEventListener("updatefound", found);
      cleanups.push(() => registration.removeEventListener("updatefound", found));
      found();
      if (navigator.onLine) void registration.update().catch(() => {});
    }
    if ("serviceWorker" in navigator) {
      void navigator.serviceWorker.getRegistration().then(watch).catch(() => {});
      void navigator.serviceWorker.ready.then(watch).catch(() => {});
    }
    void checkVersion();
    window.addEventListener("focus", checkVersion);
    return () => { disposed = true; window.removeEventListener("focus", checkVersion); cleanups.forEach((cleanup) => cleanup()); };
  }, []);
  if (!waiting && !latest) return null;
  return <aside className="app-update-notice" aria-label="Atualização disponível"><span>Há uma nova versão do Rotafy. Salve o cadastro em andamento antes de atualizar.{error && <small>{error}</small>}</span><button type="button" className="button primary" disabled={busy} onClick={async () => {
    if (!window.confirm("A tela será recarregada. Você já salvou os dados em andamento?")) return;
    setBusy(true); setError("");
    try {
      const registration = registrationRef.current;
      const worker = registration?.waiting || waiting;
      if (worker) {
        navigator.serviceWorker.addEventListener("controllerchange", () => window.location.reload(), { once: true });
        worker.postMessage({ type: "SKIP_WAITING" });
      } else {
        if (!navigator.onLine) throw new Error("Conecte-se à internet para atualizar.");
        // Unregistering does not delete IndexedDB or local boarding records.
        if (registration) await registration.unregister();
        const url = new URL(window.location.href); url.searchParams.set("_v", latest);
        window.location.replace(url.href);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível atualizar."); setBusy(false); }
  }}>{busy ? "Atualizando…" : "Atualizar aplicativo"}</button></aside>;
}
