import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import QRCode from "qrcode";
import { api, post } from "./api";
import { Alert, Field } from "./components/ui";
import "./boarding.css";

type Ticket = {
  id: string;
  full_name: string;
  leg_id: string;
  revoked_at: string | null;
};
type Issued = { id: string; full_name: string; leg_id: string; token: string };
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Não foi possível concluir.";
export function TicketManager({
  reservationId,
  confirmed,
  legs,
}: {
  reservationId: string;
  confirmed: boolean;
  legs: { id: string; origin: string; destination: string }[];
}) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [issued, setIssued] = useState<Issued[]>([]);
  const tickets = useQuery({
    queryKey: ["tickets", reservationId],
    queryFn: () => api<Ticket[]>(`/reservations/${reservationId}/tickets`),
  });
  async function issue() {
    setPending(true);
    setError("");
    try {
      const result = await post<{ issued: Issued[] }>(
        `/reservations/${reservationId}/tickets`,
        {},
      );
      setIssued(result.issued);
      if (!result.issued.length)
        setError(
          "Os bilhetes já foram emitidos. Reemita o bilhete desejado para obter um novo link.",
        );
      await tickets.refetch();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  async function change(ticket: Ticket, revoke: boolean) {
    if (
      !window.confirm(
        revoke
          ? "Revogar este bilhete? O QR atual deixará de funcionar."
          : "Reemitir este bilhete? O link e QR anteriores serão invalidados.",
      )
    )
      return;
    setPending(true);
    setError("");
    try {
      const result = await post<{ token: string }>(
        `/tickets/${ticket.id}/${revoke ? "revoke" : "reissue"}`,
        {},
      );
      setIssued((previous) => [
        ...previous.filter((t) => t.id !== ticket.id),
        ...(!revoke ? [{ ...ticket, token: result.token }] : []),
      ]);
      await tickets.refetch();
    } catch (e) {
      setError(message(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="operation-card ticket-manager">
      <h3>Bilhetes individuais por trecho</h3>
      <p>
        Emita após confirmar a reserva. Copie os links agora; reemitir invalida
        o QR anterior.
      </p>
      {(error || tickets.error) && (
        <Alert>{error || message(tickets.error)}</Alert>
      )}
      <button
        className="button secondary"
        disabled={pending || !confirmed}
        onClick={issue}
      >
        Emitir bilhetes
      </button>
      {tickets.data?.map((t) => {
        const leg = legs.find((l) => l.id === t.leg_id);
        const credential = issued.find((i) => i.id === t.id);
        return (
          <article key={t.id} className="ticket-entry">
            <strong>{t.full_name}</strong>
            <p>
              {leg?.origin} → {leg?.destination} ·{" "}
              {t.revoked_at ? "Revogado" : "Emitido"}
            </p>
            {credential && (
              <>
                <Field
                  label={`Link do bilhete de ${t.full_name} (${leg?.origin})`}
                >
                  <input
                    readOnly
                    value={`${window.location.origin}/bilhete#token=${encodeURIComponent(credential.token)}`}
                  />
                </Field>
                <a
                  className="button secondary"
                  href={`/bilhete#token=${encodeURIComponent(credential.token)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Abrir bilhete
                </a>
              </>
            )}
            <button
              className="button secondary"
              disabled={pending || !confirmed}
              onClick={() => change(t, false)}
            >
              Reemitir bilhete
            </button>
            {!t.revoked_at && (
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => change(t, true)}
              >
                Revogar bilhete
              </button>
            )}
          </article>
        );
      })}
    </section>
  );
}

type PublicTicket = {
  company: { slug: string; trade_name: string; has_logo: boolean };
  is_valid: boolean;
  ticket: {
    full_name: string;
    trip_name: string;
    vehicle_name: string;
    boarding: string;
    dropoff: string;
    boarding_at: string | null;
    dropoff_at: string | null;
    boarding_status: string;
    reservation_status: string;
    trip_status: string;
  };
};
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const labels: Record<string, string> = {
  waiting: "Aguardando embarque",
  onboard: "A bordo",
  alighted: "Desembarcado",
};
export function TicketPage() {
  const token =
    new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
  const ticket = useQuery({
    queryKey: ["public-ticket", token],
    queryFn: () => post<PublicTicket>("/public/ticket", { token }),
    enabled: !!token,
    refetchInterval: 15000,
  });
  const [qr, setQr] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setQr("");
    if (ticket.data?.is_valid && !ticket.error)
      void QRCode.toDataURL(token, {
        width: 360,
        margin: 4,
        errorCorrectionLevel: "M",
        color: { dark: "#000000", light: "#ffffff" },
      })
        .then((url) => {
          if (active) setQr(url);
        })
        .catch((e) => {
          if (active) setError(message(e));
        });
    return () => {
      active = false;
    };
  }, [token, ticket.data?.is_valid, ticket.error]);
  async function share() {
    try {
      if (navigator.share)
        await navigator.share({
          title: "Bilhete Nexus Rotafy",
          url: window.location.href,
        });
      else {
        await navigator.clipboard.writeText(window.location.href);
        setError("Link copiado para compartilhar.");
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError"))
        setError("Copie o link abaixo para compartilhar.");
    }
  }
  return (
    <main className="public-site ticket-page">
      <div className="public-container tracking-container">
        <p className="eyebrow">BILHETE INDIVIDUAL</p>
        <h1>Seu bilhete</h1>
        {!token ? (
          <Alert>Abra o link privado recebido da agência.</Alert>
        ) : ticket.error ? (
          <Alert>{message(ticket.error)}</Alert>
        ) : ticket.data ? (
          <article className="public-trip-card printable-ticket">
            {ticket.data.company.has_logo && (
              <img
                className="ticket-brand-logo"
                src={`/api/v1/public/${ticket.data.company.slug}/logo`}
                alt={ticket.data.company.trade_name}
              />
            )}
            <p>{ticket.data.company.trade_name}</p>
            <h2>{ticket.data.ticket.full_name}</h2>
            <h3>{ticket.data.ticket.trip_name}</h3>
            <p>{ticket.data.ticket.vehicle_name}</p>
            <p>
              Embarque: {ticket.data.ticket.boarding} ·{" "}
              {ticket.data.ticket.boarding_at
                ? date(ticket.data.ticket.boarding_at)
                : "Conforme orienta??o da ag?ncia"}
            </p>
            <p>
              Desembarque: {ticket.data.ticket.dropoff} ·{" "}
              {ticket.data.ticket.dropoff_at
                ? date(ticket.data.ticket.dropoff_at)
                : "Sem hor?rio individual"}
            </p>
            <p className="tracking-status">
              {labels[ticket.data.ticket.boarding_status]}
            </p>
            {ticket.data.is_valid ? (
              <>
                {qr && (
                  <img
                    className="ticket-qr"
                    src={qr}
                    alt="QR do bilhete individual"
                  />
                )}
                <p>
                  Apresente este QR ao guia no trecho indicado. A situação é
                  conferida no sistema durante a leitura.
                </p>
              </>
            ) : (
              <Alert>
                Bilhete indisponível para embarque: reserva cancelada ou viagem
                encerrada.
              </Alert>
            )}
            <div className="ticket-tools">
              <button
                className="button secondary"
                disabled={!qr || !ticket.data.is_valid}
                onClick={() => window.print()}
              >
                Imprimir ou salvar PDF
              </button>
              {qr && ticket.data.is_valid && (
                <a
                  className="button secondary"
                  href={qr}
                  download="bilhete-qr.png"
                >
                  Baixar QR
                </a>
              )}
              <button className="button secondary" onClick={share}>
                Compartilhar link
              </button>
              <Field label="Link privado do bilhete">
                <textarea readOnly value={window.location.href} />
              </Field>
              <p className="muted">
                Este link identifica somente o passageiro e o trecho acima.
                Guarde com segurança.
              </p>
              <button
                className="button secondary"
                onClick={() => ticket.refetch()}
              >
                Atualizar bilhete
              </button>
            </div>
          </article>
        ) : (
          <p>Consultando bilhete…</p>
        )}
        {error && <Alert>{error}</Alert>}
      </div>
    </main>
  );
}
