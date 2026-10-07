export type JourneyStates = Record<
  string,
  {
    status: string;
    started_at?: string;
    arrived_at?: string;
    arrival_location?: {
      status: string;
      latitude?: number;
      longitude?: number;
      accuracy_m?: number;
      captured_at?: string;
      reason?: string;
      actor_name?: string;
    };
  }
>;
export type Completion = { recorded_at: string; actor_name: string | null };
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const reasons: Record<string, string> = {
  permission_denied: "Permissão de localização negada",
  permission_denied_forever: "Permissão de localização bloqueada",
  service_disabled: "Localização desativada no celular",
  timeout: "Tempo esgotado ao obter localização",
  stale_position: "Posição recebida desatualizada",
  position_unavailable: "Não foi possível obter a posição",
  not_provided: "Localização não enviada pelo aplicativo",
};

export function TripCompletion({
  mode,
  status,
  completion,
  legs,
  vehicles,
}: {
  mode?: string;
  status: string;
  completion?: Completion | null;
  legs: { id: string; origin: string; destination: string }[];
  vehicles: {
    id: string;
    name: string;
    plate: string;
    journey_states?: JourneyStates;
    leg_positions?: number[];
  }[];
}) {
  return (
    <section className="trip-completion" aria-label="Finalização e chegadas">
      <h3>Finalização e chegadas</h3>
      {completion ? (
        <p>
          Concluída no sistema em {date(completion.recorded_at)}
          {completion.actor_name && ` · ${completion.actor_name}`}
        </p>
      ) : (
        <p className="muted">
          {status === "completed"
            ? "Viagem concluída. Horário de encerramento não disponível no histórico."
            : status === "cancelled"
              ? "Viagem cancelada."
              : "A viagem ainda não foi concluída."}
        </p>
      )}
      <div className="trip-detail-grid">
        {vehicles.flatMap((vehicle) =>
          legs.flatMap((leg, index) => {
            if (
              vehicle.leg_positions?.length &&
              !vehicle.leg_positions.includes(index + 1)
            )
              return [];
            const journey = vehicle.journey_states?.[leg.id];
            const location = journey?.arrival_location;
            return (
              <article
                className="operation-card"
                key={`${vehicle.id}:${leg.id}`}
              >
                <h4>
                  {vehicle.name} · {vehicle.plate} ·{" "}
                  {mode === "multi_destination"
                    ? `Deslocamento ${index + 1}`
                    : index === 0
                      ? "Ida"
                      : "Volta"}
                </h4>
                <p>
                  {leg.origin} → {leg.destination}
                </p>
                {journey?.started_at && (
                  <p>Saída registrada: {date(journey.started_at)}</p>
                )}
                {journey?.arrived_at ? (
                  <>
                    <p>
                      <strong>
                        Chegada registrada: {date(journey.arrived_at)}
                      </strong>
                      {location?.actor_name && ` · ${location.actor_name}`}
                    </p>
                    {location?.status === "captured" &&
                    typeof location.latitude === "number" &&
                    typeof location.longitude === "number" ? (
                      <>
                        <p>
                          GPS: {location.latitude.toFixed(6)},{" "}
                          {location.longitude.toFixed(6)}
                          {typeof location.accuracy_m === "number" &&
                            ` · precisão ${location.accuracy_m.toFixed(0)} m`}
                          {location.captured_at &&
                            ` · captura ${date(location.captured_at)}`}
                        </p>
                        <a
                          className="button secondary"
                          target="_blank"
                          rel="noopener noreferrer"
                          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${location.latitude},${location.longitude}`)}`}
                        >
                          Ver local da chegada no Google Maps
                        </a>
                      </>
                    ) : (
                      <p>
                        Sem coordenadas ·{" "}
                        {reasons[location?.reason ?? "not_provided"] ??
                          "Localização indisponível"}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="muted">
                    Sem chegada registrada pelo motorista ou guia neste trecho.
                  </p>
                )}
              </article>
            );
          }),
        )}
      </div>
    </section>
  );
}
