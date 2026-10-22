import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Alert, Field } from "./components/ui";
import "./business-hours.css";

type Interval = { day: number; start: string; end: string };
type Settings = { enabled: boolean; timezone: string; intervals: Interval[] };
const days = [
  "Segunda-feira",
  "Terça-feira",
  "Quarta-feira",
  "Quinta-feira",
  "Sexta-feira",
  "Sábado",
  "Domingo",
];

function Editor({ value }: { value: Settings }) {
  const [enabled, setEnabled] = useState(value.enabled),
    [timezone, setTimezone] = useState(value.timezone);
  const [intervals, setIntervals] = useState(value.intervals);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  const change = (index: number, changes: Partial<Interval>) => {
    setIntervals((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...changes } : row)),
    );
    setSaved(false);
  };
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/company/whatsapp/hours", {
        method: "PUT",
        body: JSON.stringify({ enabled, timezone, intervals }),
      });
      setSaved(true);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível salvar os horários.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel business-hours" onSubmit={save}>
      <h2>Horários de atendimento humano</h2>
      <p>
        O WhatsApp informa os horários e a próxima abertura quando alguém
        solicita atendimento fora do expediente. A solicitação continua
        registrada para a equipe.
      </p>
      <label className="business-hours-toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => {
            setEnabled(e.target.checked);
            setSaved(false);
            if (e.target.checked && !intervals.length)
              setIntervals(
                [0, 1, 2, 3, 4].map((day) => ({
                  day,
                  start: "09:00",
                  end: "18:00",
                })),
              );
          }}
        />{" "}
        Informar quando estivermos fora do horário de atendimento
      </label>
      <Field label="Fuso horário do atendimento">
        <select
          value={timezone}
          onChange={(e) => {
            setTimezone(e.target.value);
            setSaved(false);
          }}
        >
          <option value="America/Sao_Paulo">Brasília</option>
          <option value="America/Manaus">Manaus</option>
          <option value="America/Rio_Branco">Rio Branco</option>
          <option value="America/Noronha">Fernando de Noronha</option>
        </select>
      </Field>
      {intervals.map((row, index) => (
        <div className="business-hours-row" key={index}>
          <Field label={`Dia da semana ${index + 1}`}>
            <select
              value={row.day}
              onChange={(e) => change(index, { day: Number(e.target.value) })}
            >
              {days.map((day, i) => (
                <option value={i} key={day}>
                  {day}
                </option>
              ))}
            </select>
          </Field>
          <Field label={`Início ${index + 1}`}>
            <input
              type="time"
              value={row.start}
              required
              onChange={(e) => change(index, { start: e.target.value })}
            />
          </Field>
          <Field label={`Término ${index + 1}`}>
            <input
              type="time"
              value={row.end}
              required
              onChange={(e) => change(index, { end: e.target.value })}
            />
          </Field>
          <button
            type="button"
            className="button secondary"
            aria-label={`Remover horário ${index + 1}`}
            onClick={() => {
              setIntervals((rows) => rows.filter((_, i) => i !== index));
              setSaved(false);
            }}
          >
            Remover
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button secondary"
        disabled={intervals.length >= 42}
        onClick={() => {
          setIntervals((rows) => [
            ...rows,
            { day: 0, start: "09:00", end: "18:00" },
          ]);
          setSaved(false);
        }}
      >
        Adicionar horário
      </button>
      <p>
        Adicione mais de um turno para o mesmo dia, por exemplo, antes e depois
        do almoço. Dias sem horários são considerados fechados. Um término
        anterior ao início indica um turno que termina no dia seguinte. Esses
        horários não impedem respostas manuais da equipe nem mensagens
        automáticas.
      </p>
      {error && <Alert>{error}</Alert>}
      {saved && <p role="status">Horários de atendimento salvos.</p>}
      <button className="button primary" disabled={busy}>
        {busy ? "Salvando…" : "Salvar horários de atendimento"}
      </button>
    </form>
  );
}

export function BusinessHours() {
  const settings = useQuery({
    queryKey: ["service-hours"],
    queryFn: () => api<Settings>("/company/whatsapp/hours"),
  });
  if (settings.error)
    return (
      <Alert>Não foi possível consultar os horários de atendimento.</Alert>
    );
  if (!settings.data || !Array.isArray(settings.data.intervals)) return null;
  return <Editor value={settings.data} />;
}
