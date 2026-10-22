import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert } from "./components/ui";

type Feedback = {
  id: string;
  contact_name: string;
  phone: string;
  kind: string;
  score: number;
  comment: string | null;
  trip_name: string | null;
};
function useQuality() {
  return useQuery({
    queryKey: ["nps-quality"],
    queryFn: () => api<{ rows: Feedback[]; total: number }>("/nps/quality"),
    refetchInterval: 30000,
    retry: false,
  });
}
export function NpsQualityAlert({ onOpen }: { onOpen: () => void }) {
  const { data } = useQuality();
  if (!data?.total) return null;
  return (
    <aside
      className="panel nps-quality-alert"
      aria-label="Feedbacks para a equipe de qualidade"
    >
      <p role="status">
        <strong>
          {data.total}{" "}
          {data.total === 1
            ? "avaliação com nota de 0 a 6 aguardando análise"
            : "avaliações com notas de 0 a 6 aguardando análise"}{" "}
          da equipe de qualidade.
        </strong>
      </p>
      <button className="button secondary" onClick={onOpen}>
        Ver avaliações de qualidade
      </button>
    </aside>
  );
}
export function NpsQualityInbox() {
  const query = useQuality(),
    cache = useQueryClient();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState<string | null>(null);
  async function review(row: Feedback) {
    setBusy(row.id);
    setError("");
    try {
      await post(`/nps/quality/${row.id}/review`, { comment: row.comment });
      await cache.invalidateQueries({ queryKey: ["nps-quality"] });
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Não foi possível registrar a análise.",
      );
      await cache.invalidateQueries({ queryKey: ["nps-quality"] });
    } finally {
      setBusy(null);
    }
  }
  if (query.error)
    return (
      <Alert>
        Não foi possível consultar os feedbacks da equipe de qualidade.
      </Alert>
    );
  if (!query.data?.total) return null;
  return (
    <section
      className="panel nps-quality-inbox"
      aria-label="Análise da equipe de qualidade"
    >
      <h2>Equipe de qualidade</h2>
      <p>
        {query.data.total}{" "}
        {query.data.total === 1
          ? "avaliação aguardando análise"
          : "avaliações aguardando análise"}
        . As notas e os comentários permanecem no relatório após a análise.
      </p>
      {error && <Alert>{error}</Alert>}
      {query.data.rows.map((row) => (
        <article key={row.id}>
          <strong>
            {row.contact_name || "Cliente"} · Nota {row.score}
          </strong>
          <p>
            {row.phone} · {row.trip_name || "Atendimento humano"}
          </p>
          <p>{row.comment || "O cliente não deixou um comentário."}</p>
          <button
            className="button secondary"
            disabled={!!busy}
            onClick={() => void review(row)}
          >
            Marcar avaliação de {row.contact_name || row.phone} como analisada
          </button>
        </article>
      ))}
      {query.data.total > 50 && (
        <p>
          São exibidas as cinquenta mais antigas; as próximas aparecem após a
          análise.
        </p>
      )}
    </section>
  );
}
