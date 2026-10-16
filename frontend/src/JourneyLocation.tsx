import { Field } from "./components/ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type Location = {
  name: string;
  address: string;
  complement: string;
  order: number;
};

export function JourneyLocation({
  label,
  value,
  onChange,
  tripId,
  legId,
  kind,
  onPosition,
}: {
  label: string;
  value?: Location | null;
  onChange: (value: Location | null) => void;
  tripId: string;
  legId: string;
  kind: "boarding" | "dropoff";
  onPosition: (position: number, location: Location) => void;
}) {
  const places = useQuery({
    queryKey: ["boarding-locations", tripId],
    queryFn: () =>
      api<
        Array<{
          leg_id: string;
          boarding_location: Location | null;
          dropoff_location: Location | null;
          boarding_position: number;
          dropoff_position: number;
        }>
      >(`/trips/${tripId}/boarding-locations`),
    staleTime: 0,
  });
  const suggestions = (places.data ?? []).filter(
    (p) => p.leg_id === legId && p[`${kind}_location`],
  );
  return (
    <fieldset className="operation-card">
      <legend>{label}</legend>
      <Field label={`${label}: tipo de local`}>
        <select
          value={value ? "custom" : "route"}
          onChange={(e) =>
            onChange(
              e.target.value === "custom"
                ? { name: "", address: "", complement: "", order: 1 }
                : null,
            )
          }
        >
          <option value="route">Usar o ponto selecionado da viagem</option>
          <option value="custom">Outro local / hotel</option>
        </select>
      </Field>
      {!!suggestions.length && (
        <Field label={`${label}: hotéis já informados nesta viagem`}>
          <select
            value=""
            onChange={(e) => {
              if (!e.target.value) return;
              const point = suggestions[Number(e.target.value)];
              onPosition(point[`${kind}_position`], {
                ...point[`${kind}_location`]!,
              });
            }}
          >
            <option value="">Selecionar um local existente</option>
            {suggestions.map((p, i) => (
              <option key={i} value={i}>
                {p[`${kind}_location`]!.name} · {p[`${kind}_location`]!.address}
              </option>
            ))}
          </select>
        </Field>
      )}
      {value && (
        <>
          <div className="form-grid">
            <Field label={`${label}: nome do hotel ou local`}>
              <input
                required
                minLength={2}
                maxLength={150}
                value={value.name}
                onChange={(e) => onChange({ ...value, name: e.target.value })}
              />
            </Field>
            <Field label={`${label}: endereço completo`}>
              <input
                required
                minLength={8}
                maxLength={300}
                placeholder="Rua, número, bairro, cidade e UF"
                value={value.address}
                onChange={(e) =>
                  onChange({ ...value, address: e.target.value })
                }
              />
            </Field>
            <Field label={`${label}: complemento`}>
              <input
                maxLength={200}
                value={value.complement}
                onChange={(e) =>
                  onChange({ ...value, complement: e.target.value })
                }
              />
            </Field>
            <Field label={`${label}: ordem de visita dos hotéis`}>
              <input
                type="number"
                required
                min={1}
                max={10000}
                value={value.order}
                onChange={(e) =>
                  onChange({ ...value, order: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <p className="muted">
            Embarque: o hotel será visitado após o ponto selecionado acima.
            Desembarque: será visitado antes do ponto selecionado. A ordem
            organiza os hotéis entre esses pontos; confira o roteiro do veículo
            após salvar.
          </p>
        </>
      )}
    </fieldset>
  );
}
