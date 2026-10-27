import { test, expect, type Page } from "@playwright/test";

const dataset = {
  generated_at: "2026-10-08T15:00:00Z",
  timezone: "America/Sao_Paulo",
  summary: {
    commercial_trips: 1,
    displacements: 2,
    occupancy_pct: 75,
    confirmed_passengers: 6,
    confirmed_families: 2,
    confirmed_value_cents: 300000,
    paid_value_cents: 200000,
    unpaid_value_cents: 100000,
    average_ticket_cents: 50000,
  },
  daily: [
    { day: "2026-10-08", displacements: 1, commercial_trips: 1 },
    { day: "2026-10-09", displacements: 1, commercial_trips: 0 },
  ],
  vehicles: [
    {
      vehicle_id: "vehicle",
      name: "Executivo SC",
      plate: "ABC1D23",
      displacements: 2,
      occupancy_pct: 75,
      confirmed_peak_sum: 6,
      capacity_sum: 8,
      held_peak_sum: 1,
    },
  ],
  trip_statuses: [{ status: "scheduled", count: 1 }],
  reservation_statuses: [{ status: "confirmed", count: 2 }],
  ranking: [
    {
      product_key: "package",
      name: "Circuito SC",
      passengers: 6,
      value_cents: 300000,
    },
  ],
  upcoming: [
    {
      allocation_id: "allocation",
      leg_id: "leg",
      trip_id: "trip",
      trip_name: "Circuito SC",
      leg_position: 2,
      starts_at: "2026-10-09T11:00:00Z",
      vehicle_name: "Executivo SC",
      plate: "ABC1D23",
      destination: "Blumenau",
      occupancy_pct: 25,
      available: 3,
    },
  ],
};
async function setup(page: Page, role = "admin", empty = false) {
  const requests: URL[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", "");
    let body: any = [],
      status = 200;
    if (path === "/auth/me")
      body = {
        id: "user",
        company_id: "company",
        role,
        full_name: "Gestor",
        is_active: true,
      };
    else if (path === "/company")
      body = {
        id: "company",
        trade_name: "Transportes SC",
        slug: "transportes",
        operational_profile: "regular",
        is_active: true,
      };
    else if (path === "/trips")
      body = [
        {
          id: "trip",
          name: "Circuito SC",
          status: "scheduled",
          destination: "Blumenau",
          mode: "one_way",
          starts_at: "2026-10-09T11:00:00Z",
          ends_at: "2026-10-09T12:00:00Z",
          capacity: 4,
          vehicle_count: 1,
          price_cents: 50000,
        },
      ];
    else if (path === "/trips/trip")
      body = {
        id: "trip",
        name: "Circuito SC",
        status: "scheduled",
        destination: "Blumenau",
        mode: "one_way",
        starts_at: "2026-10-09T11:00:00Z",
        ends_at: "2026-10-09T12:00:00Z",
        price_cents: 50000,
        legs: [],
        vehicles: [],
      };
    else if (path === "/vehicles")
      body = [
        {
          id: "vehicle",
          name: "Executivo SC",
          plate: "ABC1D23",
          capacity: 4,
          is_active: true,
        },
      ];
    else if (path === "/reports/management") {
      requests.push(url);
      if (url.searchParams.get("status") === "cancelled") {
        status = 500;
        body = { detail: "Falha de consulta" };
      } else
        body = empty
          ? {
              ...dataset,
              summary: {
                ...dataset.summary,
                commercial_trips: 0,
                displacements: 0,
                confirmed_passengers: 0,
                confirmed_families: 0,
                confirmed_value_cents: 0,
                paid_value_cents: 0,
                unpaid_value_cents: 0,
                average_ticket_cents: null,
                occupancy_pct: null,
              },
              daily: [],
              vehicles: [],
              upcoming: [],
              ranking: [],
              trip_statuses: [],
              reservation_statuses: [],
            }
          : dataset;
    } else if (path === "/reports/operations")
      body = {
        generated_at: dataset.generated_at,
        trips: [],
        occupancy: [],
        presence: [],
        reservations: [],
      };
    else if (path === "/reports/consumption")
      body = { generated_at: dataset.generated_at, periods: [] };
    await route.fulfill({ status, json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Relatórios", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Movimento por dia", exact: true }),
  ).toBeVisible();
  return requests;
}

test("manager charts are interactive, responsive, filtered and open trip details", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const requests = await setup(page);
  await expect(
    page
      .getByRole("heading", { name: "Passageiros confirmados", exact: true })
      .locator(".."),
  ).toContainText("6");
  await expect(
    page.getByRole("meter", { name: "Ocupação de Executivo SC" }),
  ).toHaveAttribute("aria-valuenow", "75");
  await page
    .getByRole("button", {
      name: "08/10/2026: 1 deslocamentos, 1 viagens comerciais",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("08/10/2026 · 1 deslocamentos · 1 viagens comerciais", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Veículo do relatório", exact: true })
    .selectOption("vehicle");
  await page
    .getByRole("combobox", { name: "Situação da viagem", exact: true })
    .selectOption("scheduled");
  await page
    .getByRole("button", { name: "Aplicar filtros", exact: true })
    .click();
  await expect
    .poll(() => requests.at(-1)?.searchParams.get("vehicle_id"))
    .toBe("vehicle");
  expect(requests.at(-1)?.searchParams.get("status")).toBe("scheduled");
  await page.screenshot({
    path: "../docs/screenshots/visao-gerencial-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/screenshots/visao-gerencial-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Consultar viagem", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Circuito SC");
});

test("attendant sees management finances and legacy reports without franchise access", async ({
  page,
}) => {
  await setup(page, "attendant");
  await expect(
    page
      .getByRole("heading", { name: "Pago / crédito aplicado", exact: true })
      .locator(".."),
  ).toContainText("2.000,00");
  await expect(
    page.getByRole("button", { name: "Consultar franquia", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Ocupação", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Sem registros neste período",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Visão gerencial", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Movimento por dia", exact: true }),
  ).toBeVisible();
});

test("empty occupancy is not zero and errors do not leave stale totals visible", async ({
  page,
}) => {
  await setup(page, "admin", true);
  await expect(
    page
      .getByRole("heading", { name: "Ocupação confirmada", exact: true })
      .locator(".."),
  ).toContainText("Sem dados");
  await expect(
    page.getByRole("heading", {
      name: "Sem viagens neste período",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Situação da viagem", exact: true })
    .selectOption("cancelled");
  await page
    .getByRole("button", { name: "Aplicar filtros", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Falha de consulta");
  await expect(
    page.getByRole("heading", { name: "Ocupação confirmada", exact: true }),
  ).toHaveCount(0);
});
