import { testDocument } from "./company-document";
import { nexusCredentials } from "./support/nexus";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const env = Object.fromEntries(
  fs
    .readFileSync(path.resolve("..", ".env"), "utf8")
    .split(/\r?\n/)
    .filter((l) => l && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1)];
    }),
);
const scenarioAccount = nexusCredentials("reports.spec.ts");
env.BOOTSTRAP_EMAIL =
  scenarioAccount?.email ||
  process.env.ROTAFY_E2E_NEXUS_EMAIL ||
  env.BOOTSTRAP_EMAIL;
env.BOOTSTRAP_PASSWORD =
  scenarioAccount?.password ||
  process.env.ROTAFY_E2E_NEXUS_PASSWORD ||
  env.BOOTSTRAP_PASSWORD;
async function headers(page: Page) {
  return {
    Origin: "http://localhost:5178",
    "X-CSRF-Token": (await page.context().cookies()).find(
      (c) => c.name === "rotafy_csrf",
    )!.value,
  };
}

test("Relatorios de ocupacao, PAGO, presenca, consumo e CSV", async ({
  page,
}) => {
  test.setTimeout(120000);
  const slug = `e2e-reports-${Date.now()}`,
    email = `admin-${slug}@example.com`,
    password = "Senha teste reservas 2026!";
  await page.goto("/nexus");
  await page.getByLabel("E-mail", { exact: true }).fill(env.BOOTSTRAP_EMAIL);
  await page.getByLabel("Senha", { exact: true }).fill(env.BOOTSTRAP_PASSWORD);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  const planResponse = await page.request.post("/api/v1/nexus/plans", {
    headers: await headers(page),
    data: {
      code: slug,
      name: "Plano Homologação Reservas",
      included_trips: 5,
      price_cents: 9000,
      extra_trip_cents: 1000,
    },
  });
  expect(planResponse.status()).toBe(201);
  const plan = await planResponse.json();
  const companyResponse = await page.request.post("/api/v1/nexus/companies", {
    headers: await headers(page),
    data: {
      cnpj: testDocument(),
      plan_id: plan.id,
      operational_profile: "tourism",
      slug,
      trade_name: "Agência Homologação Reservas",
      corporate_name: "Agência Homologação Reservas LTDA",
      admin: { full_name: "Admin Reservas", email, password, role: "admin" },
    },
  });
  expect(companyResponse.status()).toBe(201);
  const company = await companyResponse.json();
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("button", { name: "Acessar painel" }),
  ).toBeVisible();
  await page.goto("/");
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  const allocations = [];
  for (let i = 0; i < 2; i++) {
    const driverResponse = await page.request.post("/api/v1/users", {
      headers: await headers(page),
      data: {
        full_name: `Motorista ${i + 1}`,
        email: `driver${i}-${slug}@example.com`,
        password,
        role: "driver",
      },
    });
    expect(driverResponse.status()).toBe(201);
    const driver = await driverResponse.json();
    const vResponse = await page.request.post("/api/v1/vehicles", {
      headers: await headers(page),
      data: {
        name: i === 0 ? "Ônibus Alfa" : "Ônibus Beta",
        plate: `DEF1G2${i}`,
        capacity: i === 0 ? 3 : 5,
      },
    });
    expect(vResponse.status()).toBe(201);
    allocations.push({
      vehicle_id: (await vResponse.json()).id,
      driver_id: driver.id,
      guide_ids: [],
    });
  }
  const guideResponse = await page.request.post("/api/v1/users", {
    headers: await headers(page),
    data: {
      full_name: "Guia Embarque",
      email: `guide-${slug}@example.com`,
      password,
      role: "guide",
    },
  });
  expect(guideResponse.status()).toBe(201);
  const guide = await guideResponse.json();
  // A viagem deste teste tem um guia no primeiro veículo.
  // A atribuição é feita na criação, antes de iniciar a operação.
  const tripResponse = await page.request.post("/api/v1/trips", {
    headers: await headers(page),
    data: {
      operation_key: crypto.randomUUID(),
      name: "Praia com a família",
      destination: "Navegantes",
      mode: "round_trip",
      price_cents: 12000,
      vehicles: allocations.map((a, index) => ({
        ...a,
        guide_ids: index === 0 ? [guide.id] : [],
      })),
      legs: [
        {
          origin: "Blumenau",
          origin_city_id: 4202404,
          destination_city_id: 4211306,
          destination: "Navegantes",
          starts_at: "2027-03-10T08:00:00-03:00",
          ends_at: "2027-03-10T10:00:00-03:00",
          stops: [
            {
              name: "Terminal",
              kind: "both",
              scheduled_at: "2027-03-10T08:30:00-03:00",
            },
          ],
        },
        {
          origin: "Navegantes",
          origin_city_id: 4211306,
          destination_city_id: 4202404,
          destination: "Blumenau",
          starts_at: "2027-03-10T16:00:00-03:00",
          ends_at: "2027-03-10T18:00:00-03:00",
          stops: [],
        },
      ],
    },
  });
  expect(tripResponse.status()).toBe(201);
  const trip = await tripResponse.json();
  const reservationResponse = await page.request.post(
    `/api/v1/trips/${trip.id}/reservations`,
    {
      headers: await headers(page),
      data: {
        operation_key: crypto.randomUUID(),
        contact_name: "Família Reports",
        phone: "+5511999999999",
        allocation_id: trip.vehicles.find(
          (v: { name: string }) => v.name === "Ônibus Alfa",
        ).id,
        passengers: [
          { full_name: "Ana Reports" },
          { full_name: "Bruno Reports" },
        ],
      },
    },
  );
  expect(reservationResponse.status()).toBe(201);
  const reservation = await reservationResponse.json();

  expect(
    (
      await page.request.patch(
        `/api/v1/reservations/${reservation.id}/payment`,
        { headers: await headers(page), data: { is_paid: true } },
      )
    ).status(),
  ).toBe(200);
  const leg = trip.legs.find(
    (l: { origin: string }) => l.origin === "Blumenau",
  );
  const prefix = `/api/v1/trips/${trip.id}/vehicles/${reservation.allocation_id}/legs/${leg.id}`;
  const passenger = reservation.passengers[0];
  expect(
    (
      await page.request.post(`${prefix}/boarding`, {
        headers: await headers(page),
        data: {
          operation_key: crypto.randomUUID(),
          passenger_id: passenger.id,
          expected_version: 0,
          action: "board",
        },
      })
    ).status(),
  ).toBe(201);
  await page.getByRole("button", { name: "Relatórios", exact: true }).click();
  await page.getByRole("button", { name: "Ocupação", exact: true }).click();
  await expect(
    page.getByText("Sem registros neste período", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Data inicial").fill("2027-03-10");
  await page.getByLabel("Data final").fill("2027-03-10");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.locator("table tbody tr").filter({ hasText: "Ônibus Alfa" }),
  ).toHaveCount(3);
  await page.screenshot({
    path: "../docs/screenshots/relatorios-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Reservas e pagamentos", exact: true })
    .click();
  await expect(page.locator("table tbody tr")).toHaveCount(1);
  await expect(
    page.getByRole("cell", { name: "PAGO", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Mostrar pagamento").selectOption("unpaid");
  await expect(
    page.getByText("Sem registros neste período", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Mostrar pagamento").selectOption("paid");
  await expect(page.locator("table tbody tr")).toHaveCount(1);
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV completo" }).click();
  const file = await downloaded;
  const content = fs.readFileSync((await file.path())!, "utf8");
  expect(content).toContain("Família Reports");
  expect(content).not.toContain("phone");
  await page.getByRole("button", { name: "Presença", exact: true }).click();
  await expect(page.locator("table tbody tr")).toHaveCount(4);
  const ida = page
    .locator("table tbody tr")
    .filter({ hasText: "Ônibus Alfa" })
    .filter({ hasText: "Blumenau" })
    .first();
  await expect(ida.getByRole("cell").nth(5)).toHaveText("1");
  await expect(ida.getByRole("cell").nth(6)).toHaveText("1");
  await expect(ida.getByRole("cell").nth(7)).toHaveText("0");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/relatorios-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page
    .getByRole("button", { name: "Consumo da franquia", exact: true })
    .click();
  await page.getByLabel("Data inicial").fill(today);
  await page.getByLabel("Data final").fill(today);
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.locator("table tbody tr")).toHaveCount(1);
  await expect(
    page.locator("table tbody tr").getByRole("cell").nth(5),
  ).toHaveText("1");
  expect(
    (
      await page.request.post(`${prefix}/boarding`, {
        headers: await headers(page),
        data: {
          operation_key: crypto.randomUUID(),
          passenger_id: passenger.id,
          expected_version: 1,
          action: "disembark",
        },
      })
    ).status(),
  ).toBe(201);
  // Histórico de homologação preservado, mas sem renovação ou consumo pendente.
  expect(
    (
      await page.request.patch(`/api/v1/trips/${trip.id}/status`, {
        headers: await headers(page),
        data: { status: "cancelled" },
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await page.request.post("/api/v1/auth/nexus/login", {
        headers: { Origin: "http://localhost:5178" },
        data: { email: env.BOOTSTRAP_EMAIL, password: env.BOOTSTRAP_PASSWORD },
      })
    ).status(),
  ).toBe(200);
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Relatórios", exact: true }).click();
  await page.getByLabel("Empresa do relatório").selectOption(company.id);
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.locator("table tbody tr")).toHaveCount(1);
  await expect(
    page.locator("table tbody tr").getByRole("cell").nth(5),
  ).toHaveText("0");
  expect((await page.request.get("/api/v1/nexus/metrics")).status()).toBe(200);
  expect(
    (
      await page.request.post(
        `/api/v1/nexus/companies/${company.id}/subscription/cancel`,
        { headers: await headers(page) },
      )
    ).status(),
  ).toBe(204);
  expect(
    (
      await page.request.patch(`/api/v1/nexus/plans/${plan.id}`, {
        headers: await headers(page),
        data: { is_active: false },
      })
    ).status(),
  ).toBe(200);
});
