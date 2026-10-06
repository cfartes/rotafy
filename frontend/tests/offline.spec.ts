import { testDocument } from "./company-document";
import { nexusCredentials } from "./support/nexus";
import QRCode from "qrcode";
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
const scenarioAccount = nexusCredentials("offline.spec.ts");
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

test("PWA offline, fila persistente, resposta perdida, conflitos e QR revogado", async ({
  page,
}) => {
  test.setTimeout(120000);
  const slug = `e2e-offline-${Date.now()}`,
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
        contact_name: "Família Offline",
        phone: "+5511999999999",
        allocation_id: trip.vehicles.find(
          (v: { name: string }) => v.name === "Ônibus Alfa",
        ).id,
        passengers: [
          { full_name: "Ana Offline" },
          { full_name: "Bruno Offline" },
        ],
      },
    },
  );
  expect(reservationResponse.status()).toBe(201);
  const reservation = await reservationResponse.json();
  const ticketResponse = await page.request.post(
    `/api/v1/reservations/${reservation.id}/tickets`,
    { headers: await headers(page) },
  );
  const issued = (await ticketResponse.json()).issued;
  const leg = trip.legs.find(
    (l: { origin: string }) => l.origin === "Blumenau",
  );
  const prefix = `/api/v1/trips/${trip.id}/vehicles/${reservation.allocation_id}/legs/${leg.id}`;
  const anaTicket = issued.find(
    (t: { full_name: string; leg_id: string }) =>
      t.full_name === "Ana Offline" && t.leg_id === leg.id,
  );
  const brunoTicket = issued.find(
    (t: { full_name: string; leg_id: string }) =>
      t.full_name === "Bruno Offline" && t.leg_id === leg.id,
  );
  const adminContext = await page.context().browser()!.newContext();
  const adminLogin = await adminContext.request.post(
    "http://localhost:5178/api/v1/auth/login",
    {
      headers: { Origin: "http://localhost:5178" },
      data: { company: slug, email, password },
    },
  );
  expect(adminLogin.status()).toBe(200);
  const adminHeaders = {
    Origin: "http://localhost:5178",
    "X-CSRF-Token": (await adminContext.cookies()).find(
      (c) => c.name === "rotafy_csrf",
    )!.value,
  };
  const historyCount = async () =>
    (
      await (
        await adminContext.request.get(
          `http://localhost:5178${prefix}/boarding-history`,
        )
      ).json()
    ).length;
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`guide-${slug}@example.com`);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await page.getByRole("button", { name: "Minhas viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page
    .getByRole("button", { name: "Abrir embarque · Ida", exact: true })
    .click();
  await page.getByRole("button", { name: "Preparar para uso offline" }).click();
  await expect(page).toHaveURL(/offline\?manifest=/);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBeTruthy();
  await page.context().setOffline(true);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Embarque offline", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Sem conexão");
  await expect(page.getByLabel("Leitura de QR por imagem")).toBeEnabled();
  for (const maskPattern of [0, 1, 2, 3, 4, 5, 6, 7] as const) {
    const qrImage = Buffer.from(
      (
        await QRCode.toDataURL(anaTicket.token, {
          width: 360,
          margin: 4,
          maskPattern,
        })
      ).split(",")[1],
      "base64",
    );
    await page.getByLabel("Leitura de QR por imagem").setInputFiles({
      name: `bilhete-${maskPattern}.png`,
      mimeType: "image/png",
      buffer: qrImage,
    });
    await expect(page.getByLabel("Leitura de QR por imagem")).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "Registrar embarque do QR local" }),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  await page
    .getByRole("button", { name: "Registrar embarque do QR local" })
    .click();
  const ana = page
    .locator(".boarding-passengers article")
    .filter({ hasText: "Ana Offline" });
  const bruno = page
    .locator(".boarding-passengers article")
    .filter({ hasText: "Bruno Offline" });
  await expect(ana).toContainText("Pendente neste dispositivo");
  await bruno.getByRole("button", { name: "Embarcar localmente" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await bruno.getByRole("button", { name: "Reverter localmente" }).click();
  await expect(page.getByRole("status")).toContainText("3 ações");
  expect(await historyCount()).toBe(0);
  await page.reload();
  await expect(page.getByRole("status")).toContainText("3 ações");
  await expect(ana).toContainText("A bordo");
  await expect(bruno).toContainText("Aguardando embarque");
  const reopened = await page.context().newPage();
  await reopened.goto(page.url());
  await expect(reopened.getByRole("status")).toContainText("3 ações");
  await expect(
    reopened.getByText("Ana Offline", { exact: true }),
  ).toBeVisible();
  await reopened.close();
  await expect(
    page.getByRole("button", { name: "Limpar dados deste dispositivo" }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/offline-pendentes-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.route(
    "**/legs/*/boarding",
    async (route) => {
      await route.fetch();
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page.context().setOffline(false);
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(page.getByText(/Não foi possível conectar/)).toBeVisible();
  expect(await historyCount()).toBe(1);
  await page.reload();
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  expect(await historyCount()).toBe(3);
  await expect(ana).toContainText("Confirmado no manifesto preparado");
  // Outro operador desembarca enquanto este aparelho registra uma reversão offline.
  await page.context().setOffline(true);
  page.once("dialog", (dialog) => dialog.accept());
  await ana.getByRole("button", { name: "Reverter localmente" }).click();
  const passenger = reservation.passengers.find(
    (p: { full_name: string }) => p.full_name === "Ana Offline",
  );
  expect(
    (
      await adminContext.request.post(
        `http://localhost:5178${prefix}/boarding`,
        {
          headers: adminHeaders,
          data: {
            operation_key: crypto.randomUUID(),
            passenger_id: passenger.id,
            expected_version: 1,
            action: "disembark",
          },
        },
      )
    ).status(),
  ).toBe(201);
  await page.context().setOffline(false);
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Conflito com o servidor", { exact: true }),
  ).toBeVisible();
  await expect(ana).toContainText("Desembarcado");
  expect(await historyCount()).toBe(4);
  await page.screenshot({
    path: "../docs/screenshots/offline-conflito-desktop.png",
    fullPage: true,
  });
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Reaplicar ação após revisão" })
    .click();
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  expect(await historyCount()).toBe(5);
  await ana.getByRole("button", { name: "Desembarcar localmente" }).click();
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  // Revogação é detectada ao sincronizar, mesmo que o QR ainda conste na cópia local.
  await page.context().setOffline(true);
  expect(
    (
      await adminContext.request.post(
        `http://localhost:5178/api/v1/tickets/${brunoTicket.id}/revoke`,
        { headers: adminHeaders },
      )
    ).status(),
  ).toBe(204);
  await page.getByLabel("Código QR ou link do bilhete").fill(brunoTicket.token);
  await page.getByRole("button", { name: "Conferir bilhete offline" }).click();
  await page
    .getByRole("button", { name: "Registrar embarque do QR local" })
    .click();
  await page.context().setOffline(false);
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Rejeitada pelo servidor", { exact: true }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Manter servidor" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  // Sair pelo painel também protege uma ação local ainda não enviada.
  // Impede a sincronização automática ao reconectar antes de testar o logout.
  await page.route("**/api/v1/trips/**/boarding", (route) => route.abort());
  await page.context().setOffline(true);
  await bruno.getByRole("button", { name: "Embarcar localmente" }).click();
  await expect(
    page.getByText("Aguardando envio", { exact: true }),
  ).toBeVisible();
  await page.context().setOffline(false);
  await page.goto("/");
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(page.getByText(/Há ações offline pendentes/)).toBeVisible();
  await page.unroute("**/api/v1/trips/**/boarding");
  await page.goto("/offline");
  await page.getByLabel("Manifesto preparado").selectOption({
    label: `Praia com a família · Ônibus Alfa · Blumenau → Navegantes`,
  });
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  await bruno.getByRole("button", { name: "Desembarcar localmente" }).click();
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(
    page.getByText("Nenhuma ação pendente neste manifesto."),
  ).toBeVisible();
  await page.goto("/");
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  await adminContext.close();
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
