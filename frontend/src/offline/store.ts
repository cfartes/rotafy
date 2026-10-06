import Dexie, { type Table } from "dexie";
import { api, post, ApiError, type User } from "../api";

export type Presence = "waiting" | "onboard" | "alighted";
export type Passenger = {
  id: string;
  full_name: string;
  boarding: string;
  dropoff: string;
  status: Presence;
  version: number;
  pending?: boolean;
};
export type Manifest = {
  trip: { id: string; name: string; status: string };
  vehicle: { id: string; name: string; plate: string; capacity: number };
  leg: { id: string; origin: string; destination: string };
  passengers: Passenger[];
  counts: Record<Presence, number>;
  can_write: boolean;
};
type Operator = {
  id: string;
  company_id: string;
  full_name: string;
  role: string;
};
export type Prepared = Manifest & {
  operator: Operator;
  prepared_at: string;
  expires_at: string;
  tickets: { passenger_id: string; token_hash: string }[];
};
export type Snapshot = {
  id: string;
  owner: string;
  endpoint: string;
  data: Prepared;
};
export type Command = {
  operation_key: string;
  passenger_id: string;
  expected_version: number;
  action: "board" | "disembark" | "reverse";
  token?: string;
  device_id: string;
  captured_at: string;
  offline: boolean;
  expected_actor_id: string;
};
export type Queued = {
  seq?: number;
  operation_key: string;
  owner: string;
  manifest_id: string;
  payload: Command;
  status: "pending" | "conflict" | "rejected";
  message?: string;
};
class OfflineDatabase extends Dexie {
  snapshots!: Table<Snapshot, string>;
  queue!: Table<Queued, number>;
  meta!: Table<{ key: string; value: string }, string>;
  constructor() {
    super("rotafy-operational-v1");
    this.version(1).stores({
      snapshots: "id,owner",
      queue: "++seq,&operation_key,owner,manifest_id,status",
      meta: "key",
    });
  }
}
export const db = new OfflineDatabase();
export async function withOfflineLock<T>(work: () => Promise<T>): Promise<T> {
  return navigator.locks
    ? navigator.locks.request("rotafy-sync", work)
    : work();
}
const ownerOf = (user: { id: string; company_id: string | null }) =>
  `${user.company_id}:${user.id}`;
export async function currentOwner() {
  return (await db.meta.get("owner"))?.value;
}
export async function pendingCount() {
  return db.queue.count();
}
export async function clearOfflineCache() {
  await withOfflineLock(() =>
    db.transaction("rw", db.snapshots, db.queue, db.meta, async () => {
      if (await db.queue.count())
        throw new Error(
          "Há ações offline pendentes. Sincronize ou resolva os conflitos antes de sair ou limpar o dispositivo.",
        );
      await db.snapshots.clear();
      await db.meta.clear();
    }),
  );
}
export async function activateOfflineUser(user: User) {
  const next = ownerOf(user);
  await db.transaction("rw", db.snapshots, db.queue, db.meta, async () => {
    const current = await currentOwner();
    if (current && current !== next) {
      if (await db.queue.count())
        throw new Error(
          "Há ações pendentes de outro acesso neste dispositivo. Entre com o usuário original para sincronizá-las.",
        );
      await db.snapshots.clear();
    }
    await db.meta.put({ key: "owner", value: next });
  });
}

export async function prepareManifest(endpoint: string) {
  return withOfflineLock(() => prepareManifestUnlocked(endpoint));
}
async function prepareManifestUnlocked(endpoint: string) {
  if (!navigator.onLine)
    throw new Error("Prepare o manifesto enquanto houver conexão.");
  const result = await api<Prepared>(`${endpoint}/offline-manifest`);
  await activateOfflineUser({
    ...result.operator,
    company_id: result.operator.company_id,
    role: result.operator.role as User["role"],
    email: "",
    is_active: true,
  });
  const owner = ownerOf(result.operator);
  const id = `${owner}:${result.trip.id}:${result.vehicle.id}:${result.leg.id}`;
  await db.transaction("rw", db.snapshots, db.queue, async () => {
    if (await db.queue.where("manifest_id").equals(id).count())
      throw new Error(
        "Sincronize ou resolva as ações deste manifesto antes de prepará-lo novamente.",
      );
    await db.snapshots.put({ id, owner, endpoint, data: result });
  });
  if (navigator.storage?.persist)
    await navigator.storage.persist().catch(() => false);
  return id;
}

