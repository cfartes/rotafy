import { DataUseNotice } from "./../components/DataUseNotice";
import { useEffect, useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { Camera } from "../Boarding";
import { Alert, Field } from "../components/ui";
import {
  db,
  currentOwner,
  projected,
  enqueue,
  offlineScan,
  synchronize,
  discardChain,
  removeSnapshot,
  clearOfflineCache,
  reapplyConflict,
  pruneExpired,
  type Queued,
  type Command,
} from "./store";
import "../boarding.css";
import { decodeQrImage } from "../qr";
import { api, type User } from "../api";

const labels: Record<string, string> = {
  waiting: "Aguardando embarque",
  onboard: "A bordo",
  alighted: "Desembarcado",
};
const actionNames: Record<string, string> = {
  board: "Embarque",
  disembark: "Desembarque",
  reverse: "Reversão",
};
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível concluir.";
export function OfflineHub() {
  const [selected, setSelected] = useState(
    new URLSearchParams(location.search).get("manifest") || "",
  );
  const [online, setOnline] = useState(navigator.onLine);
  const [, setClock] = useState(Date.now());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [camera, setCamera] = useState(false);
  const [code, setCode] = useState("");
  const [qr, setQr] = useState<{ passenger_id: string; token: string } | null>(
    null,
  );
  const cache = useLiveQuery(async () => {
    const owner = await currentOwner();
    return {
      snapshots: owner
        ? await db.snapshots.where("owner").equals(owner).toArray()
        : [],
      queue: owner
        ? await db.queue.where("owner").equals(owner).sortBy("seq")
        : [],
    };
  }, []);
  const snapshot = cache?.snapshots.find((s) => s.id === selected);
  useEffect(() => {
    if (
      !online ||
      !cache ||
      selected ||
      cache.snapshots.length ||
      cache.queue.length
    )
      return;
    let active = true;
    void api<User>("/auth/me")
      .then((user) => {
        if (active && ["admin", "attendant", "nexus"].includes(user.role))
          window.location.replace(user.role === "nexus" ? "/nexus" : "/");
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [online, !!cache, selected, cache?.snapshots.length, cache?.queue.length]);
  const queue = cache?.queue.filter((q) => q.manifest_id === selected) || [];
  const expired =
    !!snapshot && Date.parse(snapshot.data.expires_at) <= Date.now();
  const passengers = snapshot ? projected(snapshot, queue) : [];
  const writable = snapshot?.data.can_write && !expired;
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function sync() {
    if (!selected) return;
    await run(() => synchronize(selected));
    setQr(null);
  }
  useEffect(() => {
    void pruneExpired().catch((e) => setError(message(e)));
    const clock = window.setInterval(() => {
      setClock(Date.now());
      void pruneExpired().catch((e) => setError(message(e)));
    }, 30000);
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      clearInterval(clock);
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  useEffect(() => {
    if (!online || !selected) return;
    const timer = window.setInterval(() => {
      if (!busy) void sync();
    }, 15000);
    return () => clearInterval(timer);
  }, [online, selected, busy]);
  useEffect(() => {
    setQr(null);
    setCamera(false);
  }, [selected]);
  async function action(
    passenger: string,
    value: Command["action"],
    token?: string,
  ) {
    if (
      value === "reverse" &&
      !window.confirm("Reverter a situação local deste passageiro?")
    )
      return;
    await run(() => enqueue(selected, passenger, value, token));
    setQr(null);
  }
  async function read(raw: string) {
    setCamera(false);
    if (!snapshot) return;
    await run(async () => {
      setQr(await offlineScan(snapshot, raw));
      setCode("");
    });
  }
  async function image(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      setError("Use uma imagem de até 5 MB.");
      return;
    }
    await run(async () => {
      const url = URL.createObjectURL(file);
      try {
        setQr(await offlineScan(snapshot!, await decodeQrImage(url)));
      } finally {
        URL.revokeObjectURL(url);
      }
    });
  }
  async function discard(record: Queued) {
    if (
      window.confirm(
        "Descartar esta ação local e as ações seguintes do mesmo passageiro? Registros já aceitos no servidor permanecem no histórico.",
      )
    )
      await run(() => discardChain(record));
  }
  async function reapply(record: Queued) {
    if (!snapshot || !online) return;
    if (
      !window.confirm(
        "Consultar a situação atual e reaplicar esta ação? As ações locais seguintes desse passageiro serão descartadas.",
      )
    )
      return;
    await run(() => reapplyConflict(record));
  }
  return (
    <main className="public-site">
      <div className="public-container offline-container">
        <div className="section-heading">
          <div>
            <p className="eyebrow">NEXUS ROTAFY · OPERAÇÃO LOCAL</p>
            <h1>Embarque offline</h1>
          </div>
          <a className="button secondary" href="/">
            Voltar ao painel / entrar
          </a>
        </div>
        <p className="offline-banner" role="status">
          {online ? "Conexão disponível" : "Sem conexão"} ·{" "}
          {cache?.queue.length || 0} ações aguardando sincronização ou revisão
        </p>
        {error && <Alert>{error}</Alert>}
        <p>
          Prepare cada veículo e trecho online. As ações locais só ficam
          confirmadas após a sincronização. Cancelamentos e alterações de outros
          aparelhos podem ainda não estar disponíveis neste dispositivo.
        </p>
        <Field label="Manifesto preparado">
          <select
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              history.replaceState(
                null,
                "",
                `/offline?manifest=${encodeURIComponent(e.target.value)}`,
              );
            }}
            disabled={busy}
          >
            <option value="">Escolha veículo e trecho</option>
            {cache?.snapshots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.data.trip.name} · {s.data.vehicle.name} · {s.data.leg.origin}{" "}
                → {s.data.leg.destination}
              </option>
            ))}
          </select>
        </Field>
        {!cache?.snapshots.length && (
          <p>
            Não há manifestos preparados para este acesso. Entre no painel
            enquanto estiver online para preparar a viagem.
          </p>
        )}
        {snapshot && (
          <>
            <p>
              {snapshot.data.operator.full_name} · {snapshot.data.vehicle.name}{" "}
              · {snapshot.data.leg.origin} → {snapshot.data.leg.destination}
            </p>
            <p className="muted">
              Preparado em{" "}
              {new Date(snapshot.data.prepared_at).toLocaleString("pt-BR")} ·
              validade local até{" "}
              {new Date(snapshot.data.expires_at).toLocaleString("pt-BR")}
            </p>
            <div className="boarding-actions">
              <button
                className="button primary"
                disabled={busy || !online}
                onClick={sync}
              >
                Sincronizar agora
              </button>
              <button
                className="button secondary"
                disabled={busy || queue.length > 0}
                onClick={() => {
                  if (window.confirm("Remover este manifesto do dispositivo?"))
                    void run(() => removeSnapshot(selected));
                }}
              >
                Remover manifesto local
              </button>
            </div>
            {expired ? (
              <Alert>
                A preparação expirou. Conecte-se e entre com o usuário original
                para sincronizar e renovar o manifesto. Novas ações locais estão
                bloqueadas.
              </Alert>
            ) : (
              <>
                <div className="boarding-counts">
                  {(["waiting", "onboard", "alighted"] as const).map(
                    (state) => (
                      <div key={state}>
                        <strong>
                          {passengers.filter((p) => p.status === state).length}
                        </strong>
                        <span>{labels[state]}</span>
                      </div>
                    ),
                  )}
                </div>
                {writable && (
                  <section className="operation-card">
                    <h2>Leitura de bilhete preparada</h2>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() => setCamera((v) => !v)}
                    >
                      {camera ? "Fechar câmera" : "Ler QR pela câmera"}
                    </button>
                    {camera && (
                      <Camera
                        onRead={(raw) => {
                          void read(raw);
                        }}
                        onError={(value) => {
                          setError(value);
                          setCamera(false);
                        }}
                      />
                    )}
                    <Field label="Leitura de QR por imagem">
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        disabled={busy}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void image(file);
                          e.target.value = "";
                        }}
                      />
                    </Field>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void read(code);
                      }}
                    >
                      <DataUseNotice />
                      <Field label="Código QR ou link do bilhete">
                        <textarea
                          maxLength={300}
                          value={code}
                          onChange={(e) => setCode(e.target.value)}
                          required
                          disabled={busy}
                        />
                      </Field>
                      <button className="button secondary" disabled={busy}>
                        Conferir bilhete offline
                      </button>
                    </form>
                    {qr && (
                      <div className="boarding-passenger">
                        <strong>
                          {
                            passengers.find((p) => p.id === qr.passenger_id)
                              ?.full_name
                          }
                        </strong>
                        <p>
                          Validado contra o manifesto preparado; confirmação
                          final na sincronização.
                        </p>
                        <button
                          className="button primary"
                          disabled={
                            busy ||
                            passengers.find((p) => p.id === qr.passenger_id)
                              ?.status !== "waiting"
                          }
                          onClick={() =>
                            action(qr.passenger_id, "board", qr.token)
                          }
                        >
                          Registrar embarque do QR local
                        </button>
                      </div>
                    )}
                  </section>
                )}
                <Field label="Buscar passageiro">
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </Field>
                <div className="boarding-passengers">
                  {passengers
                    .filter((p) =>
                      p.full_name
                        .toLocaleLowerCase()
                        .includes(search.toLocaleLowerCase()),
                    )
                    .map((p) => {
                      const problem = queue.find(
                        (q) =>
                          q.payload.passenger_id === p.id &&
                          q.status !== "pending",
                      );
                      return (
                        <article key={p.id} className="boarding-passenger">
                          <div>
                            <h3>{p.full_name}</h3>
                            <p>
                              {p.boarding} → {p.dropoff}
                            </p>
                            <span className={`boarding-state ${p.status}`}>
                              {labels[p.status]}
                            </span>
                            <p className="offline-state">
                              {problem
                                ? "Revisão necessária"
                                : p.pending
                                  ? "Pendente neste dispositivo"
                                  : "Confirmado no manifesto preparado"}
                            </p>
                          </div>
                          {writable && !problem && (
                            <div className="boarding-actions">
                              {p.status === "waiting" && (
                                <button
                                  className="button primary"
                                  disabled={busy}
                                  onClick={() => action(p.id, "board")}
                                >
                                  Embarcar localmente
                                </button>
                              )}
                              {p.status === "onboard" && (
                                <button
                                  className="button primary"
                                  disabled={busy}
                                  onClick={() => action(p.id, "disembark")}
                                >
                                  Desembarcar localmente
                                </button>
                              )}
                              {p.status !== "waiting" && (
                                <button
                                  className="button secondary"
                                  disabled={busy}
                                  onClick={() => action(p.id, "reverse")}
                                >
                                  Reverter localmente
                                </button>
                              )}
                            </div>
                          )}
                        </article>
                      );
                    })}
                </div>
              </>
            )}
            <section className="operation-card">
              <h2>Ações locais e conflitos</h2>
              {!queue.length && <p>Nenhuma ação pendente neste manifesto.</p>}
              {queue.map((q) => (
                <article key={q.operation_key} className="ticket-entry">
                  <strong>
                    {expired
                      ? "Passageiro do manifesto"
                      : snapshot.data.passengers.find(
                          (p) => p.id === q.payload.passenger_id,
                        )?.full_name || "Passageiro"}{" "}
                    · {actionNames[q.payload.action]}
                  </strong>
                  <p>
                    {q.status === "pending"
                      ? "Aguardando envio"
                      : q.status === "conflict"
                        ? "Conflito com o servidor"
                        : "Rejeitada pelo servidor"}
                  </p>
                  {q.message && <p>{q.message}</p>}
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => discard(q)}
                  >
                    {q.status === "pending"
                      ? "Descartar ação local"
                      : "Manter servidor"}
                  </button>
                  {q.status === "conflict" && (
                    <button
                      className="button secondary"
                      disabled={busy || !online}
                      onClick={() => reapply(q)}
                    >
                      Reaplicar ação após revisão
                    </button>
                  )}
                </article>
              ))}
            </section>
          </>
        )}
        <button
          className="button secondary"
          disabled={busy || (cache?.queue.length || 0) > 0}
          onClick={() => {
            if (
              window.confirm(
                "Limpar todos os manifestos e dados operacionais locais?",
              )
            )
              void run(clearOfflineCache);
          }}
        >
          Limpar dados deste dispositivo
        </button>
        <p className="muted">
          Use um dispositivo protegido. A interface funciona offline após
          preparação; a sincronização exige conexão e login válido do mesmo
          usuário.
        </p>
      </div>
    </main>
  );
}
