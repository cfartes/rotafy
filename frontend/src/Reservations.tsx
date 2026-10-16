import { ReservationWhatsApp } from "./ReservationWhatsApp";
import {
  PassengerExceptions,
  type PassengerDocuments,
} from "./components/PassengerExceptions";
import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, patch, post } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { money } from "./billing/types";
import "./reservations.css";
import { TicketManager } from "./Tickets";
import {
  ReservationJourneyEditor,
  locationText,
  type Journey,
  type JourneyLeg,
} from "./JourneyLocation";

type Passenger = PassengerDocuments & {
  id?: string;
  full_name: string;
  cpf?: string | null;
};
type Leg = JourneyLeg;
type Trip = {
  mode?: string;
  requires_cpf?: boolean;
  geography_complete?: boolean;
  id: string;
  name: string;
  status: string;
  starts_at: string;
  price_cents: number;
  legs: Leg[];
};
type Vehicle = {
  allocation_id: string;
  name: string;
  plate: string;
  capacity: number;
  available: number;
  fits_family: boolean;
  legs: {
    vehicle_name?: string;
    leg_id: string;
    available: number;
    segments: {
      origin: string;
      destination: string;
      occupied: number;
      available: number;
    }[];
  }[];
};
type Availability = {
  vehicles: Vehicle[];
  suggested_allocation_id: string | null;
  can_book: boolean;
  message: string;
};
type Reservation = {
  leg_allocations?: {
    position: number;
    origin: string;
    destination: string;
    vehicle_name: string;
    plate: string;
  }[];
  edit_version: number;
  is_paid: boolean;
  id: string;
  contact_name: string;
  phone: string;
  passenger_count: number;
  status: string;
  vehicle_name: string;
  total_cents: number;
  expires_at: string | null;
  allocation_id: string;
  passengers: Passenger[];
  journeys: Journey[];
};
type Preview = {
  id: string;
  status: string;
  expires_at: string;
  families: {
    reference: string;
    contact_name: string;
    phone: string;
    passengers: Passenger[];
    lines: number[];
  }[];
  errors: { line: number; message: string }[];
  reservations: { id: string }[];
};
const status: Record<string, string> = {
  pending: "Bloqueio pendente",
  confirmed: "Confirmada",
  cancelled: "Cancelada",
  expired: "Expirada",
};
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível concluir a operação.";
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const fullJourney = (trip: Trip): Journey[] =>
  trip.legs.map((l) => ({
    leg_id: l.id,
    boarding_position: 0,
    dropoff_position: l.stops.length + 1,
  }));

