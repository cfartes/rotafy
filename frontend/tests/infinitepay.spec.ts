import { test, expect } from "@playwright/test";

test("Nexus configures InfiniteTag, setup and trial days without requiring a manual Pix key", async ({
  page,
}) => {
  let settings: any = {
    version: 1,
    enabled: false,
    pix_key: "",
    receiver_name: "",
    nexus_session_id: "11111111-1111-4111-8111-111111111111",
    infinitepay_enabled: false,
    infinitepay_handle: "",
    setup_cents: 0,
    trial_days: 7,
  };
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        company_id: null,
        full_name: "Nexus",
        is_active: true,
      };
    if (path === "/nexus/integrations")
      body = {
        version: 1,
        openwa_key_configured: true,
        resend_key_configured: true,
        email_from: "nexus@example.com",
      };
    if (path === "/nexus/billing/settings") {
      if (route.request().method() === "PUT") {
        saved = route.request().postDataJSON();
        settings = { ...settings, ...saved, version: 2 };
      }
      body = settings;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await page.getByLabel("Usar InfinitePay nas novas cobranças").check();
  await page
    .getByLabel("Identificador InfinitePay (InfiniteTag)")
    .fill("nexus-conta");
  await page.getByLabel("Taxa de setup (R$)").fill("500,00");
  await page.getByLabel("Prazo de teste (dias)").fill("7");
  await page
    .getByLabel("Ativar avisos e cobranças mensais automáticas")
    .check();
  await page
    .getByRole("button", { name: "Salvar configuração de cobrança" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Configuração financeira salva",
  );
  expect(saved).toMatchObject({
    enabled: true,
    infinitepay_enabled: true,
    infinitepay_handle: "nexus-conta",
    setup_cents: 50000,
    trial_days: 7,
    pix_key: "",
  });
  expect(saved).not.toHaveProperty("setup_value");
});

test("company sees setup and automatic payment link with no manual payment instructions", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        company_id: "company",
        full_name: "Cliente",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "company",
        trade_name: "Empresa",
        slug: "empresa",
        operational_profile: "tourism",
      };
    if (path === "/company/invoices")
      body = {
        blocked: false,
        invoices: [
          {
            id: "invoice",
            invoice_kind: "setup",
            plan_name: "Basic",
            starts_at: "2027-01-17T03:00:00Z",
            ends_at: "2027-01-18T03:00:00Z",
            status: "open",
            overdue: false,
            price_cents: 0,
            setup_cents: 10000,
            extra_trips: 0,
            extra_trip_cents: 1500,
            used_trips: 0,
            included_trips: 2,
            total_cents: 10000,
            due_on: "2027-01-19",
            payment_provider: "infinitepay",
            payment_url: "https://checkout.infinitepay.io/nexus/pagar",
            pix_key: "",
            receiver_name: "",
          },
        ],
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Financeiro e cobranças", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Pagar agora", exact: true }),
  ).toHaveAttribute("href", "https://checkout.infinitepay.io/nexus/pagar");
  await expect(
    page.getByText("Setup (cobrança única):", { exact: false }),
  ).toContainText("100,00");
  await expect(page.getByText("Mensalidade:", { exact: false })).toHaveCount(0);
  await expect(page.getByText("Setup em", { exact: false })).toBeVisible();
  await expect(
    page.getByText("A baixa depende da conferência da Nexus.", {
      exact: false,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Baixa manual excepcional" }),
  ).toHaveCount(0);
});

test("return page waits for backend verification instead of trusting checkout parameters", async ({
  page,
}) => {
  let confirmed = false;
  let callback: any;
  const id = "11111111-1111-4111-8111-111111111111";
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = {};
    if (path === "/auth/me") return route.fulfill({ status: 401, json: {} });
    if (path === "/public/payments/infinitepay/return") {
      callback = route.request().postDataJSON();
      body = { status: "processing" };
    }
    if (path === `/public/payments/infinitepay/${id}`)
      body = { status: confirmed ? "paid" : "open" };
    await route.fulfill({ json: body });
  });
  await page.goto(
    `/pagamento-concluido?checkout=${id}&order_nsu=${id}&transaction_nsu=transaction-test&slug=test-slug&paid=true`,
  );
  await expect(
    page.getByRole("heading", { name: "Conferindo seu pagamento" }),
  ).toBeVisible();
  await expect
    .poll(() => callback)
    .toMatchObject({
      order_nsu: id,
      transaction_nsu: "transaction-test",
      invoice_slug: "test-slug",
    });
  await expect(
    page.getByRole("heading", { name: "Pagamento confirmado" }),
  ).toHaveCount(0);
  confirmed = true;
  await page.getByRole("button", { name: "Atualizar situação" }).click();
  await expect(
    page.getByRole("heading", { name: "Pagamento confirmado" }),
  ).toBeVisible();
});
