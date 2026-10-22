import type { User } from "./api";
import { useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";

// Older cached sessions have no entitlements until the next online refresh.
export const hasModule = (user: Pick<User, "enabled_modules">, id: string) =>
  user.enabled_modules == null || user.enabled_modules.includes(id);

export function useModules() {
  const cache = useQueryClient();
  const user = useSyncExternalStore(
    (callback) => cache.getQueryCache().subscribe(callback),
    () => cache.getQueryData<User | null>(["session"]),
  );
  return (id: string) => hasModule(user || {}, id);
}

export const menuModule: Record<string, string> = {
  directory: "team",
  vehicles: "fleet",
  routes: "routes",
  packages: "packages",
  operations: "trips",
  tracking: "tracking",
  "ticket-sales": "sales",
  allocations: "trips",
  passengers: "sales",
  sales: "sales",
  reports: "reports",
  whatsapp: "whatsapp",
  "whatsapp-chat": "whatsapp",
  nps: "whatsapp",
  integrations: "integrations",
};
