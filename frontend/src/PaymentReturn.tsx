import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import { Alert } from "./components/ui";

export function PaymentReturn() {
  const params = new URLSearchParams(window.location.search);
  const reference = params.get("order_nsu") || params.get("checkout") || "";
  const valid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      reference,
    ) &&
    !(
      params.get("checkout") &&
      params.get("order_nsu") &&
      params.get("checkout") !== params.get("order_nsu")
    );
  const [error, setError] = useState("");
  const status = useQuery({
    queryKey: ["payment-return", reference],
    queryFn: () =>
      api<{ status: string }>(`/public/payments/infinitepay/${reference}`),
    enabled: valid,
    retry: false,
    refetchInterval: (q) =>
      ["paid", "review", "cancelled"].includes(q.state.data?.status ?? "")
        ? false
        : 5000,
  });
  useEffect(() => {
    const transaction = params.get("transaction_nsu");
    const slug = params.get("slug");
    if (valid && transaction && slug) {
      void post("/public/payments/infinitepay/return", {
        order_nsu: reference,
        transaction_nsu: transaction,
        invoice_slug: slug,
        receipt_url: params.get("receipt_url") || "",
      })
        .then(() => status.refetch())
        .catch(() =>
          setError(
            "A confirmação está pendente. Aguarde a atualização ou consulte Financeiro no painel.",
          ),
        );
    }
  }, []);
  const paid = status.data?.status === "paid";
  const review = ["review", "cancelled"].includes(status.data?.status ?? "");
  return (
    <main className="reset-layout">
      <section className="panel modal-form">
        <p className="eyebrow">NEXUS ROTAFY</p>
        <h1>
          {paid
            ? "Pagamento confirmado"
            : review
              ? "Pagamento em conferência"
              : "Conferindo seu pagamento"}
        </h1>
        <p>
          {paid
            ? "O pagamento foi registrado. A restrição financeira desta cobrança foi removida."
            : review
              ? "A Nexus verificará a situação desta cobrança. O histórico do pagamento está preservado."
              : "A confirmação é automática após aprovação do pagamento. Você pode voltar ao painel enquanto ela é processada."}
        </p>
        {(!valid || status.error || error) && (
          <Alert>
            {error ||
              "Não foi possível consultar esta referência. Consulte Financeiro no painel ou entre em contato com a Nexus."}
          </Alert>
        )}
        <div className="modal-actions">
          <a className="button primary" href="/">
            Voltar ao painel
          </a>
          {valid && !paid && (
            <button
              className="button secondary"
              disabled={status.isFetching}
              onClick={() => void status.refetch()}
            >
              Atualizar situação
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
