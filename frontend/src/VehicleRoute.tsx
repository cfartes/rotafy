import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert } from "./components/ui";
type Route = {
  vehicle_name: string;
  plate: string;
  legs: {
    id: string;
    position: number;
    navigation_stages: {
      maps_url: string;
      from_position: number;
      to_position: number;
    }[];
    points: {
      position: number;
      name: string;
      address: string;
      scheduled_at: string;
      maps_url: string;
    }[];
  }[];
};
export function VehicleRoute({
  tripId,
  allocationId,
}: {
  tripId: string;
  allocationId: string;
}) {
  const route = useQuery({
    queryKey: ["vehicle-route", tripId, allocationId],
    queryFn: () =>
      api<Route>(`/trips/${tripId}/vehicles/${allocationId}/route`),
  });
  if (route.isPending) return <p>Carregando itinerário…</p>;
  if (route.error)
    return <Alert>Não foi possível carregar a rota deste veículo.</Alert>;
  return (
    <div>
      {route.data?.legs.map((leg) => (
        <section key={leg.id} className="operation-card">
          <h3>Rota · {leg.position === 1 ? "Ida" : "Volta"}</h3>
          {leg.navigation_stages.map((stage, index) => (
            <a
              className="button primary"
              key={index}
              href={stage.maps_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {leg.navigation_stages.length === 1
                ? "Abrir rota no Google Maps"
                : `Abrir etapa ${index + 1} no Google Maps`}
            </a>
          ))}
          <ol>
            {leg.points.map((point) => (
              <li key={point.position}>
                <strong>{point.name}</strong> ·{" "}
                {new Intl.DateTimeFormat("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                  timeZone: "America/Sao_Paulo",
                }).format(new Date(point.scheduled_at))}
                <p>{point.address}</p>
                <a
                  className="button secondary"
                  href={point.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {point.position === 0
                    ? "Navegar até a saída"
                    : "Navegar até este ponto"}
                </a>
              </li>
            ))}
          </ol>
          <p className="muted">
            Siga a ordem definida pela agência. A navegação abre no Google Maps
            do aparelho, a partir da sua localização.
          </p>
        </section>
      ))}
    </div>
  );
}
