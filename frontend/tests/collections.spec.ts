import { test, expect } from "@playwright/test";

test("Nexus requests billing tests with explicit recipients and shows delivery status", async ({
  page,
}) => {
  const sent: any[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      };
    if (path === "/nexus/integrations")
      body = {
        version: 1,
        openwa_key_configured: true,
        resend_key_configured: true,
        email_from: "acesso@example.com",
      };
    if (path === "/nexus/billing/settings")
      body = {
        version: 1,
        enabled: false,
        pix_key: "financeiro@example.com",
        receiver_name: "Nexus",
        nexus_session_id: "11111111-1111-4111-8111-111111111111",
      };
    if (path === "/nexus/billing/test-delivery") {
      sent.push(route.request().postDataJSON());
      body = { status: "queued" };
    }
    if (path === "/nexus/billing/notifications")
      body = sent.map((s, i) => ({
        ...s,
        id: String(i),
        kind: "test",
        status: "sent",
        created_at: "2026-10-15T16:00:00Z",
        error_code: null,
      }));
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await page
    .getByLabel("E-mail para teste de cobrança")
    .fill("teste@example.com");
  await page
    .getByRole("button", { name: "Testar e-mail de cobrança", exact: true })
    .click();
  await expect(
    page.getByText(/E-mail · teste@example.com · Aceito/),
  ).toBeVisible();
  await page
    .getByLabel("WhatsApp para teste de cobrança")
    .fill("+5547999999999");
  await page
    .getByRole("button", { name: "Testar WhatsApp de cobrança", exact: true })
    .click();
  await expect(
    page.getByText(/WhatsApp · \+5547999999999 · Aceito/),
  ).toBeVisible();
  expect(sent.map((s) => s.channel)).toEqual(["email", "whatsapp"]);
  expect(sent.every((s) => s.operation_key)).toBeTruthy();
});

const invoice = {
  id: "11111111-1111-4111-8111-111111111111",
  company_name: "Agência A",
  plan_name: "Basic",
  starts_at: "2026-09-15T03:00:00Z",
  ends_at: "2026-10-15T03:00:00Z",
  status: "open",
  overdue: true,
  price_cents: 9900,
  extra_trip_cents: 1500,
  extra_trips: 1,
  included_trips: 2,
  used_trips: 3,
  total_cents: 11400,
  due_on: "2026-10-19",
  pix_key: "financeiro@example.com",
  receiver_name: "Nexus",
  paid_at: null as string | null,
  confirmed_at: null as string | null,
  payment_note: "",
};

test("superadmin configura Pix e confirma manualmente a cobrança", async ({
  page,
}) => {
  let settings = {
    version: 1,
    enabled: false,
    pix_key: "",
    receiver_name: "",
    nexus_session_id: null,
  };
  let current = { ...invoice };
  let saved: any, payment: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      };
    if (path === "/nexus/integrations")
      body = {
        version: 1,
        openwa_key_configured: true,
        resend_key_configured: true,
        email_from: "acesso@example.com",
      };
    if (path === "/nexus/billing/settings") {
      if (route.request().method() === "PUT") {
        saved = route.request().postDataJSON();
        settings = { ...settings, ...saved, version: 2 };
      }
      body = settings;
    }
    if (path === "/nexus/billing/invoices") body = [current];
    if (path === "/nexus/billing/pix-preview")
      body = {
        key: "financeiro@example.com",
        payload:
          "00020126440014br.gov.bcb.pix0122financeiro@example.com5204000053039865802BR5905NEXUS6008BLUMENAU62070503***63041384",
      };
    if (path.endsWith("/paid")) {
      payment = route.request().postDataJSON();
      current = {
        ...current,
        status: "paid",
        paid_at: payment.paid_at,
        confirmed_at: "2026-10-15T17:00:00Z",
        payment_note: payment.note,
      };
      body = current;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await page
    .getByLabel("Chave Pix da Nexus", { exact: true })
    .fill("financeiro@example.com");
  await page.getByLabel("Nome do favorecido do Pix").fill("Nexus");
  const copy =
    "00020126440014br.gov.bcb.pix0122financeiro@example.com5204000053039865802BR5905NEXUS6008BLUMENAU62070503***63041384";
  await page
    .getByLabel("Pix Copia e Cola sem valor definido (opcional)")
    .fill(copy);
  for (const name of [
    "Ver QR Code da chave Pix",
    "Ver QR Code do Copia e Cola",
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("img", { name: "QR Code Pix para conferência" }),
    ).toBeVisible();
    await expect(dialog.getByLabel("Pix Copia e Cola do QR Code")).toHaveValue(
      copy,
    );
    await dialog
      .getByRole("button", { name: "Fechar QR Code", exact: true })
      .click();
    expect(saved).toBeUndefined();
  }
  await page
    .getByLabel("ID da sessão WhatsApp de cobrança da Nexus")
    .fill("11111111-1111-4111-8111-111111111111");
  await page
    .getByLabel("Ativar avisos e cobranças mensais automáticas")
    .check();
  await page
    .getByRole("button", { name: "Salvar configuração de cobrança" })
    .click();
  await expect(page.getByText("Configuração financeira salva.")).toBeVisible();
  expect(saved.pix_key).toBe("financeiro@example.com");
  expect(saved.enabled).toBe(true);
  expect(saved.pix_copy_paste).toBe(copy);
  await page
    .getByRole("button", { name: "Financeiro e cobranças", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmar recebimento do Pix", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Confirmar recebimento do Pix",
  });
  await dialog
    .getByLabel("Data e hora do recebimento")
    .fill("2026-10-15T11:00");
  await dialog
    .getByLabel("Observação ou referência do Pix")
    .fill("Conferido no banco");
  await dialog
    .getByRole("button", { name: "Confirmar pagamento integral" })
    .click();
  await expect(dialog).not.toBeVisible();
  expect(payment.note).toBe("Conferido no banco");
  await expect(
    page.getByText("Conferido no banco", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Confirmar recebimento do Pix",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("empresa bloqueada consulta o Pix sem acesso às configurações ou baixa", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = [];
    if (path.endsWith("/auth/me"))
      body = {
        id: "admin",
        role: "admin",
        full_name: "Admin",
        company_id: "company",
        is_active: true,
        financial_blocked: true,
      };
    if (path.endsWith("/company"))
      body = {
        id: "company",
        trade_name: "Agência A",
        slug: "agenciaa",
        is_active: true,
      };
    if (path.endsWith("/company/invoices"))
      body = { blocked: true, invoices: [invoice] };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Financeiro e cobranças", exact: true })
    .click();
  await expect(
    page.getByText("financeiro@example.com", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Há cobrança vencida aguardando confirmação.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Configurações", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirmar recebimento do Pix" }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
