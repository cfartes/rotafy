import { useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { money, moneyInput, parseMoney } from "./billing/types";
import {
  ReservationJourneyEditor,
  type Journey,
  type JourneyLeg,
} from "./JourneyLocation";
import { TicketManager } from "./Tickets";
import { DataUseNotice } from "./components/DataUseNotice";

type Case = {
  id: string;
  trip_name: string;
  original_starts_at: string;
  contact_name: string;
  phone: string;
  passenger_count: number;
  passenger_names: string[];
  total_cents: number;
  paid_cents: number;
  credit_cents: number;
  source_version: number;
  original_status: string;
  status: string;
  manual_review: boolean;
  target_reservation_id: string | null;
  target_trip_name: string | null;
  remaining_credit_cents: number;
  financial_note: string;
  note: string;
};
type Offer = {
  trip: {
    id: string;
    name: string;
    starts_at: string;
    price_cents: number;
    edit_version: number;
    mode: string;
    legs: (JourneyLeg & { starts_at?: string; ends_at?: string })[];
  };
  journeys: Journey[];
  vehicles: { allocation_id: string; name: string; available: number }[];
  suggested_allocation_id: string;
  total_cents: number;
  difference_seconds: number;
};
type Issued = { id: string; full_name: string; leg_id: string; token: string };
type Result = {
  id: string;
  status: string;
  credit_cents: number;
  total_cents: number;
  issued_tickets?: Issued[];
};
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));

