import { DataUseNotice } from "./components/DataUseNotice";
import { ticketToken } from "./ticketLinks";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IScannerControls } from "@zxing/browser";
import { api, post, ApiError } from "./api";
import { Alert, Field } from "./components/ui";
import "./boarding.css";
import { decodeQrImage } from "./qr";

type Passenger = {
  id: string;
  full_name: string;
  boarding: string;
  dropoff: string;
  status: string;
  version: number;
};
type Manifest = {
  trip: { name: string; status: string };
  vehicle: { name: string; plate: string; capacity: number };
  leg: { origin: string; destination: string };
  passengers: Passenger[];
  counts: { waiting: number; onboard: number; alighted: number };
  can_write: boolean;
};
type Command = {
  operation_key: string;
  passenger_id: string;
  expected_version: number;
  action: string;
  token?: string;
};
const labels: Record<string, string> = {
  waiting: "Aguardando embarque",
  onboard: "A bordo",
  alighted: "Desembarcado",
};
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível concluir.";

export function Camera({
  onRead,
  onError,
}: {
  onRead: (value: string) => void;
  onError: (value: string) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const callbacks = useRef({ onRead, onError });
  callbacks.current = { onRead, onError };
  useEffect(() => {
    const preview = video.current!;
    let active = true;
    let controls: IScannerControls | undefined;
    let found = false;
    void import("@zxing/browser")
      .then(({ BrowserQRCodeReader }) => {
        if (!active) return;
        return new BrowserQRCodeReader().decodeFromConstraints(
          { video: { facingMode: { ideal: "environment" } }, audio: false },
          preview,
          (result, _error, controller) => {
            if (result && active && !found) {
              found = true;
              controller.stop();
              callbacks.current.onRead(result.getText());
            }
          },
        );
      })
      .then((controller) => {
        controls = controller;
        if (!active || found) controller?.stop();
      })
      .catch(() => {
        if (active)
          callbacks.current.onError(
            "Não foi possível abrir a câmera. Permita o acesso, use HTTPS ou faça a leitura por imagem/lista.",
          );
      });
    return () => {
      active = false;
      controls?.stop();
      const stream = preview.srcObject;
      if (stream instanceof MediaStream)
        stream.getTracks().forEach((track) => track.stop());
    };
  }, []);
  return (
    <video
      ref={video}
      className="boarding-camera"
      autoPlay
      muted
      playsInline
      aria-label="Câmera para leitura de QR"
    />
  );
}

export function Boarding({
  tripId,
  allocationId,
  legId,
  onBack,
}: {
  tripId: string;
  allocationId: string;
  legId: string;
  onBack: () => void;
}) {
  const endpoint = `/trips/${tripId}/vehicles/${allocationId}/legs/${legId}`;
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [camera, setCamera] = useState(false);
  const [code, setCode] = useState("");
  const [selection, setSelection] = useState<{
    passenger_id: string;
    full_name: string;
    boarding_status: string;
    version: number;
    token: string;
  } | null>(null);
  const [retry, setRetry] = useState<Command | null>(null);
  const manifest = useQuery({
    queryKey: ["boarding", tripId, allocationId, legId],
    queryFn: () => api<Manifest>(`${endpoint}/manifest`),
    refetchInterval: 10000,
  });
  const history = useQuery({
    queryKey: ["boarding-history", tripId, allocationId, legId],
    queryFn: () =>
      api<
        {
          id: string;
          full_name: string;
          actor_name: string;
          action: string;
          created_at: string;
        }[]
      >(`${endpoint}/boarding-history`),
    refetchInterval: 10000,
  });
  async function read(raw: string) {
    setCamera(false);
    setPending(true);
    setError("");
    setSelection(null);
    try {
      const token = ticketToken(raw);
      const result = await post<{
        passenger_id: string;
        full_name: string;
        boarding_status: string;
        version: number;
      }>(`${endpoint}/scan`, { token });
      setSelection({ ...result, token });
      setCode("");
      await manifest.refetch();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  async function scanFile(file: File) {
    setPending(true);
    setError("");
    const url = URL.createObjectURL(file);
    try {
      await read(await decodeQrImage(url));
    } catch {
      setError(
        "Não foi possível ler um QR nesta imagem. Tente outra imagem ou use a lista.",
      );
    } finally {
      URL.revokeObjectURL(url);
      setPending(false);
    }
  }
  async function send(payload: Command) {
    setPending(true);
    setError("");
    try {
      await post(`${endpoint}/boarding`, payload);
      setRetry(null);
      setSelection(null);
      await manifest.refetch();
      await history.refetch();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        setRetry(payload);
        setError(
          "A resposta não chegou. Tente novamente a mesma operação antes de registrar outra ação.",
        );
      } else {
        setRetry(null);
        setSelection(null);
        setError(message(e));
        await manifest.refetch();
      }
    } finally {
      setPending(false);
    }
  }
  function action(passenger: Passenger, value: string, token?: string) {
    if (
      value === "reverse" &&
      !window.confirm(`Reverter a última situação de ${passenger.full_name}?`)
    )
      return;
    void send({
      operation_key: crypto.randomUUID(),
      passenger_id: passenger.id,
      expected_version: passenger.version,
      action: value,
      ...(token ? { token } : {}),
    });
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    void read(code);
  }
  const data = manifest.data;
  const disabled = pending || !!retry;
  async function prepare() {
    setPending(true);
    setError("");
    try {
      const { prepareManifest } = await import("./offline/store");
      const id = await prepareManifest(endpoint);
      window.location.assign(`/offline?manifest=${encodeURIComponent(id)}`);
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="boarding-page">
      <button className="button secondary" onClick={onBack} disabled={disabled}>
        Voltar às viagens
      </button>
      {(error || manifest.error) && (
        <Alert>{error || message(manifest.error)}</Alert>
      )}
      {retry && (
        <button
          className="button primary"
          disabled={pending}
          onClick={() => send(retry)}
        >
          Tentar novamente a mesma operação
        </button>
      )}
      {!data ? (
        <p>Carregando manifesto…</p>
      ) : (
        <>
          <div className="section-heading">
            <div>
              <p className="eyebrow">OPERAÇÃO DE EMBARQUE</p>
              <h2>{data.trip.name}</h2>
              <p>
                {data.vehicle.name} · {data.vehicle.plate} · {data.leg.origin} →{" "}
                {data.leg.destination}
              </p>
            </div>
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => manifest.refetch()}
            >
              Atualizar lista
            </button>
          </div>
          <div className="boarding-counts" aria-live="polite">
            <div>
              <strong>{data.counts.waiting}</strong>
              <span>Aguardando</span>
            </div>
            <div>
              <strong>{data.counts.onboard}</strong>
              <span>A bordo</span>
            </div>
            <div>
              <strong>{data.counts.alighted}</strong>
              <span>Desembarcados</span>
            </div>
          </div>
          <p className="muted">
            Somente reservas confirmadas. Esta etapa exige conexão; alterações
            aparecem após confirmação do servidor.
          </p>
          <button
            className="button secondary"
            disabled={disabled}
            onClick={prepare}
          >
            Preparar para uso offline
          </button>
          {data.can_write ? (
            <section className="operation-card">
              <h3>Leitura de bilhete</h3>
              <button
                className="button secondary"
                disabled={disabled}
                onClick={() => {
                  setCamera((v) => !v);
                  setSelection(null);
                }}
              >
                {camera ? "Fechar câmera" : "Ler QR pela câmera"}
              </button>
              {camera && (
                <Camera
                  onRead={(value) => {
                    void read(value);
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
                  disabled={disabled}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      if (file.size > 5 * 1024 * 1024)
                        setError("Use uma imagem de até 5 MB.");
                      else void scanFile(file);
                    }
                    e.target.value = "";
                  }}
                />
              </Field>
              <form onSubmit={submit}>
                <DataUseNotice purpose="validar e registrar o embarque e o desembarque dos passageiros" />
                <Field label="Código QR ou link do bilhete">
                  <textarea
                    value={code}
                    maxLength={300}
                    onChange={(e) => setCode(e.target.value)}
                    required
                    disabled={disabled}
                  />
                </Field>
                <button className="button secondary" disabled={disabled}>
                  Conferir bilhete
                </button>
              </form>
              {selection && (
                <article className="boarding-passenger">
                  <h3>{selection.full_name}</h3>
                  <p>{labels[selection.boarding_status]}</p>
                  {selection.boarding_status === "waiting" && (
                    <button
                      className="button primary"
                      disabled={disabled}
                      onClick={() =>
                        action(
                          {
                            id: selection.passenger_id,
                            full_name: selection.full_name,
                            status: selection.boarding_status,
                            version: selection.version,
                            boarding: "",
                            dropoff: "",
                          },
                          "board",
                          selection.token,
                        )
                      }
                    >
                      Confirmar embarque do QR
                    </button>
                  )}
                </article>
              )}
            </section>
          ) : (
            <p>
              Consulta da operação. Seu perfil ou a situação da viagem não
              permite registrar ações.
            </p>
          )}
          <Field label="Buscar passageiro">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Nome do passageiro"
            />
          </Field>
          <div className="boarding-passengers">
            {data.passengers
              .filter((p) =>
                p.full_name
                  .toLocaleLowerCase()
                  .includes(search.toLocaleLowerCase()),
              )
              .map((p) => (
                <article key={p.id} className="boarding-passenger">
                  <div>
                    <h3>{p.full_name}</h3>
                    <p>
                      {p.boarding} → {p.dropoff}
                    </p>
                    <span className={`boarding-state ${p.status}`}>
                      {labels[p.status]}
                    </span>
                  </div>
                  {data.can_write && (
                    <div className="boarding-actions">
                      {p.status === "waiting" && (
                        <button
                          className="button primary"
                          disabled={disabled}
                          onClick={() => action(p, "board")}
                        >
                          Embarcar
                        </button>
                      )}
                      {p.status === "onboard" && (
                        <button
                          className="button primary"
                          disabled={disabled}
                          onClick={() => action(p, "disembark")}
                        >
                          Desembarcar
                        </button>
                      )}
                      {p.status !== "waiting" && (
                        <button
                          className="button secondary"
                          disabled={disabled}
                          onClick={() => action(p, "reverse")}
                        >
                          Reverter
                        </button>
                      )}
                    </div>
                  )}
                </article>
              ))}
          </div>
          {!data.passengers.length && (
            <p className="empty-state">
              Nenhum passageiro confirmado neste veículo e trecho.
            </p>
          )}
          <details className="operation-card">
            <summary>Histórico de presença</summary>
            {history.error && <Alert>{message(history.error)}</Alert>}
            {history.data?.map((h) => (
              <p key={h.id}>
                {h.full_name} ·{" "}
                {
                  (
                    {
                      board: "Embarque",
                      disembark: "Desembarque",
                      reverse: "Reversão",
                    } as Record<string, string>
                  )[h.action]
                }{" "}
                · {h.actor_name} ·{" "}
                {new Date(h.created_at).toLocaleString("pt-BR", {
                  timeZone: "America/Sao_Paulo",
                })}
              </p>
            ))}
          </details>
        </>
      )}
    </div>
  );
}