export function Reservations({
  tripId,
  onBack,
  onLogout,
  initialCreate = false,
  backLabel = "Voltar às viagens",
  hideBack = false,
}: {
  tripId: string;
  onBack: () => void;
  onLogout: () => void;
  initialCreate?: boolean;
  backLabel?: string;
  hideBack?: boolean;
}) {
  const client = useQueryClient();
  const [creating, setCreating] = useState(initialCreate);
  const [importing, setImporting] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const trip = useQuery({
    queryKey: ["operations", "trip", tripId],
    queryFn: () => api<Trip>(`/trips/${tripId}`),
    refetchInterval: 30000,
  });
  const reservations = useQuery({
    queryKey: ["reservations", tripId],
    queryFn: () => api<Reservation[]>(`/trips/${tripId}/reservations`),
    refetchInterval: 30000,
  });
  const availability = useQuery({
    queryKey: ["availability", tripId],
    queryFn: () => post<Availability>(`/trips/${tripId}/availability`, {}),
    refetchInterval: 30000,
  });
  const queryError = trip.error || reservations.error || availability.error;
  useEffect(() => {
    if (queryError instanceof ApiError && queryError.status === 401) onLogout();
  }, [queryError, onLogout]);
  async function refresh() {
    await client.invalidateQueries({
      queryKey: ["boarding-locations", tripId],
    });
    await client.invalidateQueries({ queryKey: ["vehicle-route", tripId] });
    await client.invalidateQueries({ queryKey: ["reservations"] });
    await client.invalidateQueries({ queryKey: ["availability"] });
    await client.invalidateQueries({ queryKey: ["audit"] });
  }
  const bookable =
    trip.data?.status === "scheduled" &&
    new Date(trip.data.starts_at) > new Date();
  return (
    <div className="reservation-workspace">
      {!hideBack && (
        <button className="button secondary" onClick={onBack}>
          {backLabel}
        </button>
      )}
      <div className="reservation-heading">
        <div>
          <p className="eyebrow">ATENDIMENTO</p>
          <h2>Reservas · {trip.data?.name || "Carregando…"}</h2>
          {trip.data && (
            <p className="muted">
              {date(trip.data.starts_at)} · {money(trip.data.price_cents)} por
              passageiro
            </p>
          )}
          <p className="muted">
            Uma família, um telefone e o mesmo veículo nos trechos escolhidos.
          </p>
        </div>
        <div className="reservation-actions">
          <button
            className="button secondary"
            disabled={!bookable}
            onClick={() => setImporting(true)}
          >
            Importar CSV/XLSX
          </button>
          <button
            className="button primary"
            disabled={!bookable}
            onClick={() => setCreating(true)}
          >
            Nova reserva
          </button>
        </div>
      </div>
      {(error || queryError) && <Alert>{error || message(queryError)}</Alert>}
      {trip.data && !bookable && (
        <Alert>Esta viagem não está aberta para novas reservas.</Alert>
      )}
      <div className="availability-grid">
        {availability.data?.vehicles.map((v) => (
          <section className="panel availability-card" key={v.allocation_id}>
            <h3>{v.name}</h3>
            <p className="muted">
              {v.plate} · {v.capacity} lugares
            </p>
            <strong>{v.available} disponíveis na rota completa</strong>
            {v.legs.map((l, index) => (
              <details key={l.leg_id}>
                <summary>
                  {trip.data?.mode === "multi_destination"
                    ? `Deslocamento ${index + 1}`
                    : index === 0
                      ? "Ida"
                      : "Volta"}{" "}
                  · {l.available} lugares na rota completa
                  {trip.data?.mode === "multi_destination" &&
                    l.vehicle_name &&
                    ` · ${l.vehicle_name}`}
                </summary>
                {l.segments.map((s, i) => (
                  <p key={i}>
                    {s.origin} → {s.destination}
                    <br />
                    <span className="muted">
                      {s.occupied} ocupados · {s.available} disponíveis
                    </span>
                  </p>
                ))}
              </details>
            ))}
          </section>
        ))}
      </div>
      <section className="panel">
        <header className="panel-header">
          <div>
            <h2>Famílias e passageiros</h2>
            <p className="muted">
              Bloqueios pendentes expiram em 15 minutos. Reservas não alteram a
              franquia de viagens.
            </p>
          </div>
          <button
            className="button secondary"
            onClick={() => {
              setError("");
              refresh().catch((e) => setError(message(e)));
            }}
          >
            Atualizar lugares
          </button>
        </header>
        {reservations.isPending ? (
          <p className="empty-state">Carregando…</p>
        ) : (
          <div className="table-scroll">
            <table className="reservations-table">
              <thead>
                <tr>
                  {[
                    "Responsável / telefone",
                    "Passageiros",
                    "Veículo",
                    "Situação",
                    "Valor",
                    "",
                  ].map((h, i) => (
                    <th key={i}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reservations.data?.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.contact_name}</strong>
                      <div className="muted">{r.phone}</div>
                    </td>
                    <td>
                      {r.passenger_count}{" "}
                      {r.passenger_count === 1 ? "passageiro" : "passageiros"}
                    </td>
                    <td>{r.vehicle_name}</td>
                    <td>
                      {status[r.status]}
                      {r.status === "pending" && r.expires_at && (
                        <div className="muted">até {date(r.expires_at)}</div>
                      )}
                    </td>
                    <td>{money(r.total_cents)}</td>
                    <td>
                      <button
                        className="button secondary"
                        onClick={() => setSelected(r.id)}
                      >
                        Ver reserva
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!reservations.data?.length && (
              <p className="empty-state">
                Nenhuma família cadastrada nesta viagem.
              </p>
            )}
          </div>
        )}
      </section>
      {creating && trip.data && bookable && (
        <ReservationModal
          trip={trip.data}
          onClose={() => setCreating(false)}
          onSaved={refresh}
        />
      )}{" "}
      {importing && trip.data && (
        <ImportModal
          tripId={tripId}
          onClose={() => setImporting(false)}
          onSaved={refresh}
        />
      )}{" "}
      {selected && trip.data && (
        <ReservationDetail
          reservationId={selected}
          trip={trip.data}
          onClose={() => setSelected(null)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}

function ReservationModal({
  trip,
  onClose,
  onSaved,
}: {
  trip: Trip;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [key] = useState(() => crypto.randomUUID());
  const [passengers, setPassengers] = useState<Passenger[]>([
    { full_name: "", cpf: "" },
  ]);
  const [journeys, setJourneys] = useState(fullJourney(trip));
  const [allocation, setAllocation] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const validJourneys = journeys.every(
    (j) => j.boarding_position < j.dropoff_position,
  );
  const capacityJourneys = journeys.map(
    ({ leg_id, boarding_position, dropoff_position }) => ({
      leg_id,
      boarding_position,
      dropoff_position,
    }),
  );
  const availability = useQuery({
    queryKey: ["availability", trip.id, passengers.length, capacityJourneys],
    queryFn: () =>
      post<Availability>(`/trips/${trip.id}/availability`, {
        group_size: passengers.length,
        journeys: capacityJourneys,
      }),
    enabled: validJourneys,
    refetchInterval: 15000,
  });
  const suggested = availability.data?.vehicles.find(
    (v) => v.allocation_id === availability.data?.suggested_allocation_id,
  );
  const selectedFits =
    !allocation ||
    availability.data?.vehicles.find((v) => v.allocation_id === allocation)
      ?.fits_family;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await post(`/trips/${trip.id}/reservations`, {
        operation_key: key,
        contact_name: data.get("contact_name"),
        phone: data.get("phone"),
        phone_country:
          String(data.get("phone_country") || "")
            .trim()
            .toUpperCase() || null,
        passengers: passengers.map((p) => ({ ...p, cpf: p.cpf || null })),
        journeys,
        allocation_id: allocation || null,
        status: data.get("status"),
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError(message(e));
      await availability.refetch();
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Nova reserva familiar" wide onClose={onClose}>
      <form className="modal-form reservation-form" onSubmit={submit}>
        <div className="reservation-trip-summary">
          <strong>{trip.name}</strong>
          <span>
            {date(trip.starts_at)} · {money(trip.price_cents)} por passageiro
          </span>
        </div>
        <header className="reservation-section-heading">
          <span className="reservation-step">1</span>
          <div>
            <h3>Responsável pela reserva</h3>
            <p>Um telefone para toda a família.</p>
          </div>
        </header>
        <div className="form-grid">
          <Field label="Nome do responsável">
            <input name="contact_name" required minLength={2} maxLength={150} />
          </Field>
          <Field label="Telefone da família">
            <input
              name="phone"
              type="tel"
              required
              maxLength={40}
              placeholder="+55 47 99999-9999"
            />
          </Field>
        </div>
        <details className="reservation-options">
          <summary>Telefone de outro país</summary>
          <Field label="País do telefone (sigla ISO)">
            <input
              name="phone_country"
              defaultValue="BR"
              maxLength={2}
              placeholder="BR, GB, US…"
            />
          </Field>
        </details>
        <header className="reservation-section-heading">
          <span className="reservation-step">2</span>
          <div>
            <h3>Quem vai viajar?</h3>
            <p>
              Inclua cada passageiro, inclusive o responsável se ele viajar.
            </p>
          </div>
        </header>
        {trip.requires_cpf && (
          <p className="muted">
            Viagem interestadual: CPF de todos os passageiros, exceto
            estrangeiros e menores de 5 anos.
          </p>
        )}
        {passengers.map((p, i) => (
          <fieldset
            className="operation-card reservation-passenger-card"
            key={i}
          >
            <legend>Passageiro {i + 1}</legend>
            <div className="form-grid reservation-passenger-fields">
              <Field label={`Nome do passageiro ${i + 1}`}>
                <input
                  value={p.full_name}
                  required
                  minLength={2}
                  maxLength={150}
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, j) =>
                        j === i ? { ...p, full_name: e.target.value } : p,
                      ),
                    )
                  }
                />
              </Field>
              <PassengerExceptions
                value={p}
                index={i}
                onChange={(change) =>
                  setPassengers(
                    passengers.map((item, j) =>
                      j === i ? { ...item, ...change } : item,
                    ),
                  )
                }
              />
              <Field
                label={`CPF do passageiro ${i + 1} ${trip.requires_cpf && !p.is_foreign && !p.under_five ? "(obrigat\u00f3rio)" : "(opcional)"}`}
              >
                <input
                  required={
                    !!trip.requires_cpf && !p.is_foreign && !p.under_five
                  }
                  value={p.cpf || ""}
                  inputMode="numeric"
                  maxLength={14}
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, j) =>
                        j === i ? { ...p, cpf: e.target.value } : p,
                      ),
                    )
                  }
                />
              </Field>
            </div>
            {passengers.length > 1 && (
              <button
                type="button"
                className="button secondary"
                onClick={() =>
                  setPassengers(passengers.filter((_, j) => j !== i))
                }
              >
                Remover passageiro {i + 1}
              </button>
            )}
          </fieldset>
        ))}
        <button
          type="button"
          className="button secondary"
          disabled={passengers.length >= 200}
          onClick={() =>
            setPassengers([...passengers, { full_name: "", cpf: "" }])
          }
        >
          Adicionar passageiro
        </button>
        <ReservationJourneyEditor
          trip={trip}
          journeys={journeys}
          onChange={setJourneys}
          repeatInitially
        />
        {!validJourneys && (
          <Alert>
            O desembarque deve ser posterior ao embarque em cada trecho.
          </Alert>
        )}
        <details className="reservation-options">
          <summary>Opções da reserva · veículo e situação</summary>
          <div className="form-grid">
            <Field label="Veículo da família">
              <select
                aria-label="Veículo da família"
                value={allocation}
                onChange={(e) => setAllocation(e.target.value)}
              >
                <option value="">Usar sugestão do sistema</option>
                {availability.data?.vehicles.map((v) => (
                  <option
                    key={v.allocation_id}
                    value={v.allocation_id}
                    disabled={!v.fits_family}
                  >
                    {v.name} · {v.available} lugares no itinerário escolhido
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Situação inicial">
              <select
                aria-label="Situação inicial"
                name="status"
                defaultValue="confirmed"
              >
                <option value="confirmed">Confirmar reserva</option>
                <option value="pending">Bloquear lugares por 15 minutos</option>
              </select>
            </Field>
          </div>
        </details>
        {availability.isFetching && (
          <p className="muted">Consultando lugares…</p>
        )}
        {suggested && (
          <p className="reservation-suggestion">
            Sugestão: <strong>{suggested.name}</strong>, com{" "}
            {suggested.available} lugares disponíveis. A família de{" "}
            {passengers.length} pessoas ficará junta.
          </p>
        )}
        {availability.data && !availability.data.can_book && (
          <Alert>{availability.data.message}</Alert>
        )}
        {availability.error && <Alert>{message(availability.error)}</Alert>}
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions reservation-submit">
          <div className="reservation-total">
            <small>
              {passengers.length}{" "}
              {passengers.length === 1 ? "passageiro" : "passageiros"} · total
              da família
            </small>
            <strong>{money(trip.price_cents * passengers.length)}</strong>
          </div>
          <button type="button" className="button secondary" onClick={onClose}>
            Voltar
          </button>
          <button
            className="button primary"
            disabled={
              pending ||
              !validJourneys ||
              !availability.data?.can_book ||
              !selectedFits
            }
          >
            {pending ? "Salvando…" : "Salvar reserva"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function ReservationEditor({
  reservation,
  trip,
  onClose,
  onSaved,
}: {
  reservation: Reservation;
  trip: Trip;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState(reservation.contact_name);
  const [phone, setPhone] = useState(reservation.phone);
  const [passengers, setPassengers] = useState(reservation.passengers);
  const [journeys, setJourneys] = useState(reservation.journeys);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await patch(`/reservations/${reservation.id}`, {
        operation_key: crypto.randomUUID(),
        expected_version: reservation.edit_version,
        contact_name: name,
        phone,
        passengers,
        journeys,
        status: reservation.status,
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Editar reserva" wide onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        <p className="muted">
          Passageiros, bilhetes, valor e pagamento são preservados. Pontos de um
          trecho com histórico de embarque ficam protegidos.
        </p>
        <Field label="Responsável">
          <input
            required
            minLength={2}
            maxLength={150}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Telefone internacional">
          <input
            required
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </Field>
        {passengers.map((p, index) => (
          <fieldset
            className="operation-card reservation-passenger-card"
            key={p.id}
          >
            <legend>Passageiro {index + 1}</legend>
            <div className="form-grid reservation-passenger-fields">
              <Field label={`Nome do passageiro ${index + 1}`}>
                <input
                  required
                  minLength={2}
                  maxLength={150}
                  value={p.full_name}
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, i) =>
                        i === index ? { ...p, full_name: e.target.value } : p,
                      ),
                    )
                  }
                />
              </Field>
              <PassengerExceptions
                value={p}
                index={index}
                onChange={(change) =>
                  setPassengers(
                    passengers.map((item, j) =>
                      j === index ? { ...item, ...change } : item,
                    ),
                  )
                }
              />
              <Field
                label={`CPF do passageiro ${index + 1} ${trip.requires_cpf && !p.is_foreign && !p.under_five ? "(obrigat\u00f3rio)" : "(opcional)"}`}
              >
                <input
                  required={
                    !!trip.requires_cpf && !p.is_foreign && !p.under_five
                  }
                  value={p.cpf || ""}
                  maxLength={14}
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, i) =>
                        i === index ? { ...p, cpf: e.target.value } : p,
                      ),
                    )
                  }
                />
              </Field>
            </div>
          </fieldset>
        ))}
        <ReservationJourneyEditor
          trip={trip}
          journeys={journeys}
          onChange={setJourneys}
        />
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar alterações"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function ReservationDetail({
  reservationId,
  trip,
  onClose,
  onSaved,
}: {
  reservationId: string;
  trip: Trip;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [allocation, setAllocation] = useState("");
  const [editing, setEditing] = useState(false);
  const detail = useQuery({
    queryKey: ["reservations", "detail", reservationId],
    queryFn: () => api<Reservation>(`/reservations/${reservationId}`),
    refetchInterval: 15000,
  });
  const availability = useQuery({
    queryKey: ["availability", "move", reservationId, detail.data?.journeys],
    queryFn: () =>
      post<Availability>(`/trips/${trip.id}/availability`, {
        group_size: detail.data!.passenger_count,
        journeys: detail.data!.journeys,
      }),
    enabled: !!detail.data,
  });
  async function action(kind: string) {
    if (
      kind === "cancelled" &&
      !window.confirm(
        "Cancelar a reserva e liberar os lugares de toda a família?",
      )
    )
      return;
    setPending(true);
    setError("");
    try {
      await patch(
        `/reservations/${reservationId}/${kind === "vehicle" ? "vehicle" : "status"}`,
        kind === "vehicle" ? { allocation_id: allocation } : { status: kind },
      );
      await onSaved();
      await detail.refetch();
      await availability.refetch();
      if (kind === "vehicle") setAllocation("");
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  const [trackingLink, setTrackingLink] = useState("");
  async function salesAction(kind: string) {
    setPending(true);
    setError("");
    try {
      if (kind === "payment")
        await patch(`/reservations/${reservationId}/payment`, {
          is_paid: !detail.data!.is_paid,
        });
      else if (kind === "link") {
        const result = await post<{ token: string }>(
          `/reservations/${reservationId}/tracking-link`,
          {},
        );
        setTrackingLink(
          `${window.location.origin}/acompanhar#token=${encodeURIComponent(result.token)}`,
        );
      } else {
        await post(`/reservations/${reservationId}/tracking-link/revoke`, {});
        setTrackingLink("");
      }
      await onSaved();
      await detail.refetch();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  const active = ["pending", "confirmed"].includes(detail.data?.status || "");
  return (
    <Modal title="Detalhes da reserva" wide onClose={onClose}>
      <div className="modal-form">
        {detail.isPending ? (
          <p>Carregando…</p>
        ) : detail.error ? (
          <Alert>{message(detail.error)}</Alert>
        ) : (
          detail.data && (
            <>
              <h3>{detail.data.contact_name}</h3>
              <ReservationWhatsApp reservationId={reservationId} />
              {active &&
                ["scheduled", "in_progress"].includes(trip.status) &&
                !(
                  trip.mode === "multi_destination" &&
                  trip.status === "in_progress"
                ) && (
                  <button
                    className="button secondary"
                    onClick={() => setEditing(true)}
                  >
                    Editar reserva
                  </button>
                )}
              <p>
                {detail.data.phone} · {status[detail.data.status]}
              </p>
              <p>
                {detail.data.vehicle_name} · {money(detail.data.total_cents)}
              </p>
              {detail.data.status === "pending" && detail.data.expires_at && (
                <p>Bloqueio até {date(detail.data.expires_at)}</p>
              )}
              <p>
                <strong>{detail.data.is_paid ? "PAGO" : "NÃO PAGO"}</strong> ·
                Registro manual; nenhum pagamento é processado.
              </p>
              <button
                className="button secondary"
                disabled={pending || (!active && !detail.data.is_paid)}
                onClick={() => salesAction("payment")}
              >
                {detail.data.is_paid ? "Desmarcar PAGO" : "Marcar PAGO"}
              </button>
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => salesAction("link")}
              >
                Gerar link de acompanhamento
              </button>
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => salesAction("revoke")}
              >
                Revogar link de acompanhamento
              </button>
              {trackingLink && (
                <Field label="Link privado da família">
                  <input readOnly value={trackingLink} />
                </Field>
              )}
              <h3>Passageiros</h3>
              {detail.data.passengers.map((p, i) => (
                <p key={i}>
                  {p.full_name}
                  <span className="muted">
                    {" "}
                    ·{" "}
                    {p.cpf
                      ? "CPF informado"
                      : p.is_foreign
                        ? "Estrangeiro"
                        : p.under_five
                          ? "Menor de 5 anos"
                          : "CPF não informado"}
                  </span>
                </p>
              ))}
              <TicketManager
                reservationId={reservationId}
                confirmed={
                  detail.data.status === "confirmed" &&
                  ["scheduled", "in_progress"].includes(trip.status)
                }
                legs={trip.legs}
              />
              {detail.data.journeys.map((j) => {
                const leg = trip.legs.find((l) => l.id === j.leg_id)!;
                const points = [
                  leg.origin,
                  ...leg.stops.map((s) => s.name),
                  leg.destination,
                ];
                return (
                  <p key={j.leg_id}>
                    {j.boarding_location
                      ? locationText(j.boarding_location)
                      : points[j.boarding_position]}{" "}
                    →{" "}
                    {j.dropoff_location
                      ? locationText(j.dropoff_location)
                      : points[j.dropoff_position]}
                  </p>
                );
              })}
              {trip.mode === "multi_destination" &&
                detail.data.leg_allocations?.map((a) => (
                  <p key={a.position}>
                    Deslocamento {a.position}: {a.origin} → {a.destination} ·{" "}
                    {a.vehicle_name} · {a.plate}
                  </p>
                ))}
              {active && ["scheduled", "in_progress"].includes(trip.status) && (
                <>
                  <p className="muted">
                    A família deve estar sem passageiros a bordo para trocar de
                    veículo. O histórico dos trechos concluídos é preservado.
                  </p>
                  <Field label="Realocar família para">
                    <select
                      aria-label="Realocar família para"
                      disabled={pending}
                      value={allocation}
                      onChange={(e) => setAllocation(e.target.value)}
                    >
                      <option value="">Escolha outro veículo</option>
                      {availability.data?.vehicles
                        .filter(
                          (v) => v.allocation_id !== detail.data!.allocation_id,
                        )
                        .map((v) => (
                          <option
                            key={v.allocation_id}
                            value={v.allocation_id}
                            disabled={!v.fits_family}
                          >
                            {v.name} · {v.available} lugares
                          </option>
                        ))}
                    </select>
                  </Field>
                  <button
                    className="button secondary"
                    disabled={pending || !allocation}
                    onClick={() => action("vehicle")}
                  >
                    Realocar família
                  </button>
                </>
              )}
              {editing && (
                <ReservationEditor
                  reservation={detail.data}
                  trip={trip}
                  onClose={() => setEditing(false)}
                  onSaved={async () => {
                    await onSaved();
                    await detail.refetch();
                    await availability.refetch();
                  }}
                />
              )}
              {error && <Alert>{error}</Alert>}
              <footer className="modal-actions">
                {detail.data.status === "pending" && (
                  <button
                    className="button primary"
                    disabled={pending}
                    onClick={() => action("confirmed")}
                  >
                    Confirmar reserva
                  </button>
                )}
                {active && (
                  <button
                    className="button secondary"
                    disabled={pending}
                    onClick={() => action("cancelled")}
                  >
                    Cancelar reserva
                  </button>
                )}
              </footer>
            </>
          )
        )}
      </div>
    </Modal>
  );
}

function ImportModal({
  tripId,
  onClose,
  onSaved,
}: {
  tripId: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  function template() {
    const blob = new Blob(
      [
        "\uFEFFfamilia,responsavel,telefone,pais,passageiro,cpf,estrangeiro,menor_5_anos,nascimento\nFAM001,Família Exemplo,+5511999999999,BR,Passageiro Exemplo,,nao,nao,\n",
      ],
      { type: "text/csv;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelo-reservas.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function analyze() {
    if (!file) return;
    setPending(true);
    setError("");
    try {
      if (file.size > 2 * 1024 * 1024)
        throw new Error("O arquivo deve ter até 2 MB.");
      const data = new FormData();
      data.append("file", file);
      setPreview(
        await api<Preview>(`/trips/${tripId}/reservation-imports/preview`, {
          method: "POST",
          body: data,
        }),
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  async function apply() {
    setPending(true);
    setError("");
    try {
      await post(`/reservation-imports/${preview!.id}/apply`, {});
      await onSaved();
      onClose();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Importar famílias e passageiros" onClose={onClose}>
      <div className="modal-form">
        <p>
          Uma linha por passageiro. Repita o identificador da família,
          responsável e telefone para mantê-los juntos.
        </p>
        <p className="muted">
          CSV UTF-8 ou XLSX com uma única aba e células de texto, sem fórmulas.
          Máximo de 2 MB e 500 passageiros. CPF é exigido em viagens
          interestaduais, salvo as exceções. A importação usa todos os
          deslocamentos da viagem ou pacote e confirma as reservas.
        </p>
        <button className="button secondary" onClick={template}>
          Baixar modelo CSV
        </button>
        <Field label="Arquivo de passageiros">
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setPreview(null);
              setError("");
            }}
          />
        </Field>
        <button
          className="button secondary"
          disabled={pending || !file}
          onClick={analyze}
        >
          {pending ? "Analisando…" : "Analisar arquivo"}
        </button>
        {preview && (
          <>
            <h3>Prévia da importação</h3>
            {preview.status === "applied" ? (
              <p>
                Este arquivo já foi importado: {preview.reservations.length}{" "}
                famílias. Nenhuma reserva será duplicada.
              </p>
            ) : (
              <>
                <p>
                  {preview.families.length} famílias ·{" "}
                  {preview.families.reduce(
                    (n, f) => n + f.passengers.length,
                    0,
                  )}{" "}
                  passageiros · prévia válida até {date(preview.expires_at)}
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Família</th>
                        <th>Responsável</th>
                        <th>Passageiros</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.families.map((f) => (
                        <tr key={f.reference}>
                          <td>{f.reference}</td>
                          <td>
                            {f.contact_name}
                            <div className="muted">{f.phone}</div>
                          </td>
                          <td>{f.passengers.length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.errors.length > 0 && (
                  <Alert>
                    <strong>Corrija os erros antes de importar:</strong>
                    {preview.errors.map((e, i) => (
                      <p key={i}>
                        Linha {e.line}: {e.message}
                      </p>
                    ))}
                  </Alert>
                )}
                <p className="muted">
                  A prévia não bloqueia lugares. Ao confirmar, todas as famílias
                  são verificadas na mesma operação. Se faltar lugar, nenhuma
                  reserva do lote será criada.
                </p>
              </>
            )}
          </>
        )}
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button className="button secondary" onClick={onClose}>
            Voltar
          </button>
          {preview?.status === "preview" && (
            <button
              className="button primary"
              disabled={
                pending || preview.errors.length > 0 || !preview.families.length
              }
              onClick={apply}
            >
              {pending ? "Importando…" : "Confirmar importação"}
            </button>
          )}
        </footer>
      </div>
    </Modal>
  );
}
