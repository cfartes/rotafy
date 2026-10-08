import { Field } from "./components/ui";
import type { PackageItinerary } from "./PackageItinerary";
import type { SavedRoute } from "./RouteCatalog";

export function isDailyPackage(value: PackageItinerary) {
  return (
    value.steps.length === value.destinations.length * 2 &&
    value.destinations.every((_, i) => {
      const out = value.steps[i * 2],
        back = value.steps[i * 2 + 1];
      return (
        out.destination_position === i + 1 &&
        back.destination_position === null &&
        out.day === back.day &&
        out.route_id === back.route_id &&
        out.route_leg_position === 1 &&
        back.route_leg_position === 2
      );
    })
  );
}

export function DailyPackageEditor({
  value,
  onChange,
  routes,
}: {
  value: PackageItinerary;
  onChange: (value: PackageItinerary) => void;
  routes: SavedRoute[];
}) {
  const available = routes.filter(
    (route) =>
      route.is_active && route.mode === "round_trip" && route.legs.length === 2,
  );
  function changePair(
    index: number,
    outChanges: Partial<PackageItinerary["steps"][number]>,
    backChanges: Partial<PackageItinerary["steps"][number]>,
  ) {
    onChange({
      ...value,
      steps: value.steps.map((s, i) =>
        i === index * 2
          ? { ...s, ...outChanges }
          : i === index * 2 + 1
            ? { ...s, ...backChanges }
            : s,
      ),
    });
  }
  return (
    <>
      <div className="package-rules">
        <h3>Um passeio por caixa, com ida e volta incluídas</h3>
        <p>
          Escolha uma Rota de ida e volta para cada destino. O sistema associa a
          chegada e monta o retorno automaticamente. Todos os passeios devem
          partir da mesma cidade e retornar a ela.
        </p>
        <p>
          Dia 1 é o início da viagem; os próximos passeios podem acontecer nos
          dias 2, 4 etc. O horário de retorno é a saída do destino, não a
          chegada à cidade de origem. Cada destino consome uma viagem da
          franquia, com venda do pacote completo.
        </p>
        <p>
          Para hospedagem ou continuação para outra cidade, escolha “Viagem com
          destinos em sequência”.
        </p>
      </div>
      {!available.length && (
        <p>
          Cadastre uma Rota ativa de ida e volta antes de configurar os
          passeios.
        </p>
      )}
      {value.destinations.map((destination, index) => {
        const out = value.steps[index * 2],
          back = value.steps[index * 2 + 1];
        const selected = routes.find((r) => r.id === out.route_id);
        return (
          <fieldset className="operation-card package-route-card" key={index}>
            <legend>
              Passeio {index + 1}
              {destination.name ? ` · ${destination.name}` : ""}
            </legend>
            <Field label={`Rota de ida e volta do passeio ${index + 1}`}>
              <select
                required
                value={out.route_id}
                onChange={(e) => {
                  const route = available.find((r) => r.id === e.target.value);
                  const steps = value.steps.map((s, i) =>
                    i === index * 2 || i === index * 2 + 1
                      ? { ...s, route_id: e.target.value, leg: undefined }
                      : s,
                  );
                  onChange({
                    ...value,
                    steps,
                    destinations: value.destinations.map((d, i) =>
                      i === index
                        ? {
                            ...d,
                            name: route?.legs[0].destination || "",
                            city_id: route?.legs[0].destination_city_id || null,
                            city: undefined,
                          }
                        : d,
                    ),
                  });
                }}
              >
                <option value="">Selecione uma Rota de ida e volta</option>
                {out.route_id &&
                  !available.some((r) => r.id === out.route_id) && (
                    <option value={out.route_id}>
                      Rota salva indisponível · escolha uma Rota ativa
                    </option>
                  )}
                {available.map((route) => (
                  <option key={route.id} value={route.id}>
                    {route.name} · {route.legs[0].origin} →{" "}
                    {route.legs[0].destination} → {route.legs[1].destination}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Nome do destino do passeio ${index + 1}`}>
              <input
                required
                minLength={2}
                maxLength={150}
                value={destination.name}
                onChange={(e) =>
                  onChange({
                    ...value,
                    destinations: value.destinations.map((d, i) =>
                      i === index ? { ...d, name: e.target.value } : d,
                    ),
                  })
                }
              />
            </Field>
            <div className="form-grid">
              <Field label={`Dia do passeio ${index + 1}`}>
                <input
                  required
                  type="number"
                  min={index === 0 ? 1 : value.steps[(index - 1) * 2].day + 1}
                  max={index === 0 ? 1 : 60}
                  value={out.day}
                  onChange={(e) =>
                    changePair(
                      index,
                      { day: Number(e.target.value) },
                      { day: Number(e.target.value) },
                    )
                  }
                />
              </Field>
              <Field label={`Saída para o passeio ${index + 1}`}>
                <input
                  required
                  type="time"
                  value={out.departure_time}
                  onChange={(e) =>
                    changePair(index, { departure_time: e.target.value }, {})
                  }
                />
              </Field>
              <Field label={`Retorno saindo do destino ${index + 1}`}>
                <input
                  required
                  type="time"
                  min={out.departure_time}
                  value={back.departure_time}
                  onChange={(e) =>
                    changePair(index, {}, { departure_time: e.target.value })
                  }
                />
              </Field>
            </div>
            {selected && (
              <p className="muted">
                Ida: {selected.legs[0].origin} → {selected.legs[0].destination}.
                Volta: {selected.legs[1].origin} →{" "}
                {selected.legs[1].destination}. A cidade/UF do destino vêm da
                Rota.
              </p>
            )}
            <button
              type="button"
              className="button secondary"
              disabled={value.destinations.length === 1}
              onClick={() => {
                const steps = value.steps
                  .filter((_, i) => i !== index * 2 && i !== index * 2 + 1)
                  .map((s, i) => ({
                    ...s,
                    day: index === 0 ? s.day - value.steps[2].day + 1 : s.day,
                    destination_position: i % 2 === 0 ? i / 2 + 1 : null,
                  }));
                onChange({
                  ...value,
                  steps,
                  destinations: value.destinations.filter(
                    (_, i) => i !== index,
                  ),
                });
              }}
            >
              Remover passeio {index + 1}
            </button>
          </fieldset>
        );
      })}
      <button
        type="button"
        className="button secondary"
        disabled={
          value.destinations.length >= 20 || value.steps.at(-1)!.day >= 60
        }
        onClick={() => {
          const day = value.steps.at(-1)!.day + 1;
          const route_id = "";
          onChange({
            ...value,
            destinations: [...value.destinations, { name: "", city_id: null }],
            steps: [
              ...value.steps,
              {
                day,
                departure_time: "08:00",
                route_id,
                route_leg_position: 1,
                destination_position: value.destinations.length + 1,
              },
              {
                day,
                departure_time: "16:00",
                route_id,
                route_leg_position: 2,
                destination_position: null,
              },
            ],
          });
        }}
      >
        Adicionar passeio
      </button>
      {value.activities.length > 0 && (
        <p>
          Este pacote contém atividades adicionais. Para editá-las, use o
          formato de destinos em sequência; elas serão preservadas.
        </p>
      )}
      <p>
        <strong>
          Esta saída consumirá {value.destinations.length}{" "}
          {value.destinations.length === 1 ? "viagem" : "viagens"} da franquia,
          com retornos incluídos.
        </strong>
      </p>
    </>
  );
}
