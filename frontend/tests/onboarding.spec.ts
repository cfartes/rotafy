import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { nexusCredentials } from "./support/nexus";
import { testDocument } from "./company-document";

const env = Object.fromEntries(
  fs
    .readFileSync(path.resolve("..", ".env"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);
const account = nexusCredentials("onboarding.spec.ts");
const nexusEmail = account?.email || env.BOOTSTRAP_EMAIL;
const nexusPassword = account?.password || env.BOOTSTRAP_PASSWORD;
async function headers(page: Page) {
  return {
    Origin: "http://localhost:5178",
    "X-CSRF-Token": (await page.context().cookies()).find(
      (cookie) => cookie.name === "rotafy_csrf",
    )!.value,
  };
}

test("primeiro acesso: plano e documento obrigatórios, assinatura automática e login da empresa", async ({
  page,
}) => {
  const slug = `e2eonboarding${Date.now()}`;
  const email = `${slug}@example.com`;
  const password = "Senha onboarding teste 2026!";
  await page.goto("/nexus");
  await page.getByLabel("E-mail", { exact: true }).fill(nexusEmail);
  await page.getByLabel("Senha", { exact: true }).fill(nexusPassword);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("button", { name: "Nova empresa" }),
  ).toBeVisible();
  const planResponse = await page.request.post("/api/v1/nexus/plans", {
    headers: await headers(page),
    data: {
      code: slug,
      name: "Plano primeiro acesso",
      included_trips: 15,
      price_cents: 12000,
      extra_trip_cents: 1800,
    },
  });
  expect(planResponse.status()).toBe(201);
  const plan = await planResponse.json();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("button", { name: "Acessar painel" }),
  ).toBeVisible();
  await page.goto("/");
  await page.getByRole("link", { name: "Criar minha empresa" }).click();
  await expect(page).toHaveURL("http://localhost:5178/cadastro");
  await page.getByLabel("Nome comercial").fill("Empresa Primeiro Acesso");
  await page.getByLabel("Razão social").fill("Empresa Primeiro Acesso LTDA");
  await page.getByLabel("Identificador de acesso").fill(slug);
  await page.getByLabel("Telefone / WhatsApp").fill("47999999999");
  await expect(page.getByLabel("Telefone / WhatsApp")).toHaveValue(
    "(47) 99999-9999",
  );
  const dialogWidth = await page
    .getByRole("dialog")
    .evaluate((dialog) => dialog.getBoundingClientRect().width);
  expect(dialogWidth).toBeGreaterThan(800);
  await page.getByLabel("Nome completo").fill("Admin Primeiro Acesso");
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha inicial").fill(password);
  await page.getByLabel("Confirmar senha").fill(password);
  expect(
    await page
      .getByLabel("CPF/CNPJ")
      .evaluate((input: HTMLInputElement) => input.checkValidity()),
  ).toBe(false);
  expect(
    await page
      .getByLabel("Plano escolhido")
      .evaluate((input: HTMLSelectElement) => input.checkValidity()),
  ).toBe(false);
  await page
    .getByRole("combobox", { name: "Perfil operacional", exact: true })
    .selectOption("tourism");
  await page.getByLabel("Plano escolhido").selectOption(plan.id);
  await page.getByLabel("CPF/CNPJ").fill("11111111111");
  await page
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("CPF");
  await expect(page.getByLabel("Plano escolhido")).toHaveValue(plan.id);
  await page.getByLabel("CPF/CNPJ").fill(testDocument());
  await page.getByRole("dialog").evaluate((dialog) => {
    dialog.scrollTop = 0;
  });
  await page.screenshot({
    path: "../docs/screenshots/cadastro-empresa-plano.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page
      .getByRole("dialog")
      .evaluate((dialog) => dialog.scrollWidth <= dialog.clientWidth),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/screenshots/cadastro-empresa-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Empresa cadastrada" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Entrar na minha empresa" }).click();
  await expect(page.getByLabel("Identificador da empresa")).toHaveValue(slug);
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("button", { name: "Gerenciar veículos" }),
  ).toBeVisible();
  const company = await (await page.request.get("/api/v1/company")).json();
  const report = await (
    await page.request.get("/api/v1/company/subscription")
  ).json();
  expect(report.subscription.plan_id).toBe(plan.id);
  expect(report.current_period.used_trips).toBe(0);
  expect((await page.request.get("/api/v1/nexus/companies")).status()).toBe(
    403,
  );
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("button", { name: "Acessar painel" }),
  ).toBeVisible();
  expect(
    (
      await page.request.post("/api/v1/auth/nexus/login", {
        headers: { Origin: "http://localhost:5178" },
        data: { email: nexusEmail, password: nexusPassword },
      })
    ).status(),
  ).toBe(200);
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