export function nextState(
  state: Presence,
  action: Command["action"],
): Presence | undefined {
  return (
    {
      "waiting:board": "onboard",
      "onboard:disembark": "alighted",
      "onboard:reverse": "waiting",
      "alighted:reverse": "onboard",
    } as Record<string, Presence>
  )[`${state}:${action}`];
}
export function projected(snapshot: Snapshot, queue: Queued[]) {
  return snapshot.data.passengers.map((original) => {
    let p = { ...original };
    for (const record of queue.filter((q) => q.payload.passenger_id === p.id)) {
      if (
        record.status !== "pending" ||
        record.payload.expected_version !== p.version
      )
        break;
      const status = nextState(p.status, record.payload.action);
      if (!status) break;
      p = { ...p, status, version: p.version + 1, pending: true };
    }
    return p;
  });
}
export async function enqueue(
  id: string,
  passenger: string,
  action: Command["action"],
  token?: string,
) {
  await db.transaction("rw", db.snapshots, db.queue, db.meta, async () => {
    const snapshot = await db.snapshots.get(id);
    if (!snapshot || snapshot.owner !== (await currentOwner()))
      throw new Error("Manifesto não pertence ao acesso ativo.");
    if (
      Date.parse(snapshot.data.expires_at) <= Date.now() ||
      !snapshot.data.can_write
    )
      throw new Error(
        "Preparação vencida ou acesso somente leitura. Conecte-se novamente.",
      );
    const queue = await db.queue.where("manifest_id").equals(id).sortBy("seq");
    if (
      queue.some(
        (q) => q.payload.passenger_id === passenger && q.status !== "pending",
      )
    )
      throw new Error(
        "Resolva o conflito ou a rejeição deste passageiro antes de registrar outra ação.",
      );
    const person = projected(snapshot, queue).find((p) => p.id === passenger);
    if (!person || !nextState(person.status, action))
      throw new Error("Ação incompatível com a situação local.");
    let device = (await db.meta.get("device"))?.value;
    if (!device) {
      device = crypto.randomUUID();
      await db.meta.put({ key: "device", value: device });
    }
    const payload: Command = {
      operation_key: crypto.randomUUID(),
      passenger_id: passenger,
      expected_version: person.version,
      action,
      device_id: device,
      captured_at: new Date().toISOString(),
      offline: !navigator.onLine,
      expected_actor_id: snapshot.data.operator.id,
      ...(token ? { token } : {}),
    };
    await db.queue.add({
      operation_key: payload.operation_key,
      owner: snapshot.owner,
      manifest_id: id,
      payload,
      status: "pending",
    });
  });
}
export async function offlineScan(snapshot: Snapshot, raw: string) {
  if (Date.parse(snapshot.data.expires_at) <= Date.now())
    throw new Error("Manifesto vencido. Conecte-se para atualizar.");
  let token = raw.trim();
  if (token.startsWith(location.origin + "/bilhete#"))
    token =
      new URLSearchParams(new URL(token).hash.slice(1)).get("token") || "";
  if (
    !new RegExp(
      `^bt\\.${snapshot.data.operator.company_id}\\.[A-Za-z0-9_-]{43}$`,
    ).test(token)
  )
    throw new Error("Bilhete inválido ou de outra empresa.");
  const hash = Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token)),
    ),
  )
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
  const ticket = snapshot.data.tickets.find((t) => t.token_hash === hash);
  if (!ticket)
    throw new Error("QR não consta neste veículo e trecho preparados.");
  return { passenger_id: ticket.passenger_id, token };
}

