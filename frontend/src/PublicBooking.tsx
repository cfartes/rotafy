import {
  PassengerExceptions,
  type PassengerDocuments,
} from "./components/PassengerExceptions";
import { useState, type FormEvent, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert, Field } from "./components/ui";
import { money } from "./billing/types";
import "./public-sales.css";

type Company = {
  id: string;
  slug: string;
  trade_name: string;
  primary_color: string;
  accent_color: string;
  has_logo: boolean;
};
type Trip = {
  requires_cpf?: boolean;
  geography_complete?: boolean;
  id: string;
  name: string;
  destination: string;
  starts_at: string;
  ends_at: string;
  price_cents: number;
  mode: string;
  description?: string;
  legs: {
    id: string;
    origin: string;
    destination: string;
    stops: { name: string; kind: string }[];
  }[];
};
type Capacity = {
  can_book: boolean;
  message: string;
  suggested_allocation_id: string | null;
  vehicles: {
    allocation_id: string;
    name: string;
    available: number;
    fits_family: boolean;
  }[];
};
const date = (v: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(v));
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível concluir.";
function secret() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}
function brandText(color: string) {
  const channels = [1, 3, 5].map((i) => {
    const value = parseInt(color.slice(i, i + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722 >
    0.179
    ? "#000000"
    : "#ffffff";
}
function Brand({ company }: { company: Company }) {
  return (
    <header className="public-brand">
      <a href={`/comprar/${company.slug}`}>
        {company.has_logo ? (
          <img
            src={`/api/v1/public/${company.slug}/logo`}
            alt={company.trade_name}
          />
        ) : (
          <span className="public-monogram">
            {company.trade_name.slice(0, 1)}
          </span>
        )}
        <strong>{company.trade_name}</strong>
      </a>
      <span>Reservas de viagens</span>
    </header>
  );
}

export function PublicBooking() {
  const parts = window.location.pathname.split("/");
  const slug = parts[2] || "";
  const tripId = parts[3];
  const catalog = useQuery({
    queryKey: ["public", slug],
    queryFn: () =>
      api<{ company: Company; trips: Trip[] }>(
        `/public/${encodeURIComponent(slug)}/catalog`,
      ),
  });
  const detail = useQuery({
    queryKey: ["public", slug, tripId],
    queryFn: () =>
      api<{ company: Company; trip: Trip; availability: Capacity }>(
        `/public/${encodeURIComponent(slug)}/trips/${tripId}`,
      ),
    enabled: !!tripId,
  });
  const company = catalog.data?.company;
  const error = catalog.error || detail.error;
  return (
    <main
      className="public-site"
      style={
        company
          ? ({
              "--public-color": company.primary_color,
              "--public-on-color": brandText(company.primary_color),
            } as CSSProperties)
          : undefined
      }
    >
      {company && <Brand company={company} />}
      <div className="public-container">
        {error ? (
          <Alert>{message(error)}</Alert>
        ) : catalog.isPending ? (
          <p>Carregando viagens…</p>
        ) : tripId ? (
          detail.data ? (
            <BookingForm
              company={detail.data.company}
              trip={detail.data.trip}
            />
          ) : (
            <p>Carregando viagem…</p>
          )
        ) : (
          <>
            <section className="public-intro">
              <p className="eyebrow">SUA PRÓXIMA VIAGEM</p>
              <h1>
                Escolha o destino.
                <br />
                Viaje com sua família.
              </h1>
              <p>
                Consulte datas, pontos e lugares. Solicite sua reserva e
                acompanhe a confirmação da agência.
              </p>
            </section>
            <div className="public-catalog">
              {catalog.data?.trips.map((t) => (
                <article className="public-trip-card" key={t.id}>
                  <p className="eyebrow">{t.destination}</p>
                  <h2>{t.name}</h2>
                  <p>
                    {date(t.starts_at)}
                    <br />
                    <span className="muted">
                      Até {date(t.ends_at)} ·{" "}
                      {t.mode === "round_trip" ? "Ida e volta" : "Somente ida"}
                    </span>
                  </p>
                  {t.description && <p>{t.description}</p>}
                  <strong>
                    {money(t.price_cents)} <small>por passageiro</small>
                  </strong>
                  <a
                    className="button primary"
                    href={`/comprar/${slug}/${t.id}`}
                  >
                    Ver viagem e reservar
                  </a>
                </article>
              ))}
            </div>
            {!catalog.data?.trips.length && (
              <section className="public-trip-card">
                <h2>Novas viagens em breve</h2>
                <p>A agência ainda não publicou viagens disponíveis.</p>
              </section>
            )}
          </>
        )}
      </div>
      <footer className="public-footer">
        Nexus Rotafy · Reservas com confirmação pela agência
      </footer>
    </main>
  );
}

function BookingForm({ company, trip }: { company: Company; trip: Trip }) {
  const [key] = useState(() => crypto.randomUUID());
  const [token] = useState(() => `rt.${company.id}.${secret()}`);
  const [passengers, setPassengers] = useState<
    (PassengerDocuments & { full_name: string; cpf: string })[]
  >([{ full_name: "", cpf: "" }]);
  const [journeys, setJourneys] = useState(
    trip.legs.map((l) => ({
      leg_id: l.id,
      boarding_position: 0,
      dropoff_position: l.stops.length + 1,
    })),
  );
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const valid = journeys.every((j) => j.boarding_position < j.dropoff_position);
  const availability = useQuery({
    queryKey: ["public-availability", trip.id, passengers.length, journeys],
    queryFn: () =>
      post<Capacity>(`/public/${company.slug}/trips/${trip.id}/availability`, {
        group_size: passengers.length,
        journeys,
      }),
    enabled: valid,
    refetchInterval: 15000,
  });
  const suggestion = availability.data?.vehicles.find(
    (v) => v.allocation_id === availability.data?.suggested_allocation_id,
  );
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      await post(`/public/${company.slug}/trips/${trip.id}/reservations`, {
        operation_key: key,
        access_token: token,
        contact_name: form.get("contact_name"),
        phone: form.get("phone"),
        phone_country: String(form.get("country") || "").toUpperCase() || null,
        passengers: passengers.map((p) => ({ ...p, cpf: p.cpf || null })),
        journeys,
      });
      window.location.assign(`/acompanhar#token=${encodeURIComponent(token)}`);
    } catch (e) {
      setError(message(e));
      await availability.refetch();
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <a href={`/comprar/${company.slug}`} className="public-back">
        ← Todas as viagens
      </a>
      <section className="public-intro">
        <p className="eyebrow">{trip.destination}</p>
        <h1>{trip.name}</h1>
        <p>
          {date(trip.starts_at)} até {date(trip.ends_at)}
        </p>
        <strong>{money(trip.price_cents)} por passageiro</strong>
      </section>
      <div className="public-booking-grid">
        <form className="public-trip-card modal-form" onSubmit={submit}>
          <h2>Reserve para sua família</h2>
          <Field label="Nome do responsável">
            <input name="contact_name" required minLength={2} maxLength={150} />
          </Field>
          <div className="form-grid">
            <Field label="Telefone da família">
              <input
                type="tel"
                name="phone"
                required
                maxLength={40}
                placeholder="+55 47 99999-9999"
              />
            </Field>
            <Field label="País do telefone (sigla ISO)">
              <input name="country" defaultValue="BR" maxLength={2} />
            </Field>
          </div>
          <p className="muted">
            Um telefone para toda a família. Informe o país para números
            nacionais ou use + e o código internacional.
          </p>
          {trip.requires_cpf && (
            <p className="muted">
              Viagem interestadual: CPF de todos os passageiros, exceto
              estrangeiros e menores de 5 anos.
            </p>
          )}
          {passengers.map((p, i) => (
            <fieldset className="operation-card" key={i}>
              <legend>Passageiro {i + 1}</legend>
              <Field label={`Nome do passageiro ${i + 1}`}>
                <input
                  required
                  minLength={2}
                  maxLength={150}
                  value={p.full_name}
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, j) =>
                        i === j ? { ...p, full_name: e.target.value } : p,
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
                  value={p.cpf}
                  maxLength={14}
                  inputMode="numeric"
                  onChange={(e) =>
                    setPassengers(
                      passengers.map((p, j) =>
                        i === j ? { ...p, cpf: e.target.value } : p,
                      ),
                    )
                  }
                />
              </Field>
              {passengers.length > 1 && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    setPassengers(passengers.filter((_, j) => i !== j))
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
          {trip.legs.map((l, i) => (
            <fieldset key={l.id} className="operation-card">
              <legend>
                {i === 0 ? "Ida" : "Volta"}: {l.origin} → {l.destination}
              </legend>
              <Field label={`Embarque da ${i === 0 ? "ida" : "volta"}`}>
                <select
                  aria-label={`Embarque da ${i === 0 ? "ida" : "volta"}`}
                  value={journeys[i].boarding_position}
                  onChange={(e) =>
                    setJourneys(
                      journeys.map((j, index) =>
                        i === index
                          ? { ...j, boarding_position: Number(e.target.value) }
                          : j,
                      ),
                    )
                  }
                >
                  <option value={0}>{l.origin}</option>
                  {l.stops.map(
                    (s, index) =>
                      ["boarding", "both"].includes(s.kind) && (
                        <option key={index} value={index + 1}>
                          {s.name}
                        </option>
                      ),
                  )}
                </select>
              </Field>
              <Field label={`Desembarque da ${i === 0 ? "ida" : "volta"}`}>
                <select
                  aria-label={`Desembarque da ${i === 0 ? "ida" : "volta"}`}
                  value={journeys[i].dropoff_position}
                  onChange={(e) =>
                    setJourneys(
                      journeys.map((j, index) =>
                        i === index
                          ? { ...j, dropoff_position: Number(e.target.value) }
                          : j,
                      ),
                    )
                  }
                >
                  {l.stops.map(
                    (s, index) =>
                      ["dropoff", "both"].includes(s.kind) && (
                        <option key={index} value={index + 1}>
                          {s.name}
                        </option>
                      ),
                  )}
                  <option value={l.stops.length + 1}>{l.destination}</option>
                </select>
              </Field>
            </fieldset>
          ))}
          {!valid && (
            <Alert>
              Selecione desembarque depois do embarque em todos os trechos.
            </Alert>
          )}
          {suggestion && (
            <p className="reservation-suggestion">
              Sua família de {passengers.length} pessoas cabe inteira em{" "}
              {suggestion.name}.
            </p>
          )}
          {availability.data && !availability.data.can_book && (
            <Alert>{availability.data.message}</Alert>
          )}
          {availability.data && !availability.data.can_book && (
            <button
              type="button"
              className="button secondary"
              disabled={pending}
              onClick={async () => {
                setPending(true);
                try {
                  await post(
                    `/public/${company.slug}/trips/${trip.id}/unavailability`,
                    { group_size: passengers.length, journeys },
                  );
                  setError(
                    "Agência avisada sobre a falta de lugares para sua família.",
                  );
                } catch (e) {
                  setError(message(e));
                } finally {
                  setPending(false);
                }
              }}
            >
              Avisar agência
            </button>
          )}
          {availability.error && <Alert>{message(availability.error)}</Alert>}
          {error && <Alert>{error}</Alert>}
          <button
            className="button primary"
            disabled={pending || !valid || !availability.data?.can_book}
          >
            {pending ? "Solicitando…" : "Solicitar reserva"}
          </button>
        </form>
        <aside className="public-trip-card public-summary">
          <h2>Resumo da solicitação</h2>
          <p>
            {passengers.length}{" "}
            {passengers.length === 1 ? "passageiro" : "passageiros"}
          </p>
          <strong>{money(trip.price_cents * passengers.length)}</strong>
          <p>
            Os lugares ficam bloqueados por 15 minutos. A agência precisa
            confirmar a reserva dentro desse prazo.
          </p>
          <p>
            Esta página não recebe pagamentos. Combine o pagamento diretamente
            com a agência.
          </p>
          <p>
            Após solicitar, você receberá um link privado para acompanhar sua
            família.
          </p>
        </aside>
      </div>
    </>
  );
}

type TrackingData = {
  contact_name: string;
  status: string;
  is_paid: boolean;
  total_cents: number;
  expires_at: string | null;
  vehicle_name: string;
  passengers: { full_name: string }[];
  trip: {
    name: string;
    destination: string;
    starts_at: string;
    ends_at: string;
  };
  journeys: { boarding: string; dropoff: string; starts_at: string }[];
};
export function TrackingPage() {
  const token =
    new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
  const tracking = useQuery({
    queryKey: ["buyer-tracking", token],
    queryFn: () => post<TrackingData>("/public/tracking", { token }),
    enabled: !!token,
    refetchInterval: 15000,
  });
  const data = tracking.data;
  const labels: Record<string, string> = {
    pending: "Aguardando confirmação da agência",
    confirmed: "Reserva confirmada",
    cancelled: "Reserva cancelada",
    expired: "O bloqueio de lugares expirou",
  };
  return (
    <main className="public-site">
      <div className="public-container tracking-container">
        <p className="eyebrow">ACOMPANHAMENTO PRIVADO</p>
        <h1>Sua reserva</h1>
        {!token ? (
          <Alert>Abra o link privado fornecido ao solicitar sua reserva.</Alert>
        ) : tracking.error ? (
          <Alert>{message(tracking.error)}</Alert>
        ) : data ? (
          <section className="public-trip-card">
            <p className="tracking-status">{labels[data.status]}</p>
            <h2>{data.trip.name}</h2>
            <p>
              {date(data.trip.starts_at)} até {date(data.trip.ends_at)}
            </p>
            <p>Responsável: {data.contact_name}</p>
            <p>Veículo: {data.vehicle_name}</p>
            <h3>Passageiros</h3>
            {data.passengers.map((p, i) => (
              <p key={i}>{p.full_name}</p>
            ))}
            {data.journeys.map((j, i) => (
              <p key={i}>
                {j.boarding} → {j.dropoff}
              </p>
            ))}
            <p>
              <strong>
                {money(data.total_cents)} · {data.is_paid ? "PAGO" : "NÃO PAGO"}
              </strong>
            </p>
            {data.status === "pending" && data.expires_at && (
              <Alert>
                Confirmação necessária até {date(data.expires_at)}. Combine os
                próximos passos diretamente com a agência.
              </Alert>
            )}
            {data.status === "expired" && (
              <p>
                O prazo encerrou e os lugares foram liberados. Consulte a
                agência para solicitar outra reserva.
              </p>
            )}
            <Field label="Link privado da reserva">
              <textarea
                readOnly
                value={window.location.href}
                onFocus={(e) => e.currentTarget.select()}
              />
            </Field>
            <p className="muted">
              Guarde este link. Qualquer pessoa com acesso a ele poderá
              consultar esta reserva.
            </p>
            <button
              className="button secondary"
              onClick={() => tracking.refetch()}
            >
              Atualizar situação
            </button>
          </section>
        ) : (
          <p>Consultando sua reserva…</p>
        )}
      </div>
    </main>
  );
}
