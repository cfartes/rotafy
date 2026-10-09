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
const scenarioAccount = nexusCredentials("reservations.spec.ts");
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

test("reserva familiar, bloqueio, confirmação, realocação, falta de lugares e importação", async ({
  page,
}) => {
  test.setTimeout(60000);
  const slug = `e2ereservations${Date.now()}`,
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
      contact_phone: "+5547999999999",
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
  await page.getByRole("button", { name: "Frota, pacotes e viagens" }).click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page.getByRole("button", { name: "Reservas e lugares" }).click();
  await expect(
    page.getByRole("heading", { name: "Reservas · Praia com a família" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Nova reserva", exact: true }).click();
  await page.getByLabel("Nome do responsável").fill("Família Silva");
  await page.getByLabel("Telefone da família").fill("(11) 99999-9999");
  await page
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Ana Silva");
  await page.getByRole("button", { name: "Adicionar passageiro" }).click();
  await page
    .getByLabel("Nome do passageiro 2", { exact: true })
    .fill("Bruno Silva");
  await page
    .getByRole("combobox", { name: "Situação inicial", exact: true })
    .selectOption("pending");
  await expect(page.locator(".reservation-suggestion")).toContainText(
    "Ônibus Alfa",
  );
  await page.getByRole("button", { name: "Salvar reserva" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const row = page.locator("tbody tr").filter({ hasText: "Família Silva" });
  await expect(row).toContainText("Bloqueio pendente");
  await expect(row).toContainText("2 passageiros");
  await expect(row).toContainText("240,00");
  await row.getByRole("button", { name: "Ver reserva" }).click();
  await expect(
    page.getByRole("dialog").getByText("Ana Silva", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirmar reserva", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByText(/Confirmada/)).toBeVisible();
  await page
    .getByRole("button", { name: "Editar reserva", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar reserva",
    exact: true,
  });
  await editor
    .getByLabel("Responsável", { exact: true })
    .fill("Família Silva revisada");
  await editor
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Ana Silva revisada");
  await editor
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("Ana Silva revisada", { exact: false }),
  ).toBeVisible();
  const beta = trip.vehicles.find(
    (v: { name: string }) => v.name === "Ônibus Beta",
  );
  await page
    .getByRole("combobox", { name: "Realocar família para", exact: true })
    .selectOption(beta.id);
  await page
    .getByRole("button", { name: "Realocar família", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByText(/Ônibus Beta ·/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page.getByRole("button", { name: "Nova reserva", exact: true }).click();
  for (let i = 0; i < 3; i++)
    await page.getByRole("button", { name: "Adicionar passageiro" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Nenhum veículo comporta a família inteira",
  );
  await expect(
    page.getByRole("button", { name: "Salvar reserva" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page
    .getByRole("button", { name: "Importar CSV/XLSX", exact: true })
    .click();
  await page.getByLabel("Arquivo de passageiros").setInputFiles({
    name: "invalido.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "familia,responsavel,telefone,pais,passageiro,cpf\nF1,Responsável,errado,BR,Visitante,\n",
    ),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(page.getByRole("alert")).toContainText("Linha 2");
  await expect(
    page.getByRole("button", { name: "Confirmar importação" }),
  ).toBeDisabled();
  const csv = Buffer.from(
    "familia,responsavel,telefone,pais,passageiro,cpf\nF1,Família Visitante,+442083661177,GB,Visitante Internacional,\n",
  );
  await page
    .getByLabel("Arquivo de passageiros")
    .setInputFiles({ name: "familias.csv", mimeType: "text/csv", buffer: csv });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(
    page.getByRole("heading", { name: "Prévia da importação" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Importar CSV/XLSX", exact: true })
    .click();
  await page
    .getByLabel("Arquivo de passageiros")
    .setInputFiles({ name: "familias.csv", mimeType: "text/csv", buffer: csv });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(page.getByText(/Este arquivo já foi importado/)).toBeVisible();
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  expect(
    (await (await page.request.get("/api/v1/company/subscription")).json())
      .current_period.used_trips,
  ).toBe(1);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../docs/screenshots/reservas-desktop.png",
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
    path: "../docs/screenshots/reservas-mobile.png",
    fullPage: true,
  });
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
