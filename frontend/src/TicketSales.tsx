import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { Alert, Field } from "./components/ui";
import { Reservations } from "./Reservations";
import { money } from "./billing/types";

type Trip = {
  id: string;
  name: string;
  destination: string;
  status: string;
  starts_at: string;
  price_cents: number;
};
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const searchText = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

export function TicketSales({ onLogout }: { onLogout: () => void }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [selling, setSelling] = useState<string | null>(null);
  const trips = useQuery({
    queryKey: ["ticket-sales", "trips"],
    queryFn: () => api<Trip[]>("/trips"),
    refetchInterval: 30000,
  });
  useEffect(() => {
    if (trips.error instanceof ApiError && trips.error.status === 401)
      onLogout();
  }, [trips.error, onLogout]);
  const available = (trips.data ?? [])
    .filter(
      (trip) =>
        trip.status === "scheduled" && new Date(trip.starts_at) > new Date(),
    )
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const filtered = available.filter((trip) =>
    searchText(`${trip.name} ${trip.destination}`).includes(searchText(search)),
  );
  const current = filtered.find((trip) => trip.id === selected);
  if (selling)
    return (
      <Reservations
        key={selling}
        tripId={selling}
        initialCreate
        hideBack
        backLabel="Voltar à venda de bilhetes"
        onBack={() => {
          setSelling(null);
          void trips.refetch();
        }}
        onLogout={onLogout}
      />
    );
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Vender bilhete</h2>
          <p className="muted">
            Selecione a viagem para cadastrar passageiros e reservar os lugares.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={trips.isFetching}
          onClick={() => void trips.refetch()}
        >
          Atualizar viagens
        </button>
      </header>
      <div className="modal-form">
        <div className="form-grid">
          <Field label="Buscar viagem ou destino">
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSelected("");
              }}
              placeholder="Nome da viagem ou cidade"
            />
          </Field>
          <Field label="Viagem para vender bilhete">
            <select
              value={current ? selected : ""}
              onChange={(e) => setSelected(e.target.value)}
              disabled={trips.isPending}
            >
              <option value="">Selecione uma viagem</option>
              {filtered.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name} · {trip.destination} · {date(trip.starts_at)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {trips.isPending && <p>Carregando viagens…</p>}
        {trips.error && (
          <Alert>Não foi possível carregar as viagens. Tente atualizar.</Alert>
        )}
        {!trips.isPending && !trips.error && filtered.length === 0 && (
          <p className="empty-state">
            Nenhuma viagem aberta para venda neste filtro.
          </p>
        )}
        {current && (
          <div className="operation-card">
            <h3>{current.name}</h3>
            <p>
              {current.destination} · {date(current.starts_at)}
            </p>
            <p>{money(current.price_cents)} por passageiro</p>
          </div>
        )}
        <button
          className="button primary"
          disabled={!current || trips.isFetching}
          onClick={() => {
            if (current) setSelling(current.id);
          }}
        >
          Vender bilhete
        </button>
        <p className="muted">
          Viagens concluídas, canceladas, em andamento ou com saída passada não
          aceitam novas vendas. A disponibilidade é conferida antes de confirmar
          a reserva.
        </p>
      </div>
    </section>
  );
}