export function Reaccommodations({
  allowHistory = false,
}: {
  allowHistory?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState(false);
  const [selected, setSelected] = useState<Case | null>(null);
  const cache = useQueryClient();
  const [listOffset, setListOffset] = useState(0);
  const query = useQuery({
    queryKey: ["reaccommodations", history, listOffset],
    queryFn: () =>
      api<{
        items: Case[];
        pending_families: number;
        pending_passengers: number;
        financial_pending: number;
        has_more: boolean;
      }>(`/reaccommodations?history=${history}&offset=${listOffset}`),
    refetchInterval: 15000,
    retry: false,
  });
  const items = Array.isArray(query.data?.items) ? query.data.items : [];
  const pending = query.data?.pending_families || 0;
  const financial = query.data?.financial_pending || 0;
  if (!pending && !financial && !allowHistory && !open && !query.error)
    return null;
  async function refresh() {
    await cache.invalidateQueries({ queryKey: ["reaccommodations"] });
  }
  return (
    <>
      {(pending > 0 || financial > 0) && (
        <aside
          className="billing-upcoming billing-due-notice"
          aria-label="Reservas afetadas por cancelamentos"
        >
          <p role="status">
            <strong>
              {pending > 0
                ? `${pending} família(s) / ${query.data?.pending_passengers || 0} passageiro(s) aguardam atendimento após cancelamento.`
                : "Saldos de reservas canceladas aguardam revisão."}
            </strong>
          </p>
          {financial > 0 && (
            <p>
              {financial} saldo(s) a favor do cliente aguardam revisão
              financeira.
            </p>
          )}
          <button
            className="button primary"
            onClick={() => {
              setHistory(false);
              setListOffset(0);
              setOpen(true);
            }}
          >
            Revisar passageiros e alternativas
          </button>
        </aside>
      )}
      {query.error && (
        <Alert>Não foi possível consultar as pendências de realocação.</Alert>
      )}
      {allowHistory && (
        <button
          className="button secondary"
          onClick={() => {
            setHistory(true);
            setListOffset(0);
            setOpen(true);
          }}
        >
          Consultar realocações e histórico
        </button>
      )}
      {open && (
        <Modal
          title="Atendimento após cancelamento"
          wide
          onClose={() => {
            setOpen(false);
            setSelected(null);
          }}
        >
          {selected ? (
            <ReaccommodationCase
              key={selected.id}
              item={selected}
              onBack={() => {
                setSelected(null);
                void refresh();
              }}
              onRefresh={refresh}
            />
          ) : (
            <div className="modal-form">
              <p>
                Escolha a família para revisar as alternativas. A transferência
                só ocorre após sua confirmação e concordância do cliente.
              </p>
              {query.isPending && <p role="status">Consultando pendências…</p>}
              {!query.isPending && !items.length && (
                <p>Nenhuma pendência encontrada.</p>
              )}
              {items.map((item) => (
                <article className="operation-card modal-form" key={item.id}>
                  <h3>
                    {item.trip_name} · {date(item.original_starts_at)}
                  </h3>
                  <p>
                    <strong>{item.contact_name}</strong> · {item.phone} ·{" "}
                    {item.passenger_count} passageiro(s)
                  </p>
                  <p>{item.passenger_names.join(", ")}</p>
                  <p>
                    {item.status === "pending"
                      ? "Aguardando atendimento"
                      : item.status === "transferred"
                        ? `Realocado para ${item.target_trip_name}`
                        : "Encerrado sem realocar"}
                    {item.manual_review
                      ? " · Viagem parcialmente realizada: revisão manual"
                      : ""}
                  </p>
                  {item.remaining_credit_cents > 0 && (
                    <p>
                      Saldo a favor do cliente:{" "}
                      {money(item.remaining_credit_cents)} ·{" "}
                      {item.financial_note || "Ajuste pendente"}
                    </p>
                  )}
                  <button
                    className="button secondary"
                    onClick={() => setSelected(item)}
                  >
                    Revisar {item.contact_name}
                  </button>
                </article>
              ))}
              <div className="modal-actions">
                {listOffset > 0 && (
                  <button
                    className="button secondary"
                    onClick={() => setListOffset(listOffset - 50)}
                  >
                    Famílias anteriores
                  </button>
                )}
                {query.data?.has_more && (
                  <button
                    className="button secondary"
                    onClick={() => setListOffset(listOffset + 50)}
                  >
                    Mais famílias
                  </button>
                )}
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

function ReaccommodationCase({
  item,
  onBack,
  onRefresh,
}: {
  item: Case;
  onBack: () => void;
  onRefresh: () => Promise<void>;
}) {
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [offer, setOffer] = useState<Offer | null>(null);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [allocation, setAllocation] = useState("");
  const [cash, setCash] = useState(moneyInput(item.paid_cents));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [finished, setFinished] = useState(false);
  const operationKey = useRef(crypto.randomUUID());
  const suggestions = useQuery({
    queryKey: ["reaccommodation-suggestions", item.id, offset],
    queryFn: () =>
      api<{ items: Offer[]; has_more: boolean }>(
        `/reaccommodations/${item.id}/suggestions?offset=${offset}`,
      ),
    enabled:
      item.status === "pending" && !item.manual_review && !result && !finished,
    retry: false,
  });
  let recognized: number | null = null;
  try {
    recognized = parseMoney(cash, item.total_cents);
  } catch {
    /* The form reports an invalid amount on submit. */
  }
  const credit = item.credit_cents + (recognized ?? 0);
  function choose(value: Offer) {
    setOffer(value);
    setJourneys(value.journeys);
    setAllocation(value.suggested_allocation_id);
    operationKey.current = crypto.randomUUID();
    setError("");
  }
  async function transfer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!offer || busy) return;
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const response = await post<Result>(
        `/reaccommodations/${item.id}/transfer`,
        {
          operation_key: operationKey.current,
          trip_id: offer.trip.id,
          allocation_id: allocation,
          expected_trip_version: offer.trip.edit_version,
          expected_price_cents: offer.trip.price_cents,
          expected_source_version: item.source_version,
          expected_source_paid_cents: item.paid_cents,
          recognized_cash_cents: parseMoney(cash, item.total_cents),
          review_note: String(form.get("review_note") || ""),
          consent: form.get("consent") === "on",
          logistics_reviewed: form.get("logistics") === "on",
          journeys,
        },
      );
      setResult(response);
      await cache.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível transferir.");
      await suggestions.refetch();
    } finally {
      setBusy(false);
    }
  }
  async function resolve(e: FormEvent<HTMLFormElement>, financial: boolean) {
    e.preventDefault();
    if (busy) return;
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await post(
        `/reaccommodations/${item.id}/${financial ? "financial-resolution" : "close"}`,
        {
          note: String(form.get("note") || ""),
          ...(!financial
            ? {
                reviewed_credit_cents: parseMoney(
                  form.get("credit"),
                  item.paid_cents + item.credit_cents,
                ),
              }
            : {}),
        },
      );
      setFinished(true);
      await onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível registrar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-form">
      <button
        type="button"
        className="button secondary"
        disabled={busy}
        onClick={onBack}
      >
        Voltar às famílias
      </button>
      <h3>
        {item.contact_name} · {item.passenger_count} passageiro(s)
      </h3>
      <p>
        {item.trip_name} · saída original {date(item.original_starts_at)} ·
        horário de Brasília
      </p>
      <p>{item.passenger_names.join(", ")}</p>
      <p>
        Valor original: {money(item.total_cents)} · Dinheiro recebido:{" "}
        {money(item.paid_cents)} · Crédito anterior: {money(item.credit_cents)}
      </p>
      {item.original_status === "pending" && (
        <p>
          Reserva provisória: a transferência não confirma a venda
          automaticamente.
        </p>
      )}
      {error && <Alert>{error}</Alert>}
      {finished && (
        <p role="status">
          Atendimento registrado. Consulte o histórico para acompanhar os
          valores e a justificativa.
        </p>
      )}
      {result && offer && (
        <section className="operation-card modal-form">
          <h3>Realocação concluída</h3>
          <p role="status">
            Nova reserva em {offer.trip.name} · {date(offer.trip.starts_at)}.
          </p>
          <p>
            Crédito aplicado: {money(result.credit_cents)} · Diferença a pagar:{" "}
            {money(result.total_cents - result.credit_cents)}.
          </p>
          <p>
            A reserva anterior continua cancelada. Oriente motorista/guia a
            sincronizar e preparar o novo manifesto.
          </p>
          <TicketManager
            reservationId={result.id}
            confirmed={result.status === "confirmed"}
            legs={offer.trip.legs}
            initialIssued={result.issued_tickets}
          />
        </section>
      )}
      {!result && !finished && item.status === "pending" && (
        <>
          {item.manual_review ? (
            <Alert>
              Há etapas já realizadas. Revise o atendimento e os valores
              manualmente; a viagem inteira não será transferida
              automaticamente.
            </Alert>
          ) : (
            <>
              <h3>Viagens compatíveis mais próximas</h3>
              {suggestions.isPending && (
                <p role="status">Consultando vagas e itinerários…</p>
              )}
              {suggestions.error && (
                <Alert>
                  Não foi possível consultar alternativas.{" "}
                  <button
                    type="button"
                    onClick={() => void suggestions.refetch()}
                  >
                    Tentar novamente
                  </button>
                </Alert>
              )}
              {suggestions.data?.items?.length === 0 && (
                <p>
                  Nenhuma alternativa compatível com vagas nesta consulta.
                  Contate o cliente para decidir outra solução.
                </p>
              )}
              {suggestions.data?.items?.map((choice) => (
                <article
                  className="operation-card modal-form"
                  key={choice.trip.id}
                >
                  <h4>
                    {choice.trip.name} · {date(choice.trip.starts_at)}
                  </h4>
                  <p>
                    {Math.round(Math.abs(choice.difference_seconds) / 360) / 10}{" "}
                    hora(s) {choice.difference_seconds < 0 ? "antes" : "depois"}{" "}
                    da saída original · Valor da família:{" "}
                    {money(choice.total_cents)}
                  </p>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => choose(choice)}
                  >
                    Escolher {choice.trip.name}
                  </button>
                </article>
              ))}
              <div className="modal-actions">
                {offset > 0 && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setOffset(offset - 5)}
                  >
                    Alternativas anteriores
                  </button>
                )}
                {suggestions.data?.has_more && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setOffset(offset + 5)}
                  >
                    Ver mais alternativas
                  </button>
                )}
              </div>
              {offer && (
                <form
                  key={operationKey.current}
                  className="operation-card modal-form"
                  onSubmit={transfer}
                >
                  <h3>Revisar transferência para {offer.trip.name}</h3>
                  <DataUseNotice purpose="registrar a realocação, a concordância do cliente e a conferência dos valores" />
                  {offer.trip.legs.map((leg, i) => (
                    <p key={leg.id}>
                      <strong>
                        Trecho {i + 1}: {leg.origin} → {leg.destination}
                      </strong>
                      {leg.starts_at && (
                        <>
                          {" "}
                          · {date(leg.starts_at)}
                          {leg.ends_at && <> até {date(leg.ends_at)}</>}
                        </>
                      )}
                    </p>
                  ))}
                  <Field label="Veículo da família">
                    <select
                      value={allocation}
                      onChange={(e) => setAllocation(e.target.value)}
                      disabled={busy}
                    >
                      {offer.vehicles.map((v) => (
                        <option key={v.allocation_id} value={v.allocation_id}>
                          {v.name} · {v.available} lugares disponíveis
                        </option>
                      ))}
                    </select>
                  </Field>
                  <ReservationJourneyEditor
                    key={offer.trip.id}
                    trip={offer.trip}
                    journeys={journeys}
                    onChange={setJourneys}
                  />
                  <Field label="Dinheiro já recebido na reserva original (R$)">
                    <input
                      value={cash}
                      onChange={(e) => setCash(e.target.value)}
                      required
                      inputMode="decimal"
                      disabled={busy}
                    />
                  </Field>
                  <p>
                    Crédito disponível: {money(credit)} · Aplicar:{" "}
                    {money(Math.min(credit, offer.total_cents))} · Diferença a
                    pagar: {money(Math.max(0, offer.total_cents - credit))} ·
                    Saldo a favor:{" "}
                    {money(Math.max(0, credit - offer.total_cents))}.
                  </p>
                  <Field label="Conferência do pagamento / observações">
                    <textarea
                      name="review_note"
                      maxLength={2000}
                      minLength={
                        recognized !== item.paid_cents ? 10 : undefined
                      }
                      required={recognized !== item.paid_cents}
                      disabled={busy}
                    />
                  </Field>
                  <label className="operation-checkbox">
                    <input
                      type="checkbox"
                      name="logistics"
                      required
                      disabled={busy}
                    />
                    Conferi os pontos e horários de embarque da ida e do
                    retorno.
                  </label>
                  <label className="operation-checkbox">
                    <input
                      type="checkbox"
                      name="consent"
                      required
                      disabled={busy}
                    />
                    O cliente concordou com a nova viagem e os valores.
                  </label>
                  <button
                    className="button primary"
                    disabled={busy || recognized === null}
                  >
                    {busy ? "Registrando…" : "Confirmar realocação da família"}
                  </button>
                </form>
              )}
            </>
          )}
          <details>
            <summary>Encerrar sem realocar</summary>
            <form
              className="modal-form"
              onSubmit={(e) => void resolve(e, false)}
            >
              <DataUseNotice purpose="registrar o atendimento da reserva cancelada" />
              <Field label="Motivo do encerramento">
                <textarea
                  name="note"
                  required
                  minLength={5}
                  maxLength={2000}
                  disabled={busy}
                />
              </Field>
              <Field label="Saldo a favor do cliente para revisão (R$)">
                <input
                  name="credit"
                  required
                  inputMode="decimal"
                  defaultValue={
                    item.manual_review
                      ? ""
                      : moneyInput(item.paid_cents + item.credit_cents)
                  }
                  disabled={busy}
                />
              </Field>
              <p>
                Este registro não realiza reembolso. Saldos positivos
                continuarão pendentes de revisão financeira.
              </p>
              <button className="button secondary" disabled={busy}>
                Registrar encerramento sem realocar
              </button>
            </form>
          </details>
        </>
      )}
      {!result && !finished && item.status !== "pending" && (
        <>
          <p>
            {item.target_trip_name
              ? `Realocado para ${item.target_trip_name}.`
              : "Encerrado sem realocação."}{" "}
            {item.note}
          </p>
          {item.remaining_credit_cents > 0 && (
            <p>
              Saldo a favor do cliente: {money(item.remaining_credit_cents)}
            </p>
          )}
          {item.financial_note ? (
            <p>Ajuste registrado: {item.financial_note}</p>
          ) : (
            item.remaining_credit_cents > 0 && (
              <form
                className="modal-form"
                onSubmit={(e) => void resolve(e, true)}
              >
                <DataUseNotice purpose="registrar a revisão financeira da reserva cancelada" />
                <Field label="Como o saldo foi tratado">
                  <textarea
                    name="note"
                    required
                    minLength={10}
                    maxLength={2000}
                    disabled={busy}
                  />
                </Field>
                <p>
                  Informe o tratamento realizado fora do sistema. Nenhum estorno
                  será executado.
                </p>
                <button className="button primary" disabled={busy}>
                  Registrar revisão financeira
                </button>
              </form>
            )
          )}
        </>
      )}
    </div>
  );
}
