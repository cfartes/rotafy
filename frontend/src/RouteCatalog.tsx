import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, patch, post } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { CitySelect } from "./components/CitySelect";

export type RouteStop = { name: string; address: string; kind: string };
export type RouteLeg = {
  origin: string;
  destination: string;
  origin_city_id: number | null;
  destination_city_id: number | null;
  origin_uf: string | null;
  destination_uf: string | null;
  origin_address: string;
  destination_address: string;
  duration_minutes: number;
  stop_minutes: number;
  stops: RouteStop[];
};
export type SavedRoute = {
  id: string;
  name: string;
  version: number;
  is_active: boolean;
  mode: string;
  legs: RouteLeg[];
};
const blank = (): RouteLeg => ({
  origin: "",
  destination: "",
  origin_city_id: null,
  destination_city_id: null,
  origin_uf: null,
  destination_uf: null,
  origin_address: "",
  destination_address: "",
  duration_minutes: 60,
  stop_minutes: 0,
  stops: [],
});
const kinds: Record<string, string> = {
  boarding: "Embarque",
  dropoff: "Desembarque",
  both: "Embarque e desembarque",
};

export function RouteCatalog() {
  const client = useQueryClient();
  const routes = useQuery({
    queryKey: ["routes"],
    queryFn: () => api<SavedRoute[]>("/routes"),
  });
  const [editing, setEditing] = useState<SavedRoute | null | undefined>(
    undefined,
  );
  const [duplicate, setDuplicate] = useState<SavedRoute | null>(null);
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          <h2>Rotas</h2>
          <p className="muted">
            Cadastre o percurso uma vez e utilize em diferentes datas. Rotas não
            consomem a franquia.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setDuplicate(null);
            setEditing(null);
          }}
        >
          Nova Rota
        </button>
      </header>
      {routes.error && <Alert>{routes.error.message}</Alert>}
      {routes.isPending && <p>Carregando rotas…</p>}
      {routes.data?.length === 0 && (
        <p className="muted">
          Nenhuma Rota cadastrada. Você também pode salvar o percurso de uma
          viagem existente como Rota.
        </p>
      )}
      <div className="trip-detail-grid">
        {routes.data?.map((route) => (
          <article className="operation-card" key={route.id}>
            <h3>{route.name}</h3>
            <p>
              {route.legs[0].origin} / {route.legs[0].origin_uf} →{" "}
              {route.legs[0].destination} / {route.legs[0].destination_uf}
            </p>
            <p>
              {route.mode === "round_trip" ? "Ida e volta" : "Somente ida"} ·{" "}
              {route.is_active ? "Ativa" : "Inativa"} · versão {route.version}
            </p>
            {route.legs.map((leg, i) => (
              <p key={i}>
                {i === 0 ? "Ida" : "Volta"}:{" "}
                {leg.duration_minutes + leg.stop_minutes} min previstos ·{" "}
                {leg.stops.length} paradas
              </p>
            ))}
            <button
              className="button secondary"
              onClick={() => {
                setDuplicate(null);
                setEditing(route);
              }}
            >
              Editar Rota
            </button>{" "}
            <button
              className="button secondary"
              onClick={() => {
                setDuplicate(route);
                setEditing(null);
              }}
            >
              Duplicar Rota
            </button>
          </article>
        ))}
      </div>
      {editing !== undefined && (
        <RouteEditor
          initial={editing || duplicate}
          duplicate={!!duplicate}
          onClose={() => setEditing(undefined)}
          onSaved={async () => {
            await client.invalidateQueries({ queryKey: ["routes"] });
            setEditing(undefined);
          }}
        />
      )}
    </section>
  );
}

