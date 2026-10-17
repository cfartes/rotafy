import { useState } from "react";
import { CircleAlert } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

type Upcoming = {
  upcoming: null | {
    invoice_kind: "setup" | "subscription";
    due_on: string;
    total_cents: number;
    price_cents: number;
    setup_cents: number;
    extra_trips: number;
    extra_trip_cents: number;
    is_estimate: boolean;
    installment: number | null;
  };
  reminder_enabled: boolean;
  days_until_due: number | null;
  show_reminder: boolean;
  plan_price_cents: number | null;
  subscription_status: string;
};

const currency = (cents: number) => (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const displayDate = (value: string) => value.split("-").reverse().join("/");

export function BillingUpcoming({ notice = false }: { notice?: boolean }) {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["billing-upcoming"],
    queryFn: () => api<Upcoming>("/company/billing/upcoming"),
    refetchInterval: 60000,
  });
  async function toggle(enabled: boolean) {
    setBusy(true);
    setError("");
    try {
      await api("/company/billing/reminder", { method: "PUT", body: JSON.stringify({ enabled }) });
      cache.setQueryData<Upcoming>(["billing-upcoming"], (old) => old ? {
        ...old, reminder_enabled: enabled,
        show_reminder: enabled && old.days_until_due !== null && old.days_until_due >= 0 && old.days_until_due <= 5,
      } : old);
      await cache.invalidateQueries({ queryKey: ["billing-upcoming"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar sua preferência.");
    } finally { setBusy(false); }
  }
  if (notice && !query.data?.show_reminder) return null;
  const invoice = query.data?.upcoming;
  return (
    <section className={`billing-upcoming ${notice ? "billing-due-notice" : "operation-card"}`} aria-label={notice ? "Aviso de próximo vencimento" : "A vencer"}>
      <div className="billing-upcoming-title">
        <CircleAlert size={22} aria-hidden="true" />
        <h2>{notice ? "Próximo vencimento" : "A vencer"}</h2>
      </div>
      {!notice && query.data && <div className="billing-summary-grid">
        <div className="billing-summary-card"><span>Valor a vencer</span><strong>{invoice ? currency(invoice.total_cents) : "—"}</strong><small>{invoice?.is_estimate ? "Valor previsto" : "Próxima fatura"}</small></div>
        <div className="billing-summary-card"><span>Parcela</span><strong>{invoice?.installment ? `${invoice.installment}/12` : "—"}</strong><small>Contador dos ciclos da assinatura. Setup não conta.</small></div>
        <div className="billing-summary-card"><span>Valor do plano</span><strong>{query.data.plan_price_cents != null ? currency(query.data.plan_price_cents) : "—"}</strong><small>Mensalidade sem excedentes</small></div>
        <div className="billing-summary-card"><span>Próximo vencimento</span><strong>{invoice ? displayDate(invoice.due_on) : "—"}</strong><small>Prazo para pagamento</small></div>
        <div className="billing-summary-card"><span>Situação da assinatura</span><strong>{({ active: "Ativa", trial: "Em teste", cancelled: "Cancelada", blocked: "Bloqueada por pendência", none: "Sem assinatura" } as Record<string, string>)[query.data.subscription_status] || "Em consulta"}</strong></div>
      </div>}
      {query.isPending && !notice && <p>Consultando próxima fatura…</p>}
      {query.error && !notice && <p role="alert">Não foi possível consultar a próxima fatura.</p>}
      {invoice ? (
        <>
          <p>{invoice.invoice_kind === "setup" ? "Setup" : "Mensalidade e excedentes"} · Vencimento: <strong>{displayDate(invoice.due_on)}</strong> · {invoice.is_estimate ? "Valor previsto" : "Valor da fatura"}: <strong>{currency(invoice.total_cents)}</strong></p>
          {invoice.is_estimate && <p className="muted">Previsão com os excedentes apurados até agora. O valor pode mudar até o fechamento.</p>}
          {!notice && invoice.invoice_kind !== "setup" && <p className="muted">Mensalidade: {currency(invoice.price_cents)} · Excedentes: {invoice.extra_trips} × {currency(invoice.extra_trip_cents)}{invoice.setup_cents > 0 ? ` · Setup: ${currency(invoice.setup_cents)}` : ""}</p>}
        </>
      ) : query.data && !notice && <p>Nenhuma próxima fatura prevista ou a vencer.</p>}
      {error && <p role="alert">{error}</p>}
      {query.data && <button type="button" className="text-button" disabled={busy} onClick={() => void toggle(!query.data!.reminder_enabled)}>
        {busy ? "Salvando…" : query.data.reminder_enabled ? "Desativar avisos de vencimento para mim" : "Reativar avisos de vencimento para mim"}
      </button>}
      {!notice && query.data && <p className="muted">Esta preferência controla somente o aviso na abertura do app, para seu usuário. Não altera os envios de cobrança por e-mail ou WhatsApp. O aviso aparece nos cinco dias anteriores ao vencimento e no próprio dia.</p>}
    </section>
  );
}
