import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { type SavedRoute, type RouteLeg } from "./RouteCatalog";
import { Alert, Field } from "./components/ui";
import { CitySelect } from "./components/CitySelect";

export type PackageItinerary = {
  destinations: {
    name: string;
    city_id: number | null;
    city?: { id: number; name: string; uf: string };
  }[];
  steps: {
    day: number;
    departure_time: string;
    route_id: string;
    route_leg_position: number;
    destination_position: number | null;
    leg?: RouteLeg;
    route_name?: string;
  }[];
  activities: { day: number; title: string; description: string }[];
};
export type PackageSnapshot = PackageItinerary & {
  id: string;
  name: string;
  version: number;
};
export const emptyPackageItinerary = (): PackageItinerary => ({
  destinations: [{ name: "", city_id: null }],
  steps: [
    {
      day: 1,
      departure_time: "08:00",
      route_id: "",
      route_leg_position: 1,
      destination_position: 1,
    },
    {
      day: 2,
      departure_time: "16:00",
      route_id: "",
      route_leg_position: 1,
      destination_position: null,
    },
  ],
  activities: [],
});
export function packageItineraryInput(value: PackageItinerary) {
  return {
    destinations: value.destinations.map(({ name, city_id }) => ({
      name,
      city_id,
    })),
    steps: value.steps.map(
      ({
        day,
        departure_time,
        route_id,
        route_leg_position,
        destination_position,
      }) => ({
        day,
        departure_time,
        route_id,
        route_leg_position,
        destination_position,
      }),
    ),
    activities: value.activities,
  };
}

export function packageItineraryErrors(value: PackageItinerary): string[] {
  const errors: string[] = [];
  value.destinations.forEach((destination, index) => {
    const count = value.steps.filter(
      (step) => step.destination_position === index + 1,
    ).length;
    const label = `Destino ${index + 1}${destination.name ? ` (${destination.name})` : ""}`;
    if (count === 0)
      errors.push(
        `${label}: selecione a chegada a este destino na finalidade de um deslocamento.`,
      );
    if (count > 1)
      errors.push(
        `${label}: marque a chegada somente uma vez; nas demais visitas, selecione passeio ou transferência.`,
      );
  });
  const positions = value.steps.flatMap((s) =>
    s.destination_position ? [s.destination_position] : [],
  );
  if (
    positions.some(
      (position, index) => index > 0 && position < positions[index - 1],
    )
  )
    errors.push(
      "As chegadas devem seguir a ordem dos destinos cadastrados. Ajuste a finalidade ou a ordem dos deslocamentos.",
    );
  if (value.steps.at(-1)?.destination_position != null)
    errors.push(
      "O último deslocamento deve ser o retorno à origem, sem destino comercial adicional.",
    );
  if (value.steps[0]?.day !== 1)
    errors.push("O primeiro deslocamento deve começar no dia 1 do pacote.");
  value.steps.forEach((step, index) => {
    const previous = value.steps[index - 1];
    if (
      previous &&
      (step.day < previous.day ||
        (step.day === previous.day &&
          step.departure_time <= previous.departure_time))
    )
      errors.push(
        `Deslocamento ${index + 1}: escolha um dia e horário posteriores à saída anterior.`,
      );
  });
  return errors;
}