function RouteEditor({
  initial,
  duplicate,
  onClose,
  onSaved,
}: {
  initial: SavedRoute | null;
  duplicate: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState(
    initial ? `${initial.name}${duplicate ? " (cópia)" : ""}` : "",
  );
  const [mode, setMode] = useState(initial?.mode || "one_way");
  const [legs, setLegs] = useState<RouteLeg[]>(
    initial
      ? [...initial.legs, ...(initial.legs.length === 1 ? [blank()] : [])]
      : [blank(), blank()],
  );
  const [active, setActive] = useState(
    duplicate ? true : (initial?.is_active ?? true),
  );
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  function change(index: number, update: Partial<RouteLeg>) {
    setLegs((current) =>
      current.map((leg, i) => (i === index ? { ...leg, ...update } : leg)),
    );
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      const editing = !!initial && !duplicate;
      await (editing ? patch : post)(
        editing ? `/routes/${initial.id}` : "/routes",
        {
          name,
          mode,
          is_active: active,
          legs: legs.slice(0, mode === "round_trip" ? 2 : 1),
          ...(editing ? { expected_version: initial.version } : {}),
        },
      );
      await onSaved();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Não foi possível salvar a Rota.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal
      title={initial && !duplicate ? "Editar Rota" : "Nova Rota"}
      wide
      onClose={onClose}
    >
      <form className="modal-form" onSubmit={submit}>
        <p className="muted">
          Alterações serão utilizadas nas novas viagens. Viagens existentes
          preservam o percurso original.
        </p>
        <Field label="Nome da Rota">
          <input
            required
            minLength={2}
            maxLength={150}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Sentidos">
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="one_way">Somente ida</option>
            <option value="round_trip">Ida e volta</option>
          </select>
        </Field>
        {legs.slice(0, mode === "round_trip" ? 2 : 1).map((leg, index) => (
          <fieldset className="operation-card" key={index}>
            <legend>{index === 0 ? "Ida" : "Volta"}</legend>
            <div className="form-grid">
              <CitySelect
                searchable={false}
                label={`origem da ${index === 0 ? "ida" : "volta"}`}
                cityId={leg.origin_city_id}
                uf={leg.origin_uf}
                onChange={(city, uf) =>
                  change(index, {
                    origin: city?.name || "",
                    origin_city_id: city?.id || null,
                    origin_uf: uf || null,
                  })
                }
              />
              <CitySelect
                searchable={false}
                label={`destino da ${index === 0 ? "ida" : "volta"}`}
                cityId={leg.destination_city_id}
                uf={leg.destination_uf}
                onChange={(city, uf) =>
                  change(index, {
                    destination: city?.name || "",
                    destination_city_id: city?.id || null,
                    destination_uf: uf || null,
                  })
                }
              />
              <Field label="Endereço de saída">
                <input
                  value={leg.origin_address}
                  maxLength={300}
                  onChange={(e) =>
                    change(index, { origin_address: e.target.value })
                  }
                />
              </Field>
              <Field label="Endereço de chegada">
                <input
                  value={leg.destination_address}
                  maxLength={300}
                  onChange={(e) =>
                    change(index, { destination_address: e.target.value })
                  }
                />
              </Field>
              <Field label="Deslocamento estimado (minutos)">
                <input
                  type="number"
                  required
                  min={1}
                  max={10080}
                  step={1}
                  value={leg.duration_minutes}
                  onChange={(e) =>
                    change(index, { duration_minutes: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Tempo adicional total nas paradas (minutos)">
                <input
                  type="number"
                  required
                  min={0}
                  max={10080}
                  step={1}
                  value={leg.stop_minutes}
                  onChange={(e) =>
                    change(index, { stop_minutes: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
            <p className="muted">
              Duração prevista: {leg.duration_minutes + leg.stop_minutes}{" "}
              minutos. Informe o tempo de deslocamento e acrescente o tempo de
              atendimento nas paradas.
            </p>
            {leg.stops.map((stop, position) => (
              <div className="operation-card" key={position}>
                <Field label={`Parada ${position + 1}`}>
                  <input
                    required
                    minLength={2}
                    maxLength={150}
                    value={stop.name}
                    onChange={(e) =>
                      change(index, {
                        stops: leg.stops.map((s, i) =>
                          i === position ? { ...s, name: e.target.value } : s,
                        ),
                      })
                    }
                  />
                </Field>
                <Field label={`Endereço da parada ${position + 1}`}>
                  <input
                    maxLength={300}
                    value={stop.address}
                    onChange={(e) =>
                      change(index, {
                        stops: leg.stops.map((s, i) =>
                          i === position
                            ? { ...s, address: e.target.value }
                            : s,
                        ),
                      })
                    }
                  />
                </Field>
                <Field label="Finalidade">
                  <select
                    value={stop.kind}
                    onChange={(e) =>
                      change(index, {
                        stops: leg.stops.map((s, i) =>
                          i === position ? { ...s, kind: e.target.value } : s,
                        ),
                      })
                    }
                  >
                    {Object.entries(kinds).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </Field>
                <a
                  className="text-button"
                  target="_blank"
                  rel="noopener noreferrer"
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(stop.address || `${stop.name}, ${leg.origin}, ${leg.origin_uf}`)}`}
                >
                  Conferir local no Google Maps
                </a>
                <div className="modal-actions">
                  {[-1, 1].map((offset) => (
                    <button
                      key={offset}
                      type="button"
                      className="button secondary"
                      disabled={
                        position + offset < 0 ||
                        position + offset >= leg.stops.length
                      }
                      onClick={() => {
                        const stops = [...leg.stops];
                        [stops[position], stops[position + offset]] = [
                          stops[position + offset],
                          stops[position],
                        ];
                        change(index, { stops });
                      }}
                    >
                      {offset === -1 ? "Mover acima" : "Mover abaixo"}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() =>
                      change(index, {
                        stops: leg.stops.filter((_, i) => i !== position),
                      })
                    }
                  >
                    Remover parada
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="button secondary"
              disabled={leg.stops.length >= 50}
              onClick={() =>
                change(index, {
                  stops: [
                    ...leg.stops,
                    { name: "", address: "", kind: "boarding" },
                  ],
                })
              }
            >
              Adicionar parada
            </button>{" "}
            {index === 0 && mode === "round_trip" && (
              <button
                type="button"
                className="button secondary"
                onClick={() =>
                  change(1, {
                    ...leg,
                    origin: leg.destination,
                    destination: leg.origin,
                    origin_city_id: leg.destination_city_id,
                    destination_city_id: leg.origin_city_id,
                    origin_uf: leg.destination_uf,
                    destination_uf: leg.origin_uf,
                    origin_address: leg.destination_address,
                    destination_address: leg.origin_address,
                    stops: [...leg.stops].reverse().map((s) => ({
                      ...s,
                      kind:
                        s.kind === "boarding"
                          ? "dropoff"
                          : s.kind === "dropoff"
                            ? "boarding"
                            : "both",
                    })),
                  })
                }
              >
                Gerar volta invertendo a ida
              </button>
            )}
          </fieldset>
        ))}
        <label>
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
          />{" "}
          Rota ativa para novas viagens
        </label>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar Rota"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
