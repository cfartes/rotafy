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
const scenarioAccount = nexusCredentials("public-sales.spec.ts");
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

test("página pública, acompanhamento privado, PAGO e alertas", async ({
  page,
}) => {
  test.setTimeout(60000);
  const slug = `e2e-sales-${Date.now()}`,
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
      slug,
      trade_name: "Agência Homologação Reservas",
      corporate_name: "Agência Homologação Reservas LTDA",
      admin: { full_name: "Admin Reservas", email, password, role: "admin" },
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
  const tripResponse = await page.request.post("/api/v1/trips", {
    headers: await headers(page),
    data: {
      operation_key: crypto.randomUUID(),
      name: "Praia com a família",
      destination: "Navegantes",
      mode: "round_trip",
      price_cents: 12000,
      vehicles: allocations,
      legs: [
        {
          origin: "Blumenau",
          origin_city_id: 4202404,
          destination_city_id: 4106902,
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
          origin_city_id: 4106902,
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
  await page
    .getByRole("button", { name: "Página pública e integrações" })
    .click();
  await page
    .getByRole("button", { name: "Publicar viagem", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Retirar da página" }),
  ).toBeVisible();
  await page.getByLabel("Nome da integração").fill("Site parceiro de teste");
  await page.getByRole("button", { name: "Criar chave", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: /Chave exibida/ }),
  ).toHaveValue(/^rk\./);
  const buyerContext = await page.context().browser()!.newContext();
  const buyer = await buyerContext.newPage();
  await buyer.goto(`http://localhost:5178/comprar/${slug}`);
  await expect(
    buyer.getByRole("heading", { name: "Praia com a família" }),
  ).toBeVisible();
  await buyer.screenshot({
    path: "../docs/screenshots/pagina-publica-desktop.png",
    fullPage: true,
  });
  await buyer.goto(`http://localhost:5178/comprar/${slug}/${trip.id}`);
  await buyer.getByLabel("Nome do responsável").fill("Família Pública");
  await buyer.getByLabel("Telefone da família").fill("(11) 99999-9999");
  await buyer
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Ana Pública");
  await buyer.getByRole("button", { name: "Adicionar passageiro" }).click();
  await expect(
    buyer.getByLabel("CPF do passageiro 1 (obrigatório)", { exact: true }),
  ).toBeVisible();
  await buyer
    .getByLabel("CPF do passageiro 1 (obrigatório)", { exact: true })
    .fill(testDocument());
  await buyer
    .getByRole("checkbox", { name: "Estrangeiro · passageiro 2", exact: true })
    .check();
  await expect(
    buyer.getByLabel("CPF do passageiro 2 (opcional)", { exact: true }),
  ).toBeVisible();
  await buyer
    .getByRole("checkbox", { name: "Estrangeiro · passageiro 2", exact: true })
    .uncheck();
  await buyer
    .getByRole("checkbox", {
      name: "Menor de 5 anos · passageiro 2",
      exact: true,
    })
    .check();
  await buyer
    .getByLabel("Nascimento do passageiro 2", { exact: true })
    .fill("2023-04-10");
  await buyer
    .getByLabel("Nome do passageiro 2", { exact: true })
    .fill("Bruno Público");
  await expect(buyer.locator(".reservation-suggestion")).toContainText(
    "Ônibus Alfa",
  );
  await buyer.setViewportSize({ width: 390, height: 844 });
  expect(
    await buyer.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await buyer.screenshot({
    path: "../docs/screenshots/pagina-publica-mobile.png",
    fullPage: true,
  });
  await buyer
    .getByRole("button", { name: "Solicitar reserva", exact: true })
    .click();
  await expect(buyer).toHaveURL(/acompanhar#token=/);
  await expect(buyer.getByText("Ana Pública", { exact: true })).toBeVisible();
  const trackingUrl = buyer.url();
  await page.getByRole("button", { name: "Frota, pacotes e viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page.getByRole("button", { name: "Reservas e lugares" }).click();
  await page.getByRole("button", { name: "Ver reserva" }).click();
  await page.getByRole("button", { name: "Marcar PAGO", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Desmarcar PAGO", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirmar reserva", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByText(/Confirmada/)).toBeVisible();
  await buyer.reload();
  await expect(buyer.getByText(/· PAGO$/)).toBeVisible();
  await buyer.screenshot({
    path: "../docs/screenshots/acompanhamento-mobile.png",
    fullPage: true,
  });
  await buyer.goto(`http://localhost:5178/comprar/${slug}/${trip.id}`);
  for (let i = 0; i < 5; i++)
    await buyer.getByRole("button", { name: "Adicionar passageiro" }).click();
  await expect(
    buyer.getByRole("button", { name: "Avisar agência" }),
  ).toBeVisible();
  await buyer.getByRole("button", { name: "Avisar agência" }).click();
  await expect(buyer.getByText(/Agência avisada/)).toBeVisible();
  await page
    .getByRole("button", { name: "Revogar link de acompanhamento" })
    .click();
  await buyer.goto(trackingUrl);
  await expect(buyer.getByText(/indisponível|encontrada/)).toBeVisible();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page
    .getByRole("button", { name: "Página pública e integrações" })
    .click();
  await expect(page.getByText(/6 passageiros/)).toBeVisible();
  await page.getByRole("button", { name: "Marcar como visto" }).click();
  await expect(page.getByText("Nenhum alerta pendente.")).toBeVisible();
  await buyerContext.close();
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
