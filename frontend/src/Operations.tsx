import {
  PackageItineraryEditor,
  PackageProgram,
  emptyPackageItinerary,
  packageItineraryInput,
  type PackageItinerary,
  type PackageSnapshot,
} from "./PackageItinerary";
import { type SavedRoute } from "./RouteCatalog";
import { CitySelect } from "./components/CitySelect";
import { VehicleRoute } from "./VehicleRoute";
import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, post, patch, type User } from "./api";
import { Boarding } from "./Boarding";
import { Alert, Field, Modal } from "./components/ui";
import { money, parseMoney, moneyInput } from "./billing/types";
import { Reservations } from "./Reservations";
import {
  TripCompletion,
  type JourneyStates,
  type Completion,
} from "./TripCompletion";

type Vehicle = {
  id: string;
  name: string;
  plate: string;
  capacity: number;
  is_active: boolean;
};
type Package = {
  version?: number;
  itinerary?: PackageItinerary | null;
  id: string;
  name: string;
  destination: string;
  description: string;
  price_cents: number;
  is_active: boolean;
};
type Crew = { id: string; full_name: string; role: "driver" | "guide" };
type Trip = {
  edit_version: number;
  id: string;
  name: string;
  destination: string;
  mode: string;
  status: string;
  starts_at: string;
  ends_at: string;
  price_cents: number;
  capacity: number;
  vehicle_count: number;
};
type Stop = {
  name: string;
  kind: string;
  scheduled_at: string | null;
  address?: string;
};
type Leg = {
  origin_city_id?: number | null;
  destination_city_id?: number | null;
  origin_uf?: string | null;
  destination_uf?: string | null;
  origin_address?: string;
  destination_address?: string;
  origin: string;
  destination: string;
  starts_at: string;
  ends_at: string;
  stops: Stop[];
};
type Allocation = {
  allocation_id?: string;
  leg_positions?: number[];
  routes?: { leg_position: number; stop_positions: number[] }[];
  vehicle_id: string;
  driver_id: string;
  guide_ids: string[];
};
type Detail = Trip & {
  package_snapshot?: PackageSnapshot | null;
  usage_units?: number;
  route_id?: string | null;
  route_snapshot?: SavedRoute | null;
  completion?: Completion | null;
  package_id: string | null;
  legs: (Leg & { id: string })[];
  vehicles: {
    id: string;
    vehicle_id: string;
    driver_id: string;
    leg_positions?: number[];
    name: string;
    plate: string;
    capacity: number;
    driver_name: string;
    journey_states?: JourneyStates;
    guides: { id: string; full_name: string }[];
    routes?: { leg_position: number; stop_positions: number[] }[];
  }[];
};
const status: Record<string, string> = {
  scheduled: "Agendada",
  in_progress: "Em andamento",
  completed: "Concluída",
  cancelled: "Cancelada",
};
const legLabel = (mode: string, index: number) =>
  mode === "multi_destination"
    ? `Deslocamento ${index + 1}`
    : index === 0
      ? "Ida"
      : "Volta";
const stopKind: Record<string, string> = {
  boarding: "Embarque",
  dropoff: "Desembarque",
  both: "Embarque e desembarque",
};
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível salvar.";
// Horários operacionais informados em São Paulo, independente do fuso do navegador.
function localInput(value: string) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Sao_Paulo",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(value))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
function instant(value: string) {
  const local = Date.parse(`${value}:00Z`);
  let utc = local;
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let pass = 0; pass < 2; pass++) {
    const parts = Object.fromEntries(
      formatter.formatToParts(new Date(utc)).map((p) => [p.type, p.value]),
    );
    const represented = Date.UTC(
      Number(parts.year),
      Number(parts.month) - 1,
      Number(parts.day),
      Number(parts.hour),
      Number(parts.minute),
      Number(parts.second),
    );
    utc = local - (represented - utc);
  }
  return new Date(utc).toISOString();
}
const blankLeg = (): Leg => ({
  origin: "",
  destination: "",
  starts_at: "",
  ends_at: "",
  stops: [],
});