export function PackageItineraryEditor({
  value,
  onChange,
}: {
  value: PackageItinerary;
  onChange: (value: PackageItinerary) => void;
}) {
  const routes = useQuery({
    queryKey: ["routes"],
    queryFn: () => api<SavedRoute[]>("/routes"),
  });
  const issues = packageItineraryErrors(value);
  return (
    <section className="package-itinerary-editor">
      <div className="package-rules">
        <h3>Como montar o pacote</h3>
        <ol>
          <li>Cadastre os destinos na ordem em que serão visitados.</li>
          <li>
            Selecione uma Rota para cada deslocamento e indique qual destino
            será alcançado na sua finalidade.
          </li>
          <li>
            Marque a chegada a cada destino uma única vez. Passeios e
            transferências não são novos destinos comerciais.
          </li>
          <li>Inclua o retorno à origem no último deslocamento.</li>
        </ol>
        <p>
          Os dias são relativos: dia 1 é o início da viagem. Você pode visitar
          um destino no dia 1, outro no dia 4 e retornar no dia 7. As datas
          reais serão definidas ao agendar a viagem.
        </p>
      </div>
      <h3>1. Destinos comerciais</h3>
      <p className="muted">
        Cada destino consome uma viagem da franquia ao agendar o pacote. Retorno
        e paradas não acrescentam consumo. Venda somente do pacote completo.
      </p>
      {value.destinations.map((destination, index) => (
        <fieldset className="operation-card package-route-card" key={index}>
          <legend>Destino {index + 1}</legend>
          <Field label={`Nome do destino ${index + 1}`}>
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
          <CitySelect
            label={`destino comercial ${index + 1}`}
            cityId={destination.city_id}
            uf={destination.city?.uf}
            onChange={(city, uf) =>
              onChange({
                ...value,
                destinations: value.destinations.map((d, i) =>
                  i === index
                    ? {
                        ...d,
                        city_id: city?.id || null,
                        city: city || { id: 0, name: "", uf },
                        name: d.name || city?.name || "",
                      }
                    : d,
                ),
              })
            }
          />
          <button
            type="button"
            className="button secondary"
            disabled={value.destinations.length === 1}
            onClick={() =>
              onChange({
                ...value,
                destinations: value.destinations.filter((_, i) => i !== index),
                steps: value.steps.map((s) => ({
                  ...s,
                  destination_position:
                    s.destination_position === index + 1
                      ? null
                      : s.destination_position &&
                          s.destination_position > index + 1
                        ? s.destination_position - 1
                        : s.destination_position,
                })),
              })
            }
          >
            Remover destino
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        className="button secondary"
        disabled={value.destinations.length >= 20}
        onClick={() =>
          onChange({
            ...value,
            destinations: [...value.destinations, { name: "", city_id: null }],
          })
        }
      >
        Adicionar destino
      </button>
      <h3>2. Deslocamentos do roteiro</h3>
      <p className="muted">
        Selecione um sentido de Rota para cada deslocamento, em ordem. Inclua o
        retorno à origem no último deslocamento. O dia 1 corresponde à data
        inicial da viagem.
      </p>
      {routes.error && <Alert>{routes.error.message}</Alert>}
      {value.steps.map((step, index) => (
        <fieldset className="operation-card package-route-card" key={index}>
          <legend>Deslocamento {index + 1}</legend>
          <p className="muted">
            Dia {step.day} · saída às {step.departure_time} ·{" "}
            {step.destination_position
              ? `chegada ao destino ${step.destination_position}`
              : index === value.steps.length - 1
                ? "retorno à origem"
                : "passeio ou transferência"}
          </p>
          <div className="form-grid">
            <Field label={`Dia do deslocamento ${index + 1}`}>
              <input
                type="number"
                required
                min={1}
                max={60}
                step={1}
                value={step.day}
                onChange={(e) =>
                  onChange({
                    ...value,
                    steps: value.steps.map((s, i) =>
                      i === index ? { ...s, day: Number(e.target.value) } : s,
                    ),
                  })
                }
              />
            </Field>
            <Field label={`Saída do deslocamento ${index + 1}`}>
              <input
                type="time"
                required
                value={step.departure_time}
                onChange={(e) =>
                  onChange({
                    ...value,
                    steps: value.steps.map((s, i) =>
                      i === index
                        ? { ...s, departure_time: e.target.value }
                        : s,
                    ),
                  })
                }
              />
            </Field>
          </div>
          <Field label={`Rota do deslocamento ${index + 1}`}>
            <select
              required
              value={
                step.route_id
                  ? `${step.route_id}:${step.route_leg_position}`
                  : ""
              }
              onChange={(e) => {
                const [id, position] = e.target.value.split(":");
                onChange({
                  ...value,
                  steps: value.steps.map((s, i) =>
                    i === index
                      ? {
                          ...s,
                          route_id: id,
                          route_leg_position: Number(position),
                          leg: undefined,
                        }
                      : s,
                  ),
                });
              }}
            >
              <option value="">Selecione a Rota e o sentido</option>
              {step.route_id &&
                !routes.data?.some(
                  (r) => r.id === step.route_id && r.is_active,
                ) && (
                  <option value={`${step.route_id}:${step.route_leg_position}`}>
                    {step.route_name || "Rota do roteiro salvo"} · selecione uma
                    Rota ativa antes de salvar
                  </option>
                )}
              {routes.data
                ?.filter((r) => r.is_active)
                .flatMap((r) =>
                  r.legs.map((leg, i) => (
                    <option key={`${r.id}:${i}`} value={`${r.id}:${i + 1}`}>
                      {r.name} · {leg.origin} → {leg.destination}
                    </option>
                  )),
                )}
            </select>
          </Field>
          <Field label={`Finalidade do deslocamento ${index + 1}`}>
            <select
              value={step.destination_position || ""}
              onChange={(e) =>
                onChange({
                  ...value,
                  steps: value.steps.map((s, i) =>
                    i === index
                      ? {
                          ...s,
                          destination_position: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }
                      : s,
                  ),
                })
              }
            >
              <option value="">
                Passeio, transferência ou retorno (sem consumo adicional)
              </option>
              {value.destinations.map((d, i) => (
                <option key={i} value={i + 1}>
                  Chegada ao destino {i + 1}: {d.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="modal-actions">
            {[-1, 1].map((offset) => (
              <button
                type="button"
                className="button secondary"
                key={offset}
                disabled={
                  index + offset < 0 || index + offset >= value.steps.length
                }
                onClick={() => {
                  const steps = [...value.steps];
                  [steps[index], steps[index + offset]] = [
                    steps[index + offset],
                    steps[index],
                  ];
                  onChange({ ...value, steps });
                }}
              >
                {offset === -1 ? "Mover acima" : "Mover abaixo"}
              </button>
            ))}
            <button
              type="button"
              className="button secondary"
              disabled={value.steps.length <= 2}
              onClick={() =>
                onChange({
                  ...value,
                  steps: value.steps.filter((_, i) => i !== index),
                })
              }
            >
              Remover deslocamento
            </button>
          </div>
        </fieldset>
      ))}
      <button
        type="button"
        className="button secondary"
        disabled={value.steps.length >= 60}
        onClick={() =>
          onChange({
            ...value,
            steps: [
              ...value.steps,
              {
                day: value.steps.at(-1)!.day + 1,
                departure_time: "08:00",
                route_id: "",
                route_leg_position: 1,
                destination_position: null,
              },
            ],
          })
        }
      >
        Adicionar deslocamento
      </button>
      <h3>3. Atividades e dias livres (opcional)</h3>
      {value.activities.map((activity, index) => (
        <div className="operation-card" key={index}>
          <Field label={`Dia da atividade ${index + 1}`}>
            <input
              type="number"
              required
              min={1}
              max={60}
              value={activity.day}
              onChange={(e) =>
                onChange({
                  ...value,
                  activities: value.activities.map((a, i) =>
                    i === index ? { ...a, day: Number(e.target.value) } : a,
                  ),
                })
              }
            />
          </Field>
          <Field label={`Atividade ${index + 1}`}>
            <input
              required
              minLength={2}
              maxLength={150}
              value={activity.title}
              onChange={(e) =>
                onChange({
                  ...value,
                  activities: value.activities.map((a, i) =>
                    i === index ? { ...a, title: e.target.value } : a,
                  ),
                })
              }
            />
          </Field>
          <Field label={`Descrição da atividade ${index + 1}`}>
            <textarea
              maxLength={3000}
              value={activity.description}
              onChange={(e) =>
                onChange({
                  ...value,
                  activities: value.activities.map((a, i) =>
                    i === index ? { ...a, description: e.target.value } : a,
                  ),
                })
              }
            />
          </Field>
          <button
            type="button"
            className="button secondary"
            onClick={() =>
              onChange({
                ...value,
                activities: value.activities.filter((_, i) => i !== index),
              })
            }
          >
            Remover atividade
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button secondary"
        disabled={value.activities.length >= 120}
        onClick={() =>
          onChange({
            ...value,
            activities: [
              ...value.activities,
              { day: 1, title: "", description: "" },
            ],
          })
        }
      >
        Adicionar atividade
      </button>
      <p>
        <strong>
          Esta saída consumirá {value.destinations.length}{" "}
          {value.destinations.length === 1 ? "viagem" : "viagens"} da franquia,
          com retorno incluído.
        </strong>
      </p>
      {issues.length > 0 && (
        <div className="package-rules" aria-label="Pendências do roteiro">
          <h4>Antes de salvar, complete o roteiro</h4>
          <ul>
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export function PackageProgram({
  itinerary,
}: {
  itinerary: Pick<PackageItinerary, "destinations" | "activities">;
}) {
  return (
    <section className="operation-card">
      <h3>Pacote completo</h3>
      <p>
        {itinerary.destinations.map((d) => d.name).join(" → ")} · retorno
        incluído
      </p>
      {itinerary.activities.map((a, i) => (
        <p key={i}>
          <strong>
            Dia {a.day}: {a.title}
          </strong>
          {a.description && ` — ${a.description}`}
        </p>
      ))}
      <p className="muted">
        Não há venda de destinos separados. O valor por passageiro é referente
        ao pacote completo.
      </p>
    </section>
  );
}
