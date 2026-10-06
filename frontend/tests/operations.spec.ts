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
const scenarioAccount = nexusCredentials("operations.spec.ts");
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

test("frota, pacote, ida/volta com dois veículos, duplicação e estorno", async ({
  page,
}) => {
  test.setTimeout(60000);
  const slug = `e2e-operations-${Date.now()}`,
    email = `admin-${slug}@example.com`,
    password = "Senha teste operações 2026!";
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
      name: "Plano Homologação Operações",
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
      slug,
      trade_name: "Agência Homologação Operações",
      corporate_name: "Agência Homologação Operações LTDA",
      admin: { full_name: "Admin Operações", email, password, role: "admin" },
    },
  });
  expect(companyResponse.status()).toBe(201);
  const company = await companyResponse.json();
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
  const driverIds = [];
  for (let i = 0; i < 2; i++) {
    const r = await page.request.post("/api/v1/users", {
      headers: await headers(page),
      data: {
        full_name: `Motorista ${i + 1}`,
        email: `driver${i}-${slug}@example.com`,
        password,
        role: "driver",
      },
    });
    expect(r.status()).toBe(201);
    driverIds.push((await r.json()).id);
  }
  const guide = await page.request.post("/api/v1/users", {
    headers: await headers(page),
    data: {
      full_name: "Guia Praia",
      email: `guide-${slug}@example.com`,
      password,
      role: "guide",
    },
  });
  expect(guide.status()).toBe(201);
  await page.getByRole("button", { name: "Frota, pacotes e viagens" }).click();
  await page.getByRole("button", { name: "Frota", exact: true }).click();
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: "Novo veículo" }).click();
    await page.getByLabel("Nome", { exact: true }).fill(`Ônibus ${i + 1}`);
    await page.getByLabel("Placa").fill(`ABC1D2${i}`);
    await page.getByLabel("Quantidade de lugares").fill("40");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
  }
  const vehicleIds = (
    await (await page.request.get("/api/v1/vehicles")).json()
  ).map((v: { id: string }) => v.id);
  await page.getByRole("button", { name: "Pacotes", exact: true }).click();
  await page.getByRole("button", { name: "Novo pacote" }).click();
  await page.getByLabel("Nome", { exact: true }).fill("Praia em família");
  await page.getByLabel("Destino", { exact: true }).fill("Navegantes");
  await page.getByLabel("Valor por passageiro (R$)").fill("120,00");
  await page.getByLabel("Descrição").fill("Pacote ida e volta para Navegantes");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .locator(".operations-tabs")
    .getByRole("button", { name: "Viagens", exact: true })
    .click();
  await page.getByRole("button", { name: "Nova viagem" }).click();
  const packageId = (
    await (await page.request.get("/api/v1/packages")).json()
  )[0].id;
  await page.getByLabel("Pacote (opcional)").selectOption(packageId);
  await page.getByLabel("UF de origem da ida").selectOption("SC");
  await page
    .getByRole("combobox", { name: "Cidade de origem da ida", exact: true })
    .selectOption("4202404");
  await page.getByLabel("UF de destino da ida").selectOption("SC");
  await page
    .getByRole("combobox", { name: "Cidade de destino da ida", exact: true })
    .selectOption("4211306");
  await page
    .getByRole("button", { name: "Inverter rota para a volta" })
    .click();
  async function fillTimes(day: string) {
    await page
      .getByLabel("Saída da ida", { exact: true })
      .fill(`2027-02-${day}T08:00`);
    await page
      .getByLabel("Chegada da ida", { exact: true })
      .fill(`2027-02-${day}T10:00`);
    await page
      .getByLabel("Saída da volta", { exact: true })
      .fill(`2027-02-${day}T16:00`);
    await page
      .getByLabel("Chegada da volta", { exact: true })
      .fill(`2027-02-${day}T18:00`);
  }
  await fillTimes("10");
  await page.getByRole("button", { name: "Adicionar parada à ida" }).click();
  await page
    .getByLabel("Parada 1", { exact: true })
    .fill("Terminal de Blumenau");
  await page.getByLabel("Horário da parada").fill("2027-02-10T08:30");
  await page
    .getByRole("combobox", { name: "Veículo 1", exact: true })
    .selectOption(vehicleIds[0]);
  await page
    .getByRole("combobox", { name: "Motorista 1", exact: true })
    .selectOption(driverIds[0]);
  await page.getByLabel("Guia Praia").check();
  await page
    .getByRole("button", { name: "Adicionar veículo", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Veículo 2", exact: true })
    .selectOption(vehicleIds[1]);
  await page
    .getByRole("combobox", { name: "Motorista 2", exact: true })
    .selectOption(driverIds[1]);
  await expect(page.getByText("Capacidade total: 80 lugares")).toBeVisible();
  await page.getByRole("button", { name: "Criar viagem", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  const existingTrip = (
    await (await page.request.get("/api/v1/trips")).json()
  )[0];
  const reservation = await page.request.post(
    `/api/v1/trips/${existingTrip.id}/reservations`,
    {
      headers: await headers(page),
      data: {
        operation_key: crypto.randomUUID(),
        contact_name: "Familia da rota",
        phone: "+5511999999999",
        passengers: [{ full_name: "Passageiro da rota" }],
      },
    },
  );
  expect(reservation.status()).toBe(201);
  const reservedFamily = await reservation.json();
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(1);
  await page.screenshot({
    path: "../docs/screenshots/viagens-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await expect(
    page.locator("p").filter({ hasText: /^Embarque: Terminal de Blumenau/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Editar viagem", exact: true })
    .click();
  await expect(page.getByLabel("Saída da ida", { exact: true })).toHaveValue(
    "2027-02-10T08:00",
  );
  await page.getByLabel("Nome da viagem").fill("Viagem revisada pela agência");
  await page.getByLabel("Parada 1", { exact: true }).fill("Terminal revisado");
  await page
    .getByLabel("Endereço da parada 1", { exact: true })
    .fill("Terminal, Blumenau, SC");
  await page
    .getByRole("button", {
      name: "Inverter origem e destino da volta",
      exact: true,
    })
    .click();
  // The original return had no stops; editing must not replace it with outbound stops.
  await expect(page.getByLabel("Parada 1", { exact: true })).toHaveCount(1);
  await page
    .getByRole("button", { name: "Adicionar parada à ida", exact: true })
    .click();
  await page.getByLabel("Parada 2", { exact: true }).fill("Hotel da rota");
  await page
    .getByLabel("Endereço da parada 2", { exact: true })
    .fill("Hotel, Navegantes, SC");
  await page
    .getByLabel("Horário da parada", { exact: true })
    .nth(1)
    .fill("2027-02-10T09:00");
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const preservedFamily = await (
    await page.request.get(`/api/v1/reservations/${reservedFamily.id}`)
  ).json();
  expect(
    preservedFamily.journeys
      .map((j: { dropoff_position: number }) => j.dropoff_position)
      .sort(),
  ).toEqual([1, 3]);
  await expect(page.locator("tbody tr")).toContainText(
    "Viagem revisada pela agência",
  );
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(1);
  const additionalDriver = await page.request.post("/api/v1/users", {
    headers: await headers(page),
    data: {
      full_name: "Motorista Adicional",
      email: `adicional-${slug}@example.com`,
      password,
      role: "driver",
    },
  });
  expect(additionalDriver.status()).toBe(201);
  const additionalVehicle = await page.request.post("/api/v1/vehicles", {
    headers: await headers(page),
    data: { name: "Veículo Adicional", plate: "ZZZ1A23", capacity: 20 },
  });
  expect(additionalVehicle.status()).toBe(201);
  await page
    .getByRole("complementary")
    .getByRole("button", { name: "Alocar veículos", exact: true })
    .click();
  await page
    .locator("tbody")
    .getByRole("button", { name: "Alocar veículos", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Adicionar veículo", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Veículo 3", exact: true })
    .selectOption((await additionalVehicle.json()).id);
  await page
    .getByRole("combobox", { name: "Motorista 3", exact: true })
    .selectOption((await additionalDriver.json()).id);
  await page
    .getByRole("checkbox", {
      name: "Terminal revisado - veículo 3",
      exact: true,
    })
    .uncheck();
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("tbody tr")).toContainText("3 ve\u00edculos");
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(1);
  await page
    .getByRole("complementary")
    .getByRole("button", { name: "Passageiros", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Passageiros e reservas", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Nova reserva", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("complementary")
    .getByRole("button", { name: "Viagens", exact: true })
    .click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page.getByRole("button", { name: "Duplicar viagem" }).click();
  await fillTimes("12");
  await page
    .getByLabel("Horário da parada", { exact: true })
    .nth(0)
    .fill("2027-02-12T08:30");
  await page
    .getByLabel("Horário da parada", { exact: true })
    .nth(1)
    .fill("2027-02-12T09:00");
  await page.getByRole("button", { name: "Criar viagem", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(2);
  await page
    .getByRole("button", { name: "Detalhes", exact: true })
    .first()
    .click();
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: "Cancelar viagem", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByText(/Cancelada ·/)).toBeVisible();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Frota, pacotes e viagens" }).click();
  await expect(page.getByRole("complementary")).not.toBeInViewport();
  await page.screenshot({
    path: "../docs/screenshots/viagens-mobile.png",
    fullPage: true,
  });
  // Encerra somente os registros de homologação criados neste teste.
  const trips = await (await page.request.get("/api/v1/trips")).json();
  for (const t of trips) {
    if (t.status !== "cancelled")
      await page.request.patch(`/api/v1/trips/${t.id}/status`, {
        headers: await headers(page),
        data: { status: "cancelled" },
      });
  }
  await page.request.post("/api/v1/auth/logout", {
    headers: await headers(page),
    data: {},
  });
  const login = await page.request.post("/api/v1/auth/nexus/login", {
    headers: { Origin: "http://localhost:5178" },
    data: { email: env.BOOTSTRAP_EMAIL, password: env.BOOTSTRAP_PASSWORD },
  });
  expect(login.status()).toBe(200);
  expect(
    (
      await page.request.post(
        `/api/v1/nexus/companies/${company.id}/subscription/cancel`,
        { headers: await headers(page), data: {} },
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
