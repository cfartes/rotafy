import { useEffect, useState } from "react";

export function AppUpdateNotice() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    let disposed = false;
    const tracked = new Set<ServiceWorkerRegistration>();
    const cleanups: (() => void)[] = [];
    function watch(registration: ServiceWorkerRegistration | undefined) {
      if (!registration || disposed || tracked.has(registration)) return;
      tracked.add(registration);
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
    void navigator.serviceWorker.getRegistration().then(watch).catch(() => {});
    void navigator.serviceWorker.ready.then(watch).catch(() => {});
    return () => { disposed = true; cleanups.forEach((cleanup) => cleanup()); };
  }, []);
  if (!waiting) return null;
  return <aside className="app-update-notice" aria-label="Atualização disponível"><span>Há uma nova versão do Rotafy. Salve o cadastro em andamento antes de atualizar.</span><button type="button" className="button primary" onClick={() => {
    if (!window.confirm("A tela será recarregada. Você já salvou os dados em andamento?")) return;
    navigator.serviceWorker.addEventListener("controllerchange", () => window.location.reload(), { once: true });
    waiting.postMessage({ type: "SKIP_WAITING" });
  }}>Atualizar aplicativo</button></aside>;
}
