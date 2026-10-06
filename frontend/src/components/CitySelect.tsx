import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { Alert, Field } from "./ui";

type City = { id: number; name: string; uf: string };
export function CitySelect({
  label,
  cityId,
  uf = "",
  onChange,
}: {
  label: string;
  cityId?: number | null;
  uf?: string | null;
  onChange: (city: City | null, uf: string) => void;
}) {
  const [search, setSearch] = useState("");
  const states = useQuery({
    queryKey: ["states"],
    queryFn: () => api<{ name: string; uf: string }[]>("/locations/states"),
    staleTime: Infinity,
  });
  const cities = useQuery({
    queryKey: ["cities", uf],
    queryFn: () => api<City[]>(`/locations/cities/${uf}`),
    enabled: !!uf,
    staleTime: Infinity,
  });
  return (
    <div>
      <Field label={`UF de ${label}`}>
        <select
          aria-label={`UF de ${label}`}
          required
          value={uf || ""}
          onChange={(e) => {
            onChange(null, e.target.value);
            setSearch("");
          }}
        >
          <option value="">Selecione a UF</option>
          {states.data?.map((s) => (
            <option key={s.uf} value={s.uf}>
              {s.uf} · {s.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label={`Pesquisar cidade de ${label}`}>
        <input
          value={search}
          disabled={!uf}
          placeholder="Filtrar cidades"
          onChange={(e) => setSearch(e.target.value)}
        />
      </Field>
      <Field label={`Cidade de ${label}`}>
        <select
          aria-label={`Cidade de ${label}`}
          required
          disabled={!uf || cities.isPending}
          value={cityId || ""}
          onChange={(e) =>
            onChange(
              cities.data?.find((city) => city.id === Number(e.target.value)) ||
                null,
              uf || "",
            )
          }
        >
          <option value="">Selecione a cidade</option>
          {cities.data
            ?.filter(
              (c) =>
                c.id === cityId ||
                c.name
                  .toLocaleLowerCase("pt-BR")
                  .includes(search.toLocaleLowerCase("pt-BR")),
            )
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
        </select>
      </Field>
      {(states.error || cities.error) && (
        <Alert>Não foi possível carregar as cidades. Tente novamente.</Alert>
      )}
    </div>
  );
}