export function Operations({
  manage,
  user,
  onLogout,
  initialTab = "trips",
  action,
  allowPackages = true,
  initialTripId = null,
}: {
  manage: boolean;
  user: User;
  onLogout: () => void;
  initialTab?: "vehicles" | "trips";
  action?: "passengers" | "allocations";
  allowPackages?: boolean;
  initialTripId?: string | null;
}) {
  const client = useQueryClient();
  const [tab, setTab] = useState<string>(initialTab);
  const [editing, setEditing] = useState<Vehicle | Package | "new" | null>(
    null,
  );
  const [creating, setCreating] = useState(false);
  const [editingTrip, setEditingTrip] = useState<Detail | null>(null);
  const [reservationTrip, setReservationTrip] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<Detail | null>(null);
  const [selected, setSelected] = useState<string | null>(initialTripId);
  const [boarding, setBoarding] = useState<{
    tripId: string;
    allocationId: string;
    legId: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [tripFilter, setTripFilter] = useState("all");
  const vehicles = useQuery({
    queryKey: ["operations", "vehicles"],
    queryFn: () => api<Vehicle[]>("/vehicles"),
    enabled: manage,
  });
  const packages = useQuery({
    queryKey: ["operations", "packages"],
    queryFn: () => api<Package[]>("/packages"),
    enabled: manage && allowPackages,
  });
  const crew = useQuery({
    queryKey: ["operations", "crew"],
    queryFn: () => api<Crew[]>("/operations/crew"),
    enabled: manage,
  });
  const trips = useQuery({
    queryKey: ["operations", "trips"],
    queryFn: () => api<Trip[]>("/trips"),
  });
  const detail = useQuery({
    queryKey: ["operations", "trip", selected],
    queryFn: () => api<Detail>(`/trips/${selected}`),
    enabled: !!selected,
  });
  const queryError =
    vehicles.error ||
    packages.error ||
    crew.error ||
    trips.error ||
    detail.error;
  useEffect(() => {
    if (queryError instanceof ApiError && queryError.status === 401) onLogout();
  }, [queryError, onLogout]);
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["operations"] });
    await client.invalidateQueries({ queryKey: ["audit"] });
    await client.invalidateQueries({ queryKey: ["billing"] });
  }
  async function transition(value: string) {
    if (
      value === "cancelled" &&
      !window.confirm(
        "Cancelar esta viagem e devolver seu consumo à franquia do mês original?",
      )
    )
      return;
    setPending(true);
    setError("");
    try {
      await patch(`/trips/${selected}/status`, { status: value });
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  const listLoading =
    tab === "vehicles"
      ? vehicles.isPending
      : tab === "packages"
        ? packages.isPending
        : trips.isPending;
  const filteredTrips = (trips.data ?? []).filter(
    (t) =>
      tripFilter === "all" ||
      (tripFilter === "open"
        ? ["scheduled", "in_progress"].includes(t.status)
        : t.status === tripFilter),
  );
  if (reservationTrip)
    return (
      <Reservations
        tripId={reservationTrip}
        onBack={() => setReservationTrip(null)}
        onLogout={onLogout}
      />
    );
  if (boarding)
    return (
      <Boarding
        key={`${boarding.tripId}:${boarding.allocationId}:${boarding.legId}`}
        {...boarding}
        onBack={() => setBoarding(null)}
      />
    );
  return (
    <>
      {manage && (
        <div className="operations-tabs" aria-label="Módulos de operação">
          {[
            ["trips", "Viagens"],
            ["vehicles", "Frota"],
            ...(allowPackages ? [["packages", "Pacotes"]] : []),
          ].map(([id, label]) => (
            <button
              key={id}
              className={`button ${tab === id ? "primary" : "secondary"}`}
              onClick={() => {
                setTab(id);
                setEditing(null);
                setSelected(null);
                setError("");
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {(error || queryError) && <Alert>{error || message(queryError)}</Alert>}
      <section className="panel">
        <header className="panel-header">
          <div>
            <h2>
              {tab === "trips"
                ? manage
                  ? "Viagens comerciais"
                  : "Minhas viagens"
                : tab === "vehicles"
                  ? "Frota da empresa"
                  : "Catálogo de pacotes"}
            </h2>
            <p className="muted">
              {tab === "trips" && action === "passengers"
                ? "Escolha a viagem para cadastrar famílias e passageiros, consultar vagas e distribuir as reservas nos veículos."
                : tab === "trips" && action === "allocations"
                  ? "Escolha uma viagem agendada para adicionar veículos e definir motoristas/guias. Os veículos já usados pelas reservas são preservados."
                  : tab === "trips"
                    ? allowPackages
                      ? "Viagem avulsa consome uma unidade. Pacotes consomem uma unidade por destino comercial, com retorno incluído."
                      : "Cada viagem avulsa consome uma unidade da franquia."
                    : "Cadastros não consomem a franquia. Arquive para preservar o histórico."}
            </p>
          </div>
          {manage && (
            <button
              className="button primary"
              onClick={() =>
                tab === "trips"
                  ? (setDuplicate(null), setCreating(true))
                  : setEditing("new")
              }
            >
              {tab === "trips"
                ? "Nova viagem"
                : tab === "vehicles"
                  ? "Novo veículo"
                  : "Novo pacote"}
            </button>
          )}
        </header>
        {tab === "trips" && (
          <div className="trip-filters">
            <Field label="Situação da viagem">
              <select
                value={tripFilter}
                onChange={(e) => setTripFilter(e.target.value)}
              >
                <option value="all">Todas</option>
                <option value="open">Abertas</option>
                <option value="scheduled">Agendadas</option>
                <option value="in_progress">Em andamento</option>
                <option value="completed">Fechadas / concluídas</option>
                <option value="cancelled">Canceladas</option>
              </select>
            </Field>
            <p className="muted">
              {filteredTrips.length} de {trips.data?.length ?? 0} viagens ·
              Abertas inclui agendadas e em andamento.
            </p>
          </div>
        )}
        {listLoading ? (
          <p className="empty-state">Carregando…</p>
        ) : (
          <div className="table-scroll">
            <table className={`operations-table-${tab}`}>
              <thead>
                <tr>
                  {(tab === "trips"
                    ? [
                        "Viagem / destino",
                        "Saída e retorno",
                        "Veículos / capacidade",
                        "Situação",
                        "",
                      ]
                    : tab === "vehicles"
                      ? ["Veículo", "Placa", "Capacidade", "Situação", ""]
                      : [
                          "Pacote",
                          "Destino",
                          "Valor por passageiro",
                          "Situação",
                          "",
                        ]
                  ).map((h, i) => (
                    <th key={i}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tab === "trips" &&
                  filteredTrips.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <strong>{t.name}</strong>
                        <div className="muted">
                          {t.destination} ·{" "}
                          {t.mode === "multi_destination"
                            ? "Pacote completo"
                            : t.mode === "round_trip"
                              ? "Ida e volta"
                              : "Somente ida"}
                        </div>
                      </td>
                      <td>
                        {date(t.starts_at)}
                        <div className="muted">até {date(t.ends_at)}</div>
                      </td>
                      <td>
                        {t.vehicle_count} veículos · {t.capacity} lugares
                      </td>
                      <td>{status[t.status]}</td>
                      <td>
                        {manage && action && (
                          <button
                            className="button primary"
                            disabled={
                              action === "allocations"
                                ? t.status !== "scheduled"
                                : ["completed", "cancelled"].includes(t.status)
                            }
                            onClick={async () => {
                              if (action === "passengers")
                                setReservationTrip(t.id);
                              else {
                                try {
                                  setEditingTrip(
                                    await api<Detail>(`/trips/${t.id}`),
                                  );
                                } catch (e) {
                                  setError(message(e));
                                }
                              }
                            }}
                          >
                            {action === "passengers"
                              ? "Passageiros e reservas"
                              : "Alocar veículos"}
                          </button>
                        )}
                        <button
                          className="button secondary"
                          onClick={() => {
                            setSelected(t.id);
                            setError("");
                          }}
                        >
                          Detalhes
                        </button>
                      </td>
                    </tr>
                  ))}
                {tab === "trips" && filteredTrips.length === 0 && (
                  <tr>
                    <td colSpan={5} className="empty-state">
                      Nenhuma viagem nesta situação.
                    </td>
                  </tr>
                )}
                {tab === "vehicles" &&
                  vehicles.data?.map((v) => (
                    <tr key={v.id}>
                      <td>
                        <strong>{v.name}</strong>
                      </td>
                      <td>{v.plate}</td>
                      <td>{v.capacity} lugares</td>
                      <td>{v.is_active ? "Ativo" : "Arquivado"}</td>
                      <td>
                        <button
                          className="button secondary"
                          onClick={() => setEditing(v)}
                        >
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                {tab === "packages" &&
                  packages.data?.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.name}</strong>
                      </td>
                      <td>{p.destination}</td>
                      <td>{money(p.price_cents)}</td>
                      <td>{p.is_active ? "Ativo" : "Arquivado"}</td>
                      <td>
                        <button
                          className="button secondary"
                          onClick={() => setEditing(p)}
                        >
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {!(tab === "trips"
              ? trips.data?.length
              : tab === "vehicles"
                ? vehicles.data?.length
                : packages.data?.length) && (
              <p className="empty-state">Nenhum cadastro disponível.</p>
            )}
          </div>
        )}
      </section>
      {editing && (
        <CatalogModal
          kind={tab}
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}
      {creating && (
        <TripModal
          initial={duplicate}
          vehicles={vehicles.data || []}
          packages={packages.data || []}
          allowPackages={allowPackages}
          crew={crew.data || []}
          onClose={() => setCreating(false)}
          onSaved={refresh}
        />
      )}
      {editingTrip && (
        <TripModal
          initial={editingTrip}
          edit
          vehicles={vehicles.data || []}
          packages={packages.data || []}
          allowPackages={allowPackages}
          crew={crew.data || []}
          onClose={() => setEditingTrip(null)}
          onSaved={refresh}
        />
      )}
      {selected && (
        <Modal
          title="Detalhes da viagem"
          wide
          onClose={() => setSelected(null)}
        >
          {detail.isPending ? (
            <p>Carregando…</p>
          ) : (
            detail.data && (
              <div className="modal-form">
                <h3>{detail.data.name}</h3>
                <p>
                  {status[detail.data.status]} ·{" "}
                  {money(detail.data.price_cents)} por passageiro
                </p>
                <TripCompletion
                  mode={detail.data.mode}
                  status={detail.data.status}
                  completion={detail.data.completion}
                  legs={detail.data.legs}
                  vehicles={detail.data.vehicles.filter(
                    (v) =>
                      manage ||
                      v.driver_id === user.id ||
                      v.guides.some((g) => g.id === user.id),
                  )}
                />
                {detail.data.package_snapshot && (
                  <PackageProgram itinerary={detail.data.package_snapshot} />
                )}
                <h3>Itinerário previsto</h3>
                <div className="trip-detail-grid">
                  {detail.data.legs.map((l, i) => (
                    <section className="operation-card" key={i}>
                      <h3>
                        {legLabel(detail.data!.mode, i)}: {l.origin} →{" "}
                        {l.destination}
                      </h3>
                      <p>
                        {date(l.starts_at)} até {date(l.ends_at)}
                      </p>
                      {l.stops.map((s, i) => (
                        <p key={i}>
                          {stopKind[s.kind]}: {s.name}
                          {s.scheduled_at ? ` · ${date(s.scheduled_at)}` : ""}
                        </p>
                      ))}
                    </section>
                  ))}
                </div>
                <h3>Veículos e rotas</h3>
                <div className="trip-detail-grid">
                  {detail.data.vehicles
                    .filter(
                      (v) =>
                        manage ||
                        v.driver_id === user.id ||
                        v.guides.some((g) => g.id === user.id),
                    )
                    .map((v) => (
                      <section key={v.id} className="operation-card">
                        <h3>
                          {v.name} · {v.plate}
                        </h3>
                        <p>
                          {v.capacity} lugares · Motorista: {v.driver_name}
                        </p>
                        <VehicleRoute
                          tripId={detail.data!.id}
                          allocationId={v.id}
                          disabled={["completed", "cancelled"].includes(
                            detail.data!.status,
                          )}
                          closedLegIds={Object.entries(v.journey_states ?? {})
                            .filter(([, j]) => j.status === "completed")
                            .map(([id]) => id)}
                        />
                        <p>
                          Guias:{" "}
                          {v.guides.map((g) => g.full_name).join(", ") ||
                            "Sem guia"}
                        </p>
                        {(manage ||
                          (user.role === "driver"
                            ? v.driver_id === user.id
                            : v.guides.some((g) => g.id === user.id))) &&
                          detail.data.legs.map(
                            (leg, index) =>
                              (!v.leg_positions?.length ||
                                v.leg_positions.includes(index + 1)) && (
                                <button
                                  key={leg.id}
                                  className="button secondary"
                                  disabled={
                                    ["completed", "cancelled"].includes(
                                      detail.data!.status,
                                    ) ||
                                    v.journey_states?.[leg.id]?.status ===
                                      "completed"
                                  }
                                  onClick={() => {
                                    setBoarding({
                                      tripId: detail.data!.id,
                                      allocationId: v.id,
                                      legId: leg.id,
                                    });
                                    setSelected(null);
                                  }}
                                >
                                  Abrir embarque ·{" "}
                                  {legLabel(detail.data!.mode, index)}
                                </button>
                              ),
                          )}
                      </section>
                    ))}
                </div>
                {error && <Alert>{error}</Alert>}
                {manage && (
                  <footer className="modal-actions">
                    {detail.data.status === "scheduled" &&
                      (allowPackages || !detail.data.package_id) && (
                        <button
                          className="button secondary"
                          onClick={() => {
                            setEditingTrip(detail.data!);
                            setSelected(null);
                          }}
                        >
                          Editar viagem
                        </button>
                      )}
                    <button
                      className="button secondary"
                      disabled={
                        pending || detail.data.mode === "multi_destination"
                      }
                      onClick={async () => {
                        setPending(true);
                        setError("");
                        try {
                          const trip = detail.data!;
                          await post("/routes", {
                            name: trip.name,
                            mode: trip.mode,
                            is_active: true,
                            legs: trip.legs.map((leg) => ({
                              origin: leg.origin,
                              destination: leg.destination,
                              origin_city_id: leg.origin_city_id,
                              destination_city_id: leg.destination_city_id,
                              origin_uf: leg.origin_uf,
                              destination_uf: leg.destination_uf,
                              origin_address: leg.origin_address || "",
                              destination_address:
                                leg.destination_address || "",
                              duration_minutes: Math.max(
                                1,
                                Math.ceil(
                                  (Date.parse(leg.ends_at) -
                                    Date.parse(leg.starts_at)) /
                                    60000,
                                ),
                              ),
                              stop_minutes: 0,
                              stops: leg.stops.map((stop) => ({
                                name: stop.name,
                                kind: stop.kind,
                                address: stop.address || "",
                              })),
                            })),
                          });
                          await client.invalidateQueries({
                            queryKey: ["routes"],
                          });
                          window.alert(
                            "Rota criada. Disponível no menu Rotas; a duração foi copiada do intervalo previsto da viagem.",
                          );
                        } catch (err) {
                          setError(message(err));
                        } finally {
                          setPending(false);
                        }
                      }}
                    >
                      Salvar percurso como Rota
                    </button>
                    <button
                      className="button primary"
                      disabled={
                        pending ||
                        ["completed", "cancelled"].includes(detail.data.status)
                      }
                      onClick={() => {
                        setReservationTrip(detail.data!.id);
                        setSelected(null);
                      }}
                    >
                      Reservas e lugares
                    </button>
                    <button
                      className="button secondary"
                      disabled={
                        pending || (!allowPackages && !!detail.data.package_id)
                      }
                      onClick={() => {
                        setDuplicate(detail.data!);
                        setSelected(null);
                        setCreating(true);
                      }}
                    >
                      Duplicar viagem
                    </button>
                    {detail.data.status === "scheduled" && (
                      <button
                        className="button primary"
                        disabled={pending}
                        onClick={() => transition("in_progress")}
                      >
                        Iniciar viagem
                      </button>
                    )}
                    {detail.data.status === "in_progress" && (
                      <button
                        className="button primary"
                        disabled={pending}
                        onClick={() => transition("completed")}
                      >
                        Concluir viagem
                      </button>
                    )}
                    {["scheduled", "in_progress"].includes(
                      detail.data.status,
                    ) && (
                      <button
                        className="button secondary"
                        disabled={pending}
                        onClick={() => transition("cancelled")}
                      >
                        Cancelar viagem
                      </button>
                    )}
                  </footer>
                )}
              </div>
            )
          )}
        </Modal>
      )}
    </>
  );
}

function CatalogModal({
  kind,
  item,
  onClose,
  onSaved,
}: {
  kind: string;
  item: Vehicle | Package | "new";
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const vehicle = kind === "vehicles";
  const existing = item === "new" ? null : item;
  const [itinerary, setItinerary] = useState<PackageItinerary | null>(
    (existing as Package)?.itinerary || null,
  );
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const data = {
        name: f.get("name"),
        is_active: f.get("is_active") === "on",
        ...(vehicle
          ? { plate: f.get("plate"), capacity: Number(f.get("capacity")) }
          : {
              itinerary: itinerary ? packageItineraryInput(itinerary) : null,
              expected_version: (existing as Package)?.version || null,
              destination: f.get("destination"),
              description: f.get("description"),
              price_cents: parseMoney(String(f.get("price"))),
            }),
      };
      if (existing)
        await api(`/${kind}/${existing.id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        });
      else await post(`/${kind}`, data);
      await onSaved();
      onClose();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal
      title={`${existing ? "Editar" : "Novo"} ${vehicle ? "veículo" : "pacote"}`}
      wide={!vehicle}
      onClose={onClose}
    >
      <form className="modal-form" onSubmit={submit}>
        <Field label="Nome">
          <input
            name="name"
            defaultValue={existing?.name}
            required
            minLength={2}
            maxLength={vehicle ? 100 : 150}
          />
        </Field>
        {vehicle ? (
          <div className="form-grid">
            <Field label="Placa">
              <input
                name="plate"
                defaultValue={(existing as Vehicle)?.plate}
                required
                maxLength={8}
                placeholder="ABC1D23"
              />
            </Field>
            <Field label="Quantidade de lugares">
              <input
                name="capacity"
                type="number"
                min={1}
                max={200}
                required
                defaultValue={(existing as Vehicle)?.capacity}
              />
            </Field>
          </div>
        ) : (
          <>
            <Field label="Destino">
              <input
                name="destination"
                defaultValue={(existing as Package)?.destination}
                required
                minLength={2}
                maxLength={150}
              />
            </Field>
            <Field label="Valor por passageiro (R$)">
              <input
                name="price"
                inputMode="decimal"
                defaultValue={moneyInput(
                  (existing as Package)?.price_cents || 0,
                )}
                required
              />
            </Field>
            <Field label="Descrição">
              <textarea
                name="description"
                defaultValue={(existing as Package)?.description}
                maxLength={10000}
              />
            </Field>
          </>
        )}
        {!vehicle && (
          <>
            <label>
              <input
                type="checkbox"
                checked={!!itinerary}
                onChange={(e) =>
                  setItinerary(
                    e.target.checked ? emptyPackageItinerary() : null,
                  )
                }
              />{" "}
              Pacote com roteiro de vários destinos
            </label>
            {itinerary && (
              <PackageItineraryEditor
                value={itinerary}
                onChange={setItinerary}
              />
            )}
          </>
        )}
        <label>
          <input
            name="is_active"
            type="checkbox"
            defaultChecked={existing?.is_active ?? true}
          />{" "}
          Cadastro ativo
        </label>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Voltar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function TripModal({
  initial,
  edit = false,
  vehicles,
  packages,
  allowPackages = true,
  crew,
  onClose,
  onSaved,
}: {
  initial: Detail | null;
  edit?: boolean;
  vehicles: Vehicle[];
  packages: Package[];
  allowPackages?: boolean;
  crew: Crew[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const routeList = useQuery({
    queryKey: ["routes"],
    queryFn: () => api<SavedRoute[]>("/routes"),
  });
  const [selectedRoute, setSelectedRoute] = useState<SavedRoute | null>(
    initial?.route_snapshot || null,
  );
  const [selectedPackage, setSelectedPackage] =
    useState<PackageSnapshot | null>(initial?.package_snapshot || null);
  const [baseDate, setBaseDate] = useState(
    edit && initial ? localInput(initial.legs[0].starts_at).slice(0, 10) : "",
  );
  const legacyEdit =
    edit && !initial?.route_snapshot && !selectedRoute && !selectedPackage;
  const [key] = useState(() => crypto.randomUUID());
  const [mode, setMode] = useState(initial?.mode || "round_trip");
  const [legs, setLegs] = useState<Leg[]>(
    initial
      ? initial.legs
          .map<Leg>((l) => ({
            origin_city_id: l.origin_city_id,
            destination_city_id: l.destination_city_id,
            origin_uf: l.origin_uf,
            destination_uf: l.destination_uf,
            origin_address: l.origin_address,
            destination_address: l.destination_address,
            origin: l.origin,
            destination: l.destination,
            starts_at: edit ? localInput(l.starts_at) : "",
            ends_at: edit ? localInput(l.ends_at) : "",
            stops: l.stops.map((s) => ({
              address: s.address,
              name: s.name,
              kind: s.kind,
              scheduled_at: null,
            })),
          }))
          .concat(initial.legs.length === 1 ? [blankLeg()] : [])
      : [blankLeg(), blankLeg()],
  );
  const [allocations, setAllocations] = useState<Allocation[]>([
    ...(initial
      ? initial.vehicles.map((v) => ({
          vehicle_id: v.vehicle_id,
          allocation_id: edit ? v.id : undefined,
          leg_positions: v.leg_positions || [],
          driver_id: v.driver_id,
          guide_ids: v.guides.map((g) => g.id),
          routes: v.routes || [],
        }))
      : [{ vehicle_id: "", driver_id: "", guide_ids: [] }]),
  ]);
  const [packageId, setPackageId] = useState(initial?.package_id || "");
  const [name, setName] = useState(initial?.name || "");
  const [destination, setDestination] = useState(initial?.destination || "");
  const [price, setPrice] = useState(moneyInput(initial?.price_cents || 0));
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const activeVehicles = vehicles.filter((v) => v.is_active);
  const legCount = selectedPackage
    ? legs.length
    : mode === "round_trip"
      ? 2
      : 1;
  function packageLegs(snapshot: PackageSnapshot, dateValue: string): Leg[] {
    return snapshot.steps.map((step) => {
      const { duration_minutes, stop_minutes, ...leg } = step.leg!;
      const day = dateValue
        ? new Date(
            Date.parse(`${dateValue}T12:00:00Z`) + (step.day - 1) * 86400000,
          )
            .toISOString()
            .slice(0, 10)
        : "";
      const starts = day ? `${day}T${step.departure_time}` : "";
      return {
        ...leg,
        starts_at: starts,
        ends_at: starts
          ? localInput(
              new Date(
                Date.parse(instant(starts)) +
                  (duration_minutes + stop_minutes) * 60000,
              ).toISOString(),
            )
          : "",
        stops: leg.stops.map((stop) => ({ ...stop, scheduled_at: null })),
      };
    });
  }

  function updateLeg(index: number, update: Partial<Leg>) {
    if (update.stops && update.stops.length !== legs[index].stops.length)
      setAllocations((current) =>
        current.map((a) => ({
          ...a,
          routes: (a.routes || []).map((r) =>
            r.leg_position !== index + 1
              ? r
              : {
                  ...r,
                  stop_positions: [
                    ...r.stop_positions.filter(
                      (p) => p <= update.stops!.length,
                    ),
                    ...Array.from(
                      {
                        length: Math.max(
                          0,
                          update.stops!.length - legs[index].stops.length,
                        ),
                      },
                      (_, i) => legs[index].stops.length + i + 1,
                    ),
                  ],
                },
          ),
        })),
      );
    const template =
      selectedPackage?.steps[index].leg || selectedRoute?.legs[index];
    if (update.starts_at && template) {
      update.ends_at = localInput(
        new Date(
          Date.parse(instant(update.starts_at)) +
            (template.duration_minutes + template.stop_minutes) * 60000,
        ).toISOString(),
      );
    }
    setLegs((prev) =>
      prev.map((l, i) => (i === index ? { ...l, ...update } : l)),
    );
  }
  function updateAllocation(index: number, update: Partial<Allocation>) {
    setAllocations((prev) =>
      prev.map((a, i) => (i === index ? { ...a, ...update } : a)),
    );
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      if (!selectedRoute && !selectedPackage && !legacyEdit)
        throw new Error("Selecione uma Rota ativa antes de criar a viagem.");
      await (edit ? patch : post)(edit ? `/trips/${initial!.id}` : "/trips", {
        ...(edit ? { expected_version: initial!.edit_version } : {}),
        package_version: selectedPackage?.version || null,
        route_id: selectedRoute?.id || null,
        route_version: selectedRoute?.version || null,
        operation_key: key,
        package_id: packageId || null,
        name,
        destination,
        mode,
        price_cents: parseMoney(price),
        legs: legs.slice(0, legCount).map((l) => ({
          ...l,
          starts_at: instant(l.starts_at),
          ends_at: instant(l.ends_at),
          stops: l.stops.map((s) => ({
            ...s,
            scheduled_at: s.scheduled_at ? instant(s.scheduled_at) : null,
          })),
        })),
        vehicles: allocations.map((allocation) => ({
          ...allocation,
          routes: (allocation.routes || []).filter(
            (route) => route.leg_position <= legCount,
          ),
        })),
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
    <Modal
      title={edit ? "Editar viagem" : "Nova viagem comercial"}
      wide
      onClose={onClose}
    >
      <form className="modal-form" onSubmit={submit}>
        <p className="muted">
          {edit
            ? "A edição mantém o consumo da franquia e os valores das reservas existentes. Preserve os veículos já alocados e os trechos. Com reservas, mantenha as paradas existentes; endereços, nomes e horários podem mudar e novas paradas podem ser acrescentadas antes do destino."
            : selectedPackage
              ? `A criação consome ${selectedPackage.destinations.length} viagens da franquia, com retorno incluído.`
              : allowPackages
                ? "Viagem avulsa consome uma viagem; pacote consome uma por destino comercial."
                : "A criação consome uma viagem da franquia."}{" "}
          Horários no fuso de São Paulo. Veículos e equipe ficam reservados nos
          deslocamentos selecionados.
        </p>
        {allowPackages && (
          <Field label="Pacote (opcional)">
            <select
              value={packageId}
              disabled={edit && !!initial?.package_snapshot}
              onChange={(e) => {
                setPackageId(e.target.value);
                const p = packages.find((p) => p.id === e.target.value);
                if (p?.itinerary) {
                  const snapshot = {
                    ...p.itinerary,
                    id: p.id,
                    name: p.name,
                    version: p.version || 1,
                  };
                  setSelectedPackage(snapshot);
                  setSelectedRoute(null);
                  setMode("multi_destination");
                  setLegs(packageLegs(snapshot, baseDate));
                  setAllocations((current) =>
                    current.map((a) => ({
                      ...a,
                      routes: [],
                      leg_positions: [],
                    })),
                  );
                } else if (selectedPackage) {
                  setSelectedPackage(null);
                  setMode("round_trip");
                  setLegs([blankLeg(), blankLeg()]);
                  setAllocations((current) =>
                    current.map((a) => ({
                      ...a,
                      routes: [],
                      leg_positions: [],
                    })),
                  );
                }
                if (p) {
                  setName(p.name);
                  setDestination(p.destination);
                  setPrice(moneyInput(p.price_cents));
                  if (legacyEdit) updateLeg(0, { destination: p.destination });
                }
              }}
            >
              <option value="">Viagem avulsa</option>
              {selectedPackage &&
                !packages.some((p) => p.id === packageId && p.is_active) && (
                  <option value={packageId}>
                    {selectedPackage.name} · roteiro desta saída
                  </option>
                )}
              {packages
                .filter((p) => p.is_active)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </Field>
        )}
        <Field label="Nome da viagem">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
            maxLength={150}
          />
        </Field>
        <div className="form-grid">
          <Field label="Destino comercial">
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              required
              minLength={2}
              maxLength={150}
            />
          </Field>
          <Field label="Valor por passageiro (R$)">
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
              inputMode="decimal"
            />
          </Field>
        </div>
        {selectedPackage && (
          <>
            <PackageProgram itinerary={selectedPackage} />
            <p>
              <strong>
                Esta saída consumirá {selectedPackage.destinations.length}{" "}
                {selectedPackage.destinations.length === 1
                  ? "viagem"
                  : "viagens"}{" "}
                da franquia, com retorno incluído.
              </strong>
            </p>
            <Field label="Data inicial do pacote">
              <input
                type="date"
                required
                value={baseDate}
                onChange={(e) => {
                  setBaseDate(e.target.value);
                  setLegs(packageLegs(selectedPackage, e.target.value));
                }}
              />
            </Field>
            {legs.map((leg, index) => (
              <fieldset className="operation-card" key={index}>
                <legend>
                  Deslocamento {index + 1} ·{" "}
                  {selectedPackage.steps[index].destination_position
                    ? "Destino comercial"
                    : "Passeio / retorno"}
                </legend>
                <p>
                  {leg.origin} / {leg.origin_uf} → {leg.destination} /{" "}
                  {leg.destination_uf}
                </p>
                <p className="muted">
                  {leg.origin_address} → {leg.destination_address}
                </p>
                <ol>
                  {leg.stops.map((stop, i) => (
                    <li key={i}>
                      {stop.name} · {stopKind[stop.kind]}
                    </li>
                  ))}
                </ol>
                <Field label={`Saída do deslocamento ${index + 1}`}>
                  <input
                    type="datetime-local"
                    required
                    value={leg.starts_at}
                    onChange={(e) =>
                      updateLeg(index, {
                        starts_at: e.target.value,
                        ...(e.target.value ? {} : { ends_at: "" }),
                      })
                    }
                  />
                </Field>
                <p>
                  Chegada prevista:{" "}
                  {leg.ends_at ? date(instant(leg.ends_at)) : "Informe a saída"}
                </p>
              </fieldset>
            ))}
          </>
        )}
        {!selectedPackage && (
          <>
            <Field label="Rota">
              <select
                required={!legacyEdit}
                value={selectedRoute?.id || ""}
                disabled={edit && !!initial?.route_snapshot}
                onChange={(e) => {
                  const route = routeList.data?.find(
                    (r) => r.id === e.target.value,
                  );
                  if (!route) {
                    setSelectedRoute(null);
                    return;
                  }
                  setSelectedRoute(route);
                  setMode(route.mode);
                  if (!name) setName(route.name);
                  if (!destination) setDestination(route.legs[0].destination);
                  setLegs(
                    route.legs
                      .map<Leg>(
                        ({ duration_minutes, stop_minutes, ...leg }, i) => ({
                          ...leg,
                          starts_at: legs[i]?.starts_at || "",
                          ends_at: legs[i]?.starts_at
                            ? localInput(
                                new Date(
                                  Date.parse(instant(legs[i].starts_at)) +
                                    (duration_minutes + stop_minutes) * 60000,
                                ).toISOString(),
                              )
                            : "",
                          stops: leg.stops.map((stop) => ({
                            ...stop,
                            scheduled_at: null,
                          })),
                        }),
                      )
                      .concat(route.legs.length === 1 ? [blankLeg()] : []),
                  );
                  setAllocations((current) =>
                    current.map((a) => ({ ...a, routes: [] })),
                  );
                }}
              >
                <option value="">
                  {legacyEdit
                    ? "Percurso da viagem existente"
                    : "Selecione uma Rota"}
                </option>
                {selectedRoute &&
                  !routeList.data?.some(
                    (r) => r.id === selectedRoute.id && r.is_active,
                  ) && (
                    <option value={selectedRoute.id}>
                      {selectedRoute.name} · percurso salvo na viagem
                    </option>
                  )}
                {routeList.data
                  ?.filter((r) => r.is_active)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ·{" "}
                      {r.mode === "round_trip" ? "Ida e volta" : "Somente ida"}
                    </option>
                  ))}
              </select>
            </Field>
            {routeList.error && <Alert>{routeList.error.message}</Alert>}
            {!selectedRoute && !legacyEdit && (
              <p className="muted">
                Cadastre o percurso no menu Rotas antes de agendar a viagem.
              </p>
            )}
            {selectedRoute &&
              legs.slice(0, mode === "round_trip" ? 2 : 1).map((leg, index) => (
                <fieldset className="operation-card" key={index}>
                  <legend>{index === 0 ? "Ida" : "Volta"}</legend>
                  <p>
                    <strong>
                      {leg.origin} / {leg.origin_uf} → {leg.destination} /{" "}
                      {leg.destination_uf}
                    </strong>
                  </p>
                  <p>
                    {leg.origin_address} → {leg.destination_address}
                  </p>
                  <ol>
                    {leg.stops.map((stop, i) => (
                      <li key={i}>
                        {stop.name} · {stopKind[stop.kind]}
                        <p className="muted">{stop.address}</p>
                      </li>
                    ))}
                  </ol>
                  <Field label={`Saída da ${index === 0 ? "ida" : "volta"}`}>
                    <input
                      type="datetime-local"
                      required
                      value={leg.starts_at}
                      onChange={(e) =>
                        updateLeg(index, {
                          starts_at: e.target.value,
                          ...(e.target.value ? {} : { ends_at: "" }),
                        })
                      }
                    />
                  </Field>
                  <p className="muted">
                    Duração prevista:{" "}
                    {selectedRoute.legs[index].duration_minutes +
                      selectedRoute.legs[index].stop_minutes}{" "}
                    minutos. Chegada prevista:{" "}
                    {leg.ends_at
                      ? date(instant(leg.ends_at))
                      : "Informe a saída"}
                    .
                  </p>
                </fieldset>
              ))}
          </>
        )}
        {legacyEdit && (
          <>
            <Field label="Tipo de viagem">
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="round_trip">Ida e volta</option>
                <option value="one_way">Somente ida / trecho</option>
              </select>
            </Field>
            {legs.slice(0, mode === "round_trip" ? 2 : 1).map((l, index) => (
              <fieldset className="operation-card" key={index}>
                <legend>{index === 0 ? "Ida" : "Volta"}</legend>
                <div className="form-grid">
                  <CitySelect
                    label={`origem da ${index === 0 ? "ida" : "volta"}`}
                    cityId={l.origin_city_id}
                    uf={l.origin_uf}
                    onChange={(city, uf) =>
                      updateLeg(index, {
                        origin: city?.name || "",
                        origin_city_id: city?.id || null,
                        origin_uf: uf || null,
                      })
                    }
                  />
                  <CitySelect
                    label={`destino da ${index === 0 ? "ida" : "volta"}`}
                    cityId={l.destination_city_id}
                    uf={l.destination_uf}
                    onChange={(city, uf) =>
                      updateLeg(index, {
                        destination: city?.name || "",
                        destination_city_id: city?.id || null,
                        destination_uf: uf || null,
                      })
                    }
                  />
                  <Field
                    label={`Endereço de saída da ${index === 0 ? "ida" : "volta"}`}
                  >
                    <input
                      value={l.origin_address || ""}
                      maxLength={300}
                      placeholder="Terminal, rua, cidade e UF"
                      onChange={(e) =>
                        updateLeg(index, { origin_address: e.target.value })
                      }
                    />
                  </Field>
                  <Field
                    label={`Endereço de chegada da ${index === 0 ? "ida" : "volta"}`}
                  >
                    <input
                      value={l.destination_address || ""}
                      maxLength={300}
                      onChange={(e) =>
                        updateLeg(index, {
                          destination_address: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label={`Saída da ${index === 0 ? "ida" : "volta"}`}>
                    <input
                      type="datetime-local"
                      required
                      value={l.starts_at}
                      onChange={(e) =>
                        updateLeg(index, { starts_at: e.target.value })
                      }
                    />
                  </Field>
                  <Field label={`Chegada da ${index === 0 ? "ida" : "volta"}`}>
                    <input
                      type="datetime-local"
                      required
                      value={l.ends_at}
                      onChange={(e) =>
                        updateLeg(index, { ends_at: e.target.value })
                      }
                    />
                  </Field>
                </div>
                {l.stops.map((s, i) => (
                  <div className="operation-card" key={i}>
                    <Field label={`Parada ${i + 1}`}>
                      <input
                        required
                        minLength={2}
                        maxLength={150}
                        value={s.name}
                        onChange={(e) =>
                          updateLeg(index, {
                            stops: l.stops.map((s, j) =>
                              j === i ? { ...s, name: e.target.value } : s,
                            ),
                          })
                        }
                      />
                    </Field>
                    <Field label={`Endereço da parada ${i + 1}`}>
                      <input
                        value={s.address || ""}
                        maxLength={300}
                        placeholder="Hotel, rua, número, cidade e UF"
                        onChange={(e) =>
                          updateLeg(index, {
                            stops: l.stops.map((stop, j) =>
                              j === i
                                ? { ...stop, address: e.target.value }
                                : stop,
                            ),
                          })
                        }
                      />
                    </Field>
                    <a
                      className="text-button"
                      target="_blank"
                      rel="noopener noreferrer"
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(s.address || `${s.name}, ${l.origin}, ${l.origin_uf || ""}`)}`}
                    >
                      Conferir local no Google Maps
                    </a>
                    <div className="form-grid">
                      <Field label="Operação da parada">
                        <select
                          value={s.kind}
                          onChange={(e) =>
                            updateLeg(index, {
                              stops: l.stops.map((s, j) =>
                                j === i ? { ...s, kind: e.target.value } : s,
                              ),
                            })
                          }
                        >
                          {Object.entries(stopKind).map(([id, label]) => (
                            <option key={id} value={id}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() =>
                        updateLeg(index, {
                          stops: l.stops.filter((_, j) => j !== i),
                        })
                      }
                    >
                      Remover parada
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="button secondary"
                  disabled={l.stops.length >= 50}
                  onClick={() =>
                    updateLeg(index, {
                      stops: [
                        ...l.stops,
                        { name: "", kind: "boarding", scheduled_at: "" },
                      ],
                    })
                  }
                >
                  Adicionar parada à {index === 0 ? "ida" : "volta"}
                </button>
                {index === 0 && mode === "round_trip" && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() =>
                      updateLeg(1, {
                        origin: l.destination,
                        destination: l.origin,
                        origin_city_id: l.destination_city_id,
                        destination_city_id: l.origin_city_id,
                        origin_uf: l.destination_uf,
                        destination_uf: l.origin_uf,
                        origin_address: l.destination_address,
                        destination_address: l.origin_address,
                        ...(!edit
                          ? {
                              stops: [...l.stops].reverse().map((stop) => ({
                                ...stop,
                                kind:
                                  stop.kind === "boarding"
                                    ? "dropoff"
                                    : stop.kind === "dropoff"
                                      ? "boarding"
                                      : "both",
                                scheduled_at: "",
                              })),
                            }
                          : {}),
                      })
                    }
                  >
                    {edit
                      ? "Inverter origem e destino da volta"
                      : "Inverter rota para a volta"}
                  </button>
                )}
              </fieldset>
            ))}
          </>
        )}
        <h3>Veículos e equipe</h3>
        {allocations.map((a, index) => (
          <fieldset className="operation-card" key={index}>
            <legend>Veículo {index + 1}</legend>
            {selectedPackage && (
              <div>
                <p>Deslocamentos atendidos por este veículo e equipe</p>
                {legs.map((leg, i) => {
                  const positions = a.leg_positions?.length
                    ? a.leg_positions
                    : legs.map((_, j) => j + 1);
                  return (
                    <label className="operation-checkbox" key={i}>
                      <input
                        type="checkbox"
                        checked={positions.includes(i + 1)}
                        disabled={
                          positions.length === 1 && positions.includes(i + 1)
                        }
                        onChange={(e) =>
                          updateAllocation(index, {
                            leg_positions: e.target.checked
                              ? [...positions, i + 1].sort((x, y) => x - y)
                              : positions.filter((p) => p !== i + 1),
                          })
                        }
                      />{" "}
                      Deslocamento {i + 1}: {leg.origin} → {leg.destination}
                    </label>
                  );
                })}
              </div>
            )}
            <Field label={`Veículo ${index + 1}`}>
              <select
                required
                value={a.vehicle_id}
                onChange={(e) =>
                  updateAllocation(index, { vehicle_id: e.target.value })
                }
              >
                <option value="">Selecione</option>
                {activeVehicles.map((v) => (
                  <option
                    key={v.id}
                    value={v.id}
                    disabled={
                      !selectedPackage &&
                      allocations.some(
                        (a, i) => i !== index && a.vehicle_id === v.id,
                      )
                    }
                  >
                    {v.name} · {v.plate} · {v.capacity} lugares
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Motorista ${index + 1}`}>
              <select
                required
                value={a.driver_id}
                onChange={(e) =>
                  updateAllocation(index, { driver_id: e.target.value })
                }
              >
                <option value="">Selecione</option>
                {crew
                  .filter((c) => c.role === "driver")
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.full_name}
                    </option>
                  ))}
              </select>
            </Field>
            {legs.slice(0, legCount).map((leg, legIndex) => (
              <div
                key={legIndex}
                hidden={
                  !!a.leg_positions?.length &&
                  !a.leg_positions.includes(legIndex + 1)
                }
              >
                <p>
                  Paradas atendidas neste veículo - {legLabel(mode, legIndex)}
                </p>
                {leg.stops.map((stop, stopIndex) => {
                  const route = a.routes?.find(
                    (r) => r.leg_position === legIndex + 1,
                  );
                  const selected =
                    route?.stop_positions || leg.stops.map((_, i) => i + 1);
                  return (
                    <label className="operation-checkbox" key={stopIndex}>
                      <input
                        type="checkbox"
                        checked={selected.includes(stopIndex + 1)}
                        onChange={(e) =>
                          updateAllocation(index, {
                            routes: [
                              ...(a.routes || []).filter(
                                (r) => r.leg_position !== legIndex + 1,
                              ),
                              {
                                leg_position: legIndex + 1,
                                stop_positions: e.target.checked
                                  ? [...selected, stopIndex + 1].sort(
                                      (a, b) => a - b,
                                    )
                                  : selected.filter((p) => p !== stopIndex + 1),
                              },
                            ],
                          })
                        }
                      />
                      {stop.name || `Parada ${stopIndex + 1}`} - veículo{" "}
                      {index + 1}
                    </label>
                  );
                })}
              </div>
            ))}
            <p>Guias deste veículo</p>
            {crew
              .filter((c) => c.role === "guide")
              .map((c) => (
                <label className="operation-checkbox" key={c.id}>
                  <input
                    type="checkbox"
                    checked={a.guide_ids.includes(c.id)}
                    onChange={(e) =>
                      updateAllocation(index, {
                        guide_ids: e.target.checked
                          ? [...a.guide_ids, c.id]
                          : a.guide_ids.filter((id) => id !== c.id),
                      })
                    }
                  />
                  {c.full_name}
                </label>
              ))}
            {allocations.length > 1 &&
              (!edit ||
                !initial?.vehicles.some(
                  (v) => v.vehicle_id === a.vehicle_id,
                )) && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    setAllocations(allocations.filter((_, i) => i !== index))
                  }
                >
                  Remover veículo
                </button>
              )}
          </fieldset>
        ))}
        <button
          type="button"
          className="button secondary"
          disabled={allocations.length >= activeVehicles.length}
          onClick={() =>
            setAllocations([
              ...allocations,
              { vehicle_id: "", driver_id: "", guide_ids: [] },
            ])
          }
        >
          Adicionar veículo
        </button>
        <p>
          <strong>
            Capacidade total:{" "}
            {allocations.reduce(
              (sum, a) =>
                sum +
                (activeVehicles.find((v) => v.id === a.vehicle_id)?.capacity ||
                  0),
              0,
            )}{" "}
            lugares
          </strong>
        </p>
        {!activeVehicles.length && (
          <Alert>
            Cadastre um veículo ativo na Frota antes de criar a viagem.
          </Alert>
        )}
        {!crew.some((c) => c.role === "driver") && (
          <Alert>
            O administrador deve cadastrar um motorista ativo na Equipe.
          </Alert>
        )}
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Voltar
          </button>
          <button
            className="button primary"
            disabled={
              pending ||
              !activeVehicles.length ||
              !crew.some((c) => c.role === "driver")
            }
          >
            {pending
              ? "Salvando…"
              : edit
                ? "Salvar alterações"
                : "Criar viagem"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
