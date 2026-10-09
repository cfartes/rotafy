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
const scenarioAccount = nexusCredentials("boarding.spec.ts");
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

test("bilhetes QR, guia e motorista com presença por trecho", async ({
  page,
}) => {
  test.setTimeout(60000);
  const slug = `e2e-boarding-${Date.now()}`,
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
  const reserveResponse = await page.request.post(
    `/api/v1/trips/${trip.id}/reservations`,
    {
      headers: await headers(page),
      data: {
        operation_key: crypto.randomUUID(),
        contact_name: "Família QR",
        phone: "+5511999999999",
        allocation_id: trip.vehicles[0].id,
        status: "confirmed",
        passengers: [{ full_name: "Ana QR" }, { full_name: "Bruno QR" }],
      },
    },
  );
  expect(reserveResponse.status()).toBe(201);
  await page.getByRole("button", { name: "Frota, pacotes e viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page.getByRole("button", { name: "Reservas e lugares" }).click();
  await page.getByRole("button", { name: "Ver reserva" }).click();
  await page
    .getByRole("button", { name: "Emitir bilhetes", exact: true })
    .click();
  const link = page.getByRole("textbox", {
    name: "Link do bilhete de Ana QR",
  });
  await expect(link).toHaveValue(/bilhete#token=bt/);
  const ticketUrl = await link.inputValue();
  const token = new URLSearchParams(new URL(ticketUrl).hash.slice(1)).get(
    "token",
  )!;
  const buyerContext = await page
    .context()
    .browser()!
    .newContext({ viewport: { width: 390, height: 844 } });
  const buyer = await buyerContext.newPage();
  await buyer.goto(ticketUrl);
  await expect(
    buyer.getByRole("heading", { name: "Ana QR", exact: true }),
  ).toBeVisible();
  const qr = buyer.getByRole("img", { name: "QR do bilhete individual" });
  await expect(qr).toBeVisible();
  const png = Buffer.from(
    (await qr.getAttribute("src"))!.split(",")[1],
    "base64",
  );
  await expect(
    buyer.getByRole("button", { name: "Imprimir ou salvar PDF" }),
  ).toBeEnabled();
  expect(
    await buyer.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await buyer.screenshot({
    path: "../docs/screenshots/bilhete-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`guide-${slug}@example.com`);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await page.getByRole("button", { name: "Minhas viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Abrir embarque · Ida", exact: true }),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Abrir embarque · Ida", exact: true })
    .click();
  await expect(page.locator(".boarding-counts")).toContainText("2");
  await page
    .getByLabel("Leitura de QR por imagem")
    .setInputFiles({ name: "bilhete.png", mimeType: "image/png", buffer: png });
  await expect(
    page.getByRole("button", { name: "Confirmar embarque do QR" }),
  ).toBeVisible();
  // Simula a perda da resposta depois que o servidor já registrou o embarque.
  await page.route(
    "**/legs/*/boarding",
    async (route) => {
      await route.fetch();
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page.getByRole("button", { name: "Confirmar embarque do QR" }).click();
  await expect(
    page.getByRole("button", { name: "Tentar novamente a mesma operação" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Tentar novamente a mesma operação" })
    .click();
  const ana = page
    .locator(".boarding-passengers article")
    .filter({ hasText: "Ana QR" });
  const bruno = page
    .locator(".boarding-passengers article")
    .filter({ hasText: "Bruno QR" });
  await expect(ana).toContainText("A bordo");
  await expect(
    page.getByRole("button", { name: "Tentar novamente a mesma operação" }),
  ).toHaveCount(0);
  const journey = trip.legs.find(
    (l: { origin: string }) => l.origin === "Blumenau",
  );
  const allocation = trip.vehicles.find(
    (v: { name: string }) => v.name === "Ônibus Alfa",
  );
  const recorded = await page.request.get(
    `/api/v1/trips/${trip.id}/vehicles/${allocation.id}/legs/${journey.id}/boarding-history`,
  );
  expect((await recorded.json()).length).toBe(1);
  await bruno.getByRole("button", { name: "Embarcar", exact: true }).click();
  await expect(bruno).toContainText("A bordo");
  page.once("dialog", (dialog) => dialog.accept());
  await bruno.getByRole("button", { name: "Reverter", exact: true }).click();
  await expect(bruno).toContainText("Aguardando embarque");
  await page.screenshot({
    path: "../docs/screenshots/embarque-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("complementary")).not.toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/embarque-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await buyer.reload();
  await expect(buyer.getByText("A bordo", { exact: true })).toBeVisible();
  await ana.getByRole("button", { name: "Desembarcar", exact: true }).click();
  await expect(ana).toContainText("Desembarcado");
  await page.getByRole("button", { name: "Voltar às viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page
    .getByRole("button", { name: "Abrir embarque · Volta", exact: true })
    .click();
  await page.getByLabel("Código QR ou link do bilhete").fill(token);
  await page
    .getByRole("button", { name: "Conferir bilhete", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Confirmar embarque do QR", exact: true }),
  ).toBeVisible();
  const driverContext = await page.context().browser()!.newContext();
  const driver = await driverContext.newPage();
  await driver.goto("http://localhost:5178/");
  await driver.getByLabel("Identificador da empresa").fill(slug);
  await driver
    .getByLabel("E-mail", { exact: true })
    .fill(`driver0-${slug}@example.com`);
  await driver.getByLabel("Senha", { exact: true }).fill(password);
  await driver.getByRole("button", { name: "Acessar painel" }).click();
  await driver.getByRole("button", { name: "Minhas viagens" }).click();
  await driver.getByRole("button", { name: "Detalhes", exact: true }).click();
  await expect(
    driver.getByRole("link", {
      name: "Abrir rota no Google Maps",
      exact: true,
    }),
  ).toHaveCount(2);
  const routeUrl = await driver
    .getByRole("link", { name: "Abrir rota no Google Maps", exact: true })
    .first()
    .getAttribute("href");
  expect(new URL(routeUrl!).hostname).toBe("www.google.com");
  expect(new URL(routeUrl!).searchParams.has("key")).toBe(false);
  await driver
    .getByRole("button", { name: "Abrir embarque · Ida", exact: true })
    .click();
  await expect(driver.locator(".boarding-passengers article")).toHaveCount(2);
  await expect(
    driver.getByRole("button", { name: "Conferir bilhete", exact: true }),
  ).toBeVisible();
  await driverContext.close();
  await buyerContext.close();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
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
