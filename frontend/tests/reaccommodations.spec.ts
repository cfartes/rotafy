import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function setup(
  page: Page,
  role = "attendant",
  fail = false,
  financial = false,
) {
  let transferred = false;
  let payload: any;
  const original = {
    id: "case",
    trip_name: "Viagem cancelada",
    original_starts_at: "2027-01-10T11:00:00Z",
    contact_name: "Maria Silva",
    phone: "+5547999999999",
    passenger_names: ["Maria Silva", "João Silva"],
    passenger_count: 2,
    total_cents: 24000,
    paid_cents: 24000,
    credit_cents: 0,
    source_version: 0,
    status: "pending",
    original_status: "confirmed",
    manual_review: false,
    remaining_credit_cents: 0,
    financial_note: "",
    note: "",
  };
  const legs = [
    {
      id: "leg",
      origin: "Blumenau",
      destination: "Navegantes",
      origin_address: "Rodoviária, 100",
      destination_address: "Centro",
      stops: [],
    },
  ];
  if (financial)
    Object.assign(original, {
      status: "transferred",
      remaining_credit_cents: 6000,
    });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "staff",
        full_name: "Equipe",
        role,
        company_id: "company",
        is_active: true,
        enabled_modules: ["team", "trips", "fleet", "sales", "boarding"],
      };
    else if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        is_active: true,
      };
    else if (path === "/company/billing/upcoming")
      body = { upcoming: null, show_reminder: false };
    else if (path === "/reaccommodations")
      body = {
        items: transferred ? [] : [original],
        pending_families: transferred || financial ? 0 : 1,
        pending_passengers: transferred || financial ? 0 : 2,
        financial_pending: !transferred && financial ? 1 : 0,
        has_more: false,
      };
    else if (
      path.endsWith("/financial-resolution") ||
      path.endsWith("/close")
    ) {
      transferred = true;
      body = { status: "reviewed" };
    } else if (path.endsWith("/suggestions"))
      body = {
        has_more: false,
        items: [
          {
            trip: {
              id: "target",
              name: "Viagem alternativa",
              starts_at: "2027-01-11T11:00:00Z",
              edit_version: 2,
              price_cents: 15000,
              mode: "one_way",
              legs,
            },
            journeys: [
              { leg_id: "leg", boarding_position: 0, dropoff_position: 1 },
            ],
            vehicles: [
              { allocation_id: "bus", name: "Ônibus 01", available: 6 },
            ],
            suggested_allocation_id: "bus",
            total_cents: 30000,
            difference_seconds: 86400,
          },
        ],
      };
    else if (path.endsWith("/transfer")) {
      payload = request.postDataJSON();
      if (fail)
        return route.fulfill({
          status: 409,
          json: {
            detail:
              "A viagem perdeu a disponibilidade. Atualize as alternativas.",
          },
        });
      transferred = true;
      body = {
        id: "new",
        status: "confirmed",
        total_cents: 30000,
        credit_cents: 24000,
        issued_tickets: [],
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  return () => payload;
}

test("atendente revisa família, valores e embarque antes de realocar", async ({
  page,
}) => {
  const payload = await setup(page);
  await expect(
    page.getByRole("complementary", {
      name: "Reservas afetadas por cancelamentos",
    }),
  ).toContainText("2 passageiro(s)");
  await page
    .getByRole("button", { name: "Revisar passageiros e alternativas" })
    .click();
  await page.getByRole("button", { name: "Revisar Maria Silva" }).click();
  await page
    .getByRole("button", { name: "Escolher Viagem alternativa" })
    .click();
  await expect(page.getByText(/Crédito disponível:/)).toContainText("240,00");
  await page
    .getByRole("button", { name: "Confirmar realocação da família" })
    .click();
  expect(payload()).toBeUndefined();
  await page.getByRole("checkbox", { name: "Conferi os pontos" }).check();
  await page.getByRole("checkbox", { name: "O cliente concordou" }).check();
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({
    path: "../docs/screenshots/realocacao-reserva-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Confirmar realocação da família" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Realocação concluída" }),
  ).toBeVisible();
  expect(payload()).toMatchObject({
    trip_id: "target",
    recognized_cash_cents: 24000,
    consent: true,
    logistics_reviewed: true,
    expected_source_paid_cents: 24000,
  });
});

test("perda de vagas mantém a pendência e informa o atendente", async ({
  page,
}) => {
  await setup(page, "attendant", true);
  await page
    .getByRole("button", { name: "Revisar passageiros e alternativas" })
    .click();
  await page.getByRole("button", { name: "Revisar Maria Silva" }).click();
  await page
    .getByRole("button", { name: "Escolher Viagem alternativa" })
    .click();
  await page.getByRole("checkbox", { name: "Conferi os pontos" }).check();
  await page.getByRole("checkbox", { name: "O cliente concordou" }).check();
  await page
    .getByRole("button", { name: "Confirmar realocação da família" })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "perdeu a disponibilidade" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Realocação concluída" }),
  ).toHaveCount(0);
});

test("motorista não recebe controles administrativos de realocação", async ({
  page,
}) => {
  await setup(page, "driver");
  await expect(
    page.getByRole("button", { name: "Revisar passageiros e alternativas" }),
  ).toHaveCount(0);
});

test("saldo a favor exige registrar o tratamento financeiro sem executar reembolso", async ({
  page,
}) => {
  await setup(page, "admin", false, true);
  await expect(
    page.getByText("Saldos de reservas canceladas aguardam revisão."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Revisar passageiros e alternativas" })
    .click();
  await page.getByRole("button", { name: "Revisar Maria Silva" }).click();
  await expect(
    page.getByText(
      "Informe o tratamento realizado fora do sistema. Nenhum estorno será executado.",
    ),
  ).toBeVisible();
  await page
    .getByLabel("Como o saldo foi tratado")
    .fill("Saldo conferido e ajustado junto ao cliente");
  await page
    .getByRole("button", { name: "Registrar revisão financeira" })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Atendimento registrado" }),
  ).toBeVisible();
});
