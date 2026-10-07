import { testDocument } from "./company-document";
import { nexusCredentials } from "./support/nexus";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

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
const scenarioAccount = nexusCredentials("billing.spec.ts");
env.BOOTSTRAP_EMAIL =
  scenarioAccount?.email ||
  process.env.ROTAFY_E2E_NEXUS_EMAIL ||
  env.BOOTSTRAP_EMAIL;
env.BOOTSTRAP_PASSWORD =
  scenarioAccount?.password ||
  process.env.ROTAFY_E2E_NEXUS_PASSWORD ||
  env.BOOTSTRAP_PASSWORD;

async function headers(page: Page) {
  const cookies = await page.context().cookies();
  return {
    Origin: "http://localhost:5178",
    "X-CSRF-Token": cookies.find((cookie) => cookie.name === "rotafy_csrf")!
      .value,
  };
}

test("planos, assinatura, histórico e consulta da agência em desktop e mobile", async ({
  page,
}) => {
  const slug = `e2e-plans-${Date.now()}`;
  const code = `e2e-plan-${Date.now()}`;
  const planName = "Plano de Homologação";
  const email = `admin-${slug}@example.com`;
  const password = "Senha teste de planos 2026!";
  await page.goto("/nexus");
  await page.getByLabel("E-mail", { exact: true }).fill(env.BOOTSTRAP_EMAIL);
  await page.getByLabel("Senha", { exact: true }).fill(env.BOOTSTRAP_PASSWORD);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await page
    .getByRole("button", { name: "Planos e assinaturas", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Catálogo de planos" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Novo plano", exact: true }).click();
  await page.getByLabel("Nome do plano").fill(planName);
  await page.getByLabel("Identificador do plano").fill(code);
  await page.getByLabel("Viagens incluídas por mês").fill("2");
  await page.getByLabel("Valor mensal do plano (R$)").fill("99,90");
  await page.getByLabel("Valor por viagem extra (R$)").fill("15,00");
  await page.getByRole("button", { name: "Salvar condições" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const planResponse = await page.request.get("/api/v1/nexus/plans");
  const plan = (await planResponse.json()).find(
    (entry: { code: string }) => entry.code === code,
  );
  const companyResponse = await page.request.post("/api/v1/nexus/companies", {
    headers: await headers(page),
    data: {
      cnpj: testDocument(),
      plan_id: plan.id,
      operational_profile: "tourism",
      slug,
      trade_name: "Agência Homologação Planos",
      corporate_name: "Agência Homologação Planos LTDA",
      admin: { full_name: "Admin Planos", email, password, role: "admin" },
    },
  });
  expect(companyResponse.status()).toBe(201);
  const company = await companyResponse.json();
  await page.reload();
  await page.getByLabel("Buscar empresa").fill(slug);
  await page.getByRole("button", { name: "Editar dados", exact: true }).click();
  await page.getByLabel("Nome comercial").fill("Agência Planos Revisada");
  await page.getByLabel("CPF/CNPJ").fill("52998224725");
  await expect(page.getByLabel("CPF/CNPJ")).toHaveValue("529.982.247-25");
  await page.getByLabel("CPF/CNPJ").fill(testDocument());
  await page
    .getByRole("button", { name: "Salvar empresa", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator("tbody tr")).toContainText(
    "Agência Planos Revisada",
  );
  await page
    .getByRole("button", { name: "Gerenciar plano", exact: true })
    .click();
  await expect(page.getByLabel("Empresa da assinatura")).toHaveValue(
    company.id,
  );
  await expect(
    page.getByRole("heading", { name: "Catálogo de planos" }),
  ).not.toBeVisible();
  await expect(
    page.getByLabel("Plano para o pr\u00f3ximo ciclo"),
  ).toBeVisible();
  const report = page.locator("#subscription-report");
  await expect(
    report.getByText("Assinatura ativa", { exact: true }),
  ).toBeInViewport();
  await expect(report.locator(".subscription-value strong")).toContainText(
    "99,90",
  );
  const card = page.locator(`.plan-card[data-plan-code="${code}"]`);
  await page
    .getByRole("button", { name: "Planos e assinaturas", exact: true })
    .click();
  await card.getByRole("button", { name: "Editar condições" }).click();
  await page.getByLabel("Viagens incluídas por mês").fill("10");
  await page.getByLabel("Valor mensal do plano (R$)").fill("199,90");
  await page.getByRole("button", { name: "Salvar condições" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(report.locator(".subscription-value strong")).toContainText(
    "99,90",
  );
  const updatedCard = page.locator(`.plan-card[data-plan-code="${code}"]`);
  await updatedCard
    .getByRole("button", { name: `Ver histórico do plano ${planName}` })
    .click();
  await expect(
    page.getByRole("dialog").getByText(`Versão 2 · ${planName}`),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText(`Versão 1 · ${planName}`),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fechar", exact: true })
    .click();
  await page.getByLabel("Plano para o próximo ciclo").selectOption(plan.id);
  await page.getByRole("button", { name: "Agendar alteração" }).click();
  await expect(report.getByText(`Próximo plano: ${planName}`)).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../docs/screenshots/planos-nexus.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Cancelar alteração agendada" })
    .click();
  await expect(
    report.getByText(`Próximo plano: ${planName}`),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("button", { name: "Acessar painel" }),
  ).toBeVisible();
  await page.goto("/");
  await page.getByLabel("Identificador da empresa").fill(slug);
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await page.getByRole("button", { name: "Meu plano", exact: true }).click();
  await expect(page.locator(".subscription-value strong")).toContainText(
    "99,90",
  );
  await expect(
    page.getByRole("button", { name: "Novo plano" }),
  ).not.toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("complementary")).not.toBeInViewport();
  await page.evaluate(() => window.scrollTo(0, 0));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/meu-plano-mobile.png",
    fullPage: true,
  });
  // Limpeza dos registros exclusivos deste teste: manter histórico, encerrar renovação.
  const login = await page.request.post("/api/v1/auth/nexus/login", {
    headers: { Origin: "http://localhost:5178" },
    data: { email: env.BOOTSTRAP_EMAIL, password: env.BOOTSTRAP_PASSWORD },
  });
  expect(login.status()).toBe(200);
  const cancel = await page.request.post(
    `/api/v1/nexus/companies/${company.id}/subscription/cancel`,
    { headers: await headers(page) },
  );
  expect(cancel.status()).toBe(204);
  const archive = await page.request.patch(`/api/v1/nexus/plans/${plan.id}`, {
    headers: await headers(page),
    data: { is_active: false },
  });
  expect(archive.status()).toBe(200);
});
