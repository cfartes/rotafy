import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert } from "./components/ui";
import type { RouteLeg } from "./RouteCatalog";

type Preview = { distance_m: number; duration_minutes: number };
type Result = {
  signature: string;
  loading: boolean;
  preview?: Preview;
  error?: string;
};

export function RouteEstimate({
  leg,
  label,
  manual = true,
  automatic = true,
  onApply,
  onBusy,
}: {
  leg: RouteLeg;
  label: string;
  manual?: boolean;
  automatic?: boolean;
  onApply?: (minutes: number) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const configuration = useQuery({
    queryKey: ["route-estimate-availability"],
    queryFn: () =>
      api<{ available: boolean; message: string }>(
        "/routes/estimate-availability",
      ),
    staleTime: 30000,
    retry: false,
  });
  const payload = {
    origin_city_id: leg.origin_city_id,
    destination_city_id: leg.destination_city_id,
    origin_address: (leg.origin_address || "").trim(),
    destination_address: (leg.destination_address || "").trim(),
    stop_addresses: leg.stops.map((s) => (s.address || "").trim()),
  };
  const signature = JSON.stringify(payload);
  const ready =
    !!payload.origin_city_id &&
    !!payload.destination_city_id &&
    [
      payload.origin_address,
      payload.destination_address,
      ...payload.stop_addresses,
    ].every((a) => a.length >= 3);
  const [result, setResult] = useState<Result | null>(null);
  const [revision, setRevision] = useState(0);
  const original = useRef(signature);
  const requested = automatic || signature !== original.current || revision > 0;
  const previous = useRef("");
  const apply = useRef(onApply),
    edited = useRef(manual);
  apply.current = onApply;
  edited.current = manual;
  useEffect(() => {
    if (!requested || !configuration.data?.available || !ready) return;
    let disposed = false;
    const controller = new AbortController();
    const delay = previous.current === signature ? 0 : 1000;
    previous.current = signature;
    setResult({ signature, loading: true });
    const timer = setTimeout(async () => {
      const timeout = setTimeout(() => controller.abort(), 12000);
      try {
        const preview = await api<Preview>("/routes/estimate", {
          method: "POST",
          body: signature,
          signal: controller.signal,
        });
        if (disposed) return;
        if (
          !Number.isInteger(preview.distance_m) ||
          preview.distance_m < 0 ||
          preview.distance_m > 100000000 ||
          !Number.isInteger(preview.duration_minutes) ||
          preview.duration_minutes < 1 ||
          preview.duration_minutes > 10080
        )
          throw new Error("Não foi possível obter uma previsão válida.");
        setResult({ signature, loading: false, preview });
        if (!edited.current) apply.current?.(preview.duration_minutes);
      } catch (err) {
        if (!disposed)
          setResult({
            signature,
            loading: false,
            error:
              err instanceof Error
                ? err.message
                : "Não foi possível calcular. Informe o tempo manualmente.",
          });
      } finally {
        clearTimeout(timeout);
      }
    }, delay);
    return () => {
      disposed = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [signature, revision, ready, requested, configuration.data?.available]);
  const visible = result?.signature === signature ? result : null;
  const busyCallback = useRef(onBusy);
  busyCallback.current = onBusy;
  const busy =
    requested &&
    ready &&
    (configuration.isPending ||
      (!!configuration.data?.available && (!visible || visible.loading)));
  useEffect(() => {
    busyCallback.current?.(busy);
    return () => busyCallback.current?.(false);
  }, [busy]);
  return (
    <section className="route-estimate" aria-label={`Previsão da ${label}`}>
      <h3>Distância e tempo padrão · {label}</h3>
      {configuration.isPending ? (
        <p role="status">Conferindo disponibilidade do cálculo…</p>
      ) : configuration.error || !configuration.data?.available ? (
        <p>
          {configuration.data?.message ||
            "Cálculo automático indisponível. Você pode informar o tempo manualmente."}
        </p>
      ) : (
        <>
          {!ready && (
            <p>
              Selecione as cidades e preencha os endereços completos de saída,
              chegada e de todas as paradas para calcular.
            </p>
          )}
          {!requested && (
            <p>
              Tempo operacional cadastrado: {leg.duration_minutes} min de
              deslocamento; {leg.duration_minutes + leg.stop_minutes} min com as
              paradas. Nenhuma consulta ao Google foi realizada. Consulte a
              distância e o tempo somente se precisar de uma previsão atual.
            </p>
          )}
          {requested && ready && (visible?.loading || !visible) && (
            <p role="status">Calculando distância e tempo padrão…</p>
          )}
          {visible?.error && <Alert>{visible.error}</Alert>}
          {visible?.preview && (
            <>
              <dl className="history-summary">
                <div>
                  <dt>Distância prevista</dt>
                  <dd>
                    {(visible.preview.distance_m / 1000).toLocaleString(
                      "pt-BR",
                      { minimumFractionDigits: 2, maximumFractionDigits: 2 },
                    )}{" "}
                    km
                  </dd>
                </div>
                <div>
                  <dt>Deslocamento sem trânsito</dt>
                  <dd>{visible.preview.duration_minutes} min</dd>
                </div>
                <div>
                  <dt>Total com suas paradas</dt>
                  <dd>
                    {visible.preview.duration_minutes + leg.stop_minutes} min
                  </dd>
                </div>
              </dl>
              <p className="maps-attribution" translate="no">
                Google Maps
              </p>
              {onApply && manual && (
                <p>
                  Seu tempo manual foi preservado. Use a previsão abaixo se
                  desejar substituí-lo.
                </p>
              )}
              <p className="muted">
                Previsão atual pela ordem das paradas. Confira o percurso para o
                veículo utilizado.{" "}
                {onApply
                  ? "Ao salvar, confirme o tempo operacional."
                  : "O tempo operacional cadastrado não foi alterado."}{" "}
                A distância é consultada novamente ao solicitar outra previsão.
              </p>
            </>
          )}
          <div className="history-map-actions">
            <button
              type="button"
              className="button secondary"
              disabled={!ready || visible?.loading}
              onClick={() => setRevision((v) => v + 1)}
            >
              {requested
                ? "Recalcular percurso"
                : "Consultar distância e tempo"}
            </button>
            {onApply && visible?.preview && (
              <button
                type="button"
                className="button secondary"
                disabled={visible.loading}
                onClick={() => onApply(visible.preview!.duration_minutes)}
              >
                Usar tempo calculado
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
