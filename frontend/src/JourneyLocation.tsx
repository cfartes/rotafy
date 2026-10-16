import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin, ExternalLink } from "lucide-react";
import { api } from "./api";

export type Location = {
  name: string;
  address: string;
  complement: string;
  order: number;
};
export type Journey = {
  leg_id: string;
  boarding_position: number;
  dropoff_position: number;
  boarding_location?: Location | null;
  dropoff_location?: Location | null;
};
export type JourneyLeg = {
  id: string;
  origin: string;
  destination: string;
  origin_uf?: string;
  destination_uf?: string;
  origin_address?: string;
  destination_address?: string;
  stops: { name: string; kind: string; address?: string }[];
};
const normalize = (s: string) =>
  s
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
export const locationText = (value?: Location | null) =>
  value
    ? [
        value.name,
        value.address && value.address !== value.name ? value.address : "",
      ]
        .filter(Boolean)
        .join(" — ")
    : "";

// A single input accepts both existing route points and a new hotel/address.
function JourneyLocation({
  label,
  tripId,
  leg,
  kind,
  journey,
  onChange,
}: {
  label: string;
  tripId: string;
  leg: JourneyLeg;
  kind: "boarding" | "dropoff";
  journey: Journey;
  onChange: (journey: Journey) => void;
}) {
  const listId = useId();
  const hintId = useId();
  const value = journey[`${kind}_location`];
  const position = journey[`${kind}_position`];
  const points = [
    { name: leg.origin, address: leg.origin_address, kind: "boarding" },
    ...leg.stops,
    {
      name: leg.destination,
      address: leg.destination_address,
      kind: "dropoff",
    },
  ];
  const places = useQuery({
    queryKey: ["boarding-locations", tripId],
    queryFn: () => api<Journey[]>(`/trips/${tripId}/boarding-locations`),
    staleTime: 30000,
  });
  const options = points.flatMap((p, i) => {
    const allowed =
      kind === "boarding"
        ? i < journey.dropoff_position
        : i > journey.boarding_position;
    return allowed && [kind, "both"].includes(p.kind)
      ? [{ text: p.name, position: i, location: null as Location | null }]
      : [];
  });
  for (const p of places.data ?? []) {
    const location = p[`${kind}_location`];
    const anchor = p[`${kind}_position`];
    if (
      p.leg_id !== leg.id ||
      !location ||
      (kind === "boarding"
        ? anchor >= journey.dropoff_position
        : anchor <= journey.boarding_position)
    )
      continue;
    const text = locationText(location);
    if (!options.some((o) => normalize(o.text) === normalize(text)))
      options.push({ text, position: anchor, location });
  }
  const text = value ? locationText(value) : (points[position]?.name ?? "");
  const city = kind === "boarding" ? leg.origin : leg.destination;
  const uf = kind === "boarding" ? leg.origin_uf : leg.destination_uf;
  const query =
    value?.address ||
    (!value && points[position]?.address) ||
    [text, city, uf, "Brasil"].filter(Boolean).join(", ");
  function update(text: string) {
    const named = options.filter(
      (o) => o.location && normalize(o.location.name) === normalize(text),
    );
    const existing =
      options.find((p) => normalize(p.text) === normalize(text)) ??
      (named.length === 1 ? named[0] : undefined);
    const anchor = kind === "boarding" ? 0 : leg.stops.length + 1;
    onChange({
      ...journey,
      [`${kind}_position`]: existing?.position ?? anchor,
      [`${kind}_location`]: existing
        ? existing.location && { ...existing.location }
        : {
            name: text,
            address: "",
            complement: value?.complement ?? "",
            order: value?.order ?? 1,
          },
    });
  }
  return (
    <div className="pickup-field">
      <label className="field">
        <span>{label}</span>
        <input
          required
          minLength={2}
          maxLength={300}
          list={listId}
          value={text}
          placeholder="Digite o hotel, endereço ou escolha um ponto"
          autoComplete="off"
          aria-describedby={hintId}
          onChange={(e) => update(e.target.value)}
        />
      </label>
      <datalist id={listId}>
        {options.map((o) => (
          <option key={o.text} value={o.text} />
        ))}
      </datalist>
      <div className="pickup-tools">
        <small id={hintId}>
          Hotel ou endereço em {city}. Você também pode escolher um ponto da
          viagem.
        </small>
        {text.trim().length >= 2 && (
          <a
            className="pickup-maps"
            href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Conferir ${label.toLowerCase()} no Google Maps (nova aba)`}
          >
            <ExternalLink size={15} aria-hidden="true" /> Conferir no Maps
          </a>
        )}
      </div>
      {value?.complement && <small>Complemento: {value.complement}</small>}
    </div>
  );
}

export function ReservationJourneyEditor({
  trip,
  journeys,
  onChange,
  repeatInitially = false,
}: {
  trip: { id: string; mode?: string; legs: JourneyLeg[] };
  journeys: Journey[];
  onChange: (journeys: Journey[]) => void;
  repeatInitially?: boolean;
}) {
  const [repeat, setRepeat] = useState(repeatInitially);
  const [changeDropoff, setChangeDropoff] = useState(false);
  const leg = trip.legs[0];
  const first = journeys.find((j) => j.leg_id === leg.id)!;
  const sameCity = (
    a: string,
    aUf: string | undefined,
    b: string,
    bUf: string | undefined,
  ) => normalize(a) === normalize(b) && (!aUf || !bUf || aUf === bUf);
  const repeatable = trip.legs
    .slice(1)
    .some(
      (l) =>
        sameCity(l.origin, l.origin_uf, leg.origin, leg.origin_uf) ||
        sameCity(l.destination, l.destination_uf, leg.origin, leg.origin_uf),
    );
  function propagate(changed: Journey, apply: boolean) {
    const selected = [
      leg.origin,
      ...leg.stops.map((s) => s.name),
      leg.destination,
    ][changed.boarding_position];
    return journeys.map((j) => {
      if (j.leg_id === changed.leg_id) return changed;
      if (!apply) return j;
      const target = trip.legs.find((l) => l.id === j.leg_id)!;
      const result = { ...j };
      for (const kind of ["boarding", "dropoff"] as const) {
        const endpoint = kind === "boarding" ? "origin" : "destination";
        if (
          !sameCity(
            target[endpoint],
            target[`${endpoint}_uf`],
            leg.origin,
            leg.origin_uf,
          )
        )
          continue;
        const terminal = kind === "boarding" ? 0 : target.stops.length + 1;
        const counterpart = target.stops.findIndex(
          (s) =>
            normalize(s.name) === normalize(selected) &&
            [kind, "both"].includes(s.kind),
        );
        result[`${kind}_position`] = changed.boarding_location
          ? terminal
          : counterpart >= 0
            ? counterpart + 1
            : terminal;
        result[`${kind}_location`] = changed.boarding_location
          ? { ...changed.boarding_location }
          : changed.boarding_position === 0 || counterpart >= 0
            ? null
            : {
                name: selected,
                address:
                  leg.stops[changed.boarding_position - 1]?.address ?? "",
                complement: "",
                order: 1,
              };
      }
      return result;
    });
  }
  function manual(changed: Journey) {
    setRepeat(false);
    onChange(journeys.map((j) => (j.leg_id === changed.leg_id ? changed : j)));
  }
  const dropoffText =
    locationText(first.dropoff_location) ||
    [leg.origin, ...leg.stops.map((s) => s.name), leg.destination][
      first.dropoff_position
    ];
  return (
    <section className="reservation-pickup">
      <header className="reservation-section-heading">
        <span className="reservation-step">3</span>
        <div>
          <h3>Onde vamos buscar a família?</h3>
          <p>Um local para todos os passageiros desta reserva.</p>
        </div>
        <MapPin size={22} aria-hidden="true" />
      </header>
      <JourneyLocation
        label="Local de embarque"
        tripId={trip.id}
        leg={leg}
        kind="boarding"
        journey={first}
        onChange={(changed) => onChange(propagate(changed, repeat))}
      />
      {repeatable && (
        <label className="pickup-repeat">
          <input
            type="checkbox"
            checked={repeat}
            onChange={(e) => {
              setRepeat(e.target.checked);
              if (e.target.checked) onChange(propagate(first, true));
            }}
          />
          <span>
            Usar este local nos passeios com saída de {leg.origin} e no retorno
          </span>
        </label>
      )}
      <div className="pickup-destination">
        <span>
          Desembarque: <strong>{dropoffText}</strong>
        </span>
        <button
          type="button"
          className="pickup-text-button"
          onClick={() => setChangeDropoff((v) => !v)}
        >
          {changeDropoff ? "Recolher" : "Alterar desembarque"}
        </button>
      </div>
      {changeDropoff && (
        <JourneyLocation
          label="Local de desembarque"
          tripId={trip.id}
          leg={leg}
          kind="dropoff"
          journey={first}
          onChange={manual}
        />
      )}
      {trip.legs.length > 1 && (
        <details className="pickup-per-leg">
          <summary>
            Ajustar locais por{" "}
            {trip.mode === "multi_destination" ? "passeio" : "trecho"} (
            {trip.legs.length})
          </summary>
          <p className="muted">
            Cada alteração abaixo vale somente para o deslocamento escolhido.
          </p>
          {trip.legs.slice(1).map((l, i) => {
            const journey = journeys.find((j) => j.leg_id === l.id)!;
            return (
              <div className="pickup-leg" key={l.id}>
                <h4>
                  {trip.mode === "multi_destination"
                    ? `Deslocamento ${i + 2}`
                    : "Volta"}{" "}
                  · {l.origin} → {l.destination}
                </h4>
                <div className="form-grid">
                  <JourneyLocation
                    label={`Embarque · deslocamento ${i + 2}`}
                    tripId={trip.id}
                    leg={l}
                    kind="boarding"
                    journey={journey}
                    onChange={manual}
                  />
                  <JourneyLocation
                    label={`Desembarque · deslocamento ${i + 2}`}
                    tripId={trip.id}
                    leg={l}
                    kind="dropoff"
                    journey={journey}
                    onChange={manual}
                  />
                </div>
              </div>
            );
          })}
        </details>
      )}
    </section>
  );
}