let syncing = false;
async function syncNow(id: string) {
  if (syncing) return;
  syncing = true;
  try {
    const snapshot = await db.snapshots.get(id);
    if (!snapshot) return;
    const user = await api<User>("/auth/me");
    if (
      ownerOf(user) !== snapshot.owner ||
      snapshot.owner !== (await currentOwner())
    )
      throw new Error(
        "Entre com o usuário que preparou este manifesto antes de sincronizar.",
      );
    const queue = await db.queue.where("manifest_id").equals(id).sortBy("seq");
    const blocked = new Set<string>();
    for (const record of queue) {
      const passenger = record.payload.passenger_id;
      if (record.status !== "pending") {
        blocked.add(passenger);
        continue;
      }
      if (blocked.has(passenger)) continue;
      try {
        const result = await post<{ status: Presence; version: number }>(
          `${snapshot.endpoint}/boarding`,
          record.payload,
        );
        await db.transaction("rw", db.snapshots, db.queue, async () => {
          const latest = await db.snapshots.get(id);
          if (latest) {
            const p = latest.data.passengers.find((p) => p.id === passenger);
            if (p && p.version <= result.version) {
              p.version = result.version;
              p.status = result.status;
            }
            await db.snapshots.put(latest);
          }
          await db.queue.delete(record.seq!);
        });
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) {
          const latest = await db.snapshots.get(id);
          if (latest) {
            latest.data.can_write = false;
            await db.snapshots.put(latest);
          }
        }
        if (
          !(e instanceof ApiError) ||
          e.status === 0 ||
          e.status >= 500 ||
          e.status === 401 ||
          e.status === 403
        )
          throw e;
        await db.queue.update(record.seq!, {
          status:
            e.status === 409 && e.code !== "trip_closed"
              ? "conflict"
              : "rejected",
          message: e.message,
        });
        blocked.add(passenger);
      }
    }
    // Uma versão nova só troca a base confirmada; as ações locais permanecem na fila.
    try {
      const data = await api<Prepared>(`${snapshot.endpoint}/offline-manifest`);
      await db.snapshots.put({ ...snapshot, data });
    } catch (e) {
      if (
        e instanceof ApiError &&
        (e.status === 404 || e.status === 403 || e.code === "trip_closed")
      ) {
        await db.transaction("rw", db.snapshots, db.queue, async () => {
          if (!(await db.queue.where("manifest_id").equals(id).count()))
            await db.snapshots.delete(id);
          else {
            const latest = await db.snapshots.get(id);
            if (latest) {
              latest.data.can_write = false;
              await db.snapshots.put(latest);
            }
          }
        });
      }
      throw e;
    }
  } finally {
    syncing = false;
  }
}
export async function synchronize(id: string) {
  if (!navigator.onLine)
    throw new Error(
      "Sem conexão. As ações continuam guardadas neste dispositivo.",
    );
  if (navigator.locks)
    return navigator.locks.request("rotafy-sync", () => syncNow(id));
  return syncNow(id);
}
export async function discardChain(record: Queued) {
  await withOfflineLock(() => discardChainUnlocked(record));
}
async function discardChainUnlocked(record: Queued) {
  await db.transaction("rw", db.queue, async () => {
    const rows = await db.queue
      .where("manifest_id")
      .equals(record.manifest_id)
      .toArray();
    await db.queue.bulkDelete(
      rows
        .filter(
          (q) =>
            q.payload.passenger_id === record.payload.passenger_id &&
            q.seq! >= record.seq!,
        )
        .map((q) => q.seq!),
    );
  });
}
export async function reapplyConflict(record: Queued) {
  await withOfflineLock(async () => {
    const snapshot = await db.snapshots.get(record.manifest_id);
    const current = await db.queue.get(record.seq!);
    if (!snapshot || current?.status !== "conflict")
      throw new Error("Este conflito já foi resolvido. Atualize a lista.");
    const user = await api<User>("/auth/me");
    if (ownerOf(user) !== snapshot.owner)
      throw new Error(
        "Entre com o usuário original para resolver este conflito.",
      );
    const data = await api<Prepared>(`${snapshot.endpoint}/offline-manifest`);
    const person = data.passengers.find(
      (p) => p.id === record.payload.passenger_id,
    );
    if (!person || !nextState(person.status, record.payload.action))
      throw new Error(
        "A situação atual não permite reaplicar esta ação. Mantenha o servidor e revise pela lista.",
      );
    await db.transaction("rw", db.snapshots, db.queue, db.meta, async () => {
      await discardChainUnlocked(record);
      await db.snapshots.put({ ...snapshot, data });
      await enqueue(
        snapshot.id,
        person.id,
        record.payload.action,
        record.payload.token,
      );
    });
  });
}
export async function removeSnapshot(id: string) {
  await withOfflineLock(() =>
    db.transaction("rw", db.queue, db.snapshots, async () => {
      if (await db.queue.where("manifest_id").equals(id).count())
        throw new Error(
          "Resolva as ações pendentes antes de remover o manifesto.",
        );
      await db.snapshots.delete(id);
    }),
  );
}
export async function pruneExpired() {
  await withOfflineLock(() =>
    db.transaction("rw", db.snapshots, db.queue, async () => {
      for (const snapshot of await db.snapshots.toArray())
        if (
          Date.parse(snapshot.data.expires_at) <= Date.now() &&
          !(await db.queue.where("manifest_id").equals(snapshot.id).count())
        )
          await db.snapshots.delete(snapshot.id);
    }),
  );
}
