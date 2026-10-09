import { nexusCredentials } from "./support/nexus";
import { testDocument } from "./company-document";
import { test, expect } from "@playwright/test";
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
const scenarioAccount = nexusCredentials("foundation.spec.ts");
env.BOOTSTRAP_EMAIL =
  scenarioAccount?.email ||
  process.env.ROTAFY_E2E_NEXUS_EMAIL ||
  env.BOOTSTRAP_EMAIL;
env.BOOTSTRAP_PASSWORD =
  scenarioAccount?.password ||
  process.env.ROTAFY_E2E_NEXUS_PASSWORD ||
  env.BOOTSTRAP_PASSWORD;

test("login, cadastro de empresa, equipe e logout no navegador", async ({
  page,
}) => {
  const slug = `e2e-${Date.now()}`;
  const email = `admin-${Date.now()}@example.com`;
  const password = "Senha temporaria E2E 2026!";
  await page.goto("/nexus");
  await expect(
    page.getByRole("heading", { name: "Bem-vindo de volta" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/login-desktop.png",
    fullPage: true,
  });
  await page.getByLabel("E-mail", { exact: true }).fill(env.BOOTSTRAP_EMAIL);
  await page.getByLabel("Senha", { exact: true }).fill(env.BOOTSTRAP_PASSWORD);
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  const planResponse = await page.request.post("/api/v1/nexus/plans", {
    headers: {
      Origin: "http://localhost:5178",
      "X-CSRF-Token": (await page.context().cookies()).find(
        (cookie) => cookie.name === "rotafy_csrf",
      )!.value,
    },
    data: {
      code: slug,
      name: "Plano cadastro teste",
      included_trips: 10,
      price_cents: 9900,
      extra_trip_cents: 1500,
    },
  });
  expect(planResponse.status()).toBe(201);
  const plan = await planResponse.json();
  await page.getByRole("button", { name: "Nova empresa" }).click();
  await page
    .getByRole("combobox", { name: "Perfil operacional", exact: true })
    .selectOption("tourism");
  await page.getByLabel("Plano escolhido").selectOption(plan.id);
  await page.getByLabel("Nome comercial").fill("Receptivo de Homologação");
  await page.getByLabel("Razão social").fill("Receptivo de Homologação LTDA");
  await page.getByLabel("Identificador de acesso").fill(slug);
  await page.getByLabel("Nome completo").fill("Administrador Teste");
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Senha inicial").fill(password);
  await page.getByLabel("CPF/CNPJ").fill("0155522000177");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "CPF/CNPJ: Informe CPF com 11 dígitos ou CNPJ com 14 caracteres.",
  );
  await expect(page.getByLabel("Identificador de acesso")).toHaveValue(slug);
  await expect(page.getByLabel("Senha inicial")).toHaveValue(password);
  await page.getByLabel("CPF/CNPJ").fill("04.252.011/0001-11");
  await expect(page.getByLabel("CPF/CNPJ")).toHaveValue("04.252.011/0001-11");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "os dígitos verificadores não conferem",
  );
  await page.getByLabel("CPF/CNPJ").fill("52998224725");
  await expect(page.getByLabel("CPF/CNPJ")).toHaveValue("529.982.247-25");
  await page.getByLabel("CPF/CNPJ").fill("12abc34501de35");
  await expect(page.getByLabel("CPF/CNPJ")).toHaveValue("12.ABC.345/01DE-35");
  await page.getByLabel("CPF/CNPJ").fill(testDocument());
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Nova empresa", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Perfil operacional", exact: true })
    .selectOption("tourism");
  await page.getByLabel("Plano escolhido").selectOption(plan.id);
  await page.getByLabel("CPF/CNPJ").fill(testDocument());
  await page.getByLabel("Nome comercial").fill("Outra Empresa");
  await page.getByLabel("Razão social").fill("Outra Empresa LTDA");
  await page.getByLabel("Identificador de acesso").fill(slug);
  await page.getByLabel("Nome completo").fill("Outro Administrador");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`outro-${slug}@example.com`);
  await page.getByLabel("Senha inicial").fill(password);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Identificador de acesso já cadastrado",
  );
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page.getByRole("textbox", { name: "Buscar empresa" }).fill(slug);
  await expect(page.locator("tbody tr")).toHaveCount(1);
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
    page.getByRole("heading", { name: "Pessoas da equipe" }),
  ).toBeVisible();
  await page.goto("/offline");
  await expect(page).toHaveURL("http://localhost:5178/");
  await expect(
    page.getByRole("heading", {
      name: "Cadastros e operação da empresa",
      exact: true,
    }),
  ).toBeVisible();
  const sidebar = page.getByRole("complementary");
  await sidebar.getByRole("button", { name: "Veículos", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Novo veículo", exact: true }),
  ).toBeVisible();
  await sidebar.getByRole("button", { name: "Viagens", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Nova viagem", exact: true }),
  ).toBeVisible();
  await sidebar
    .getByRole("button", { name: "Alocar veículos", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Alocar veículos em viagens",
      exact: true,
    }),
  ).toBeVisible();
  await sidebar
    .getByRole("button", { name: "Passageiros", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Passageiros", exact: true }),
  ).toBeVisible();
  await sidebar
    .getByRole("button", { name: "Visão geral", exact: true })
    .click();
  await page.getByRole("button", { name: "Identidade da empresa" }).click();
  await page.getByLabel("Nome comercial").fill("Receptivo de Homologação Sul");
  await page.getByLabel("Cor principal").fill("#153e65");
  await page.getByRole("button", { name: "Salvar identidade" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByText("Receptivo de Homologação Sul", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .click();
  await page.getByLabel("Nome completo").fill("Guia Teste");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`guia-${slug}@example.com`);
  await page.getByLabel("Perfil").selectOption("guide");
  await page.getByLabel("Senha inicial").fill(password);
  await page
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .last()
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByText("Guia Teste", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .click();
  const inviteDialog = page.getByRole("dialog", {
    name: "Adicionar à equipe",
    exact: true,
  });
  await inviteDialog
    .getByLabel("Enviar convite para a pessoa definir sua senha")
    .check();
  await expect(inviteDialog.getByLabel("Senha inicial")).toHaveCount(0);
  await inviteDialog.getByLabel("Nome completo").fill("Pessoa Convidada");
  await inviteDialog
    .getByLabel("E-mail", { exact: true })
    .fill(`convidado-${slug}@example.com`);
  await page.route("**/api/v1/users/invitations", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.password).toBeUndefined();
    expect(body.full_name).toBe("Pessoa Convidada");
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: crypto.randomUUID(),
        email_status: "pending",
      }),
    });
  });
  await inviteDialog
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .click();
  await expect(inviteDialog).not.toBeVisible();
  await page.unroute("**/api/v1/users/invitations");
  await page
    .getByRole("button", { name: "E-mails de acesso", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "E-mails de acesso", exact: true }),
  ).toContainText("Nenhum envio registrado.");
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page.screenshot({
    path: "../docs/screenshots/painel-empresa.png",
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByText("Guia Teste", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Equipe", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Equipe", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("complementary")).not.toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/equipe-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Sair da conta" }).click();
  await expect(
    page.getByRole("heading", { name: "Bem-vindo de volta" }),
  ).toBeVisible();
  expect(
    (
      await page.request.post("/api/v1/auth/nexus/login", {
        headers: { Origin: "http://localhost:5178" },
        data: { email: env.BOOTSTRAP_EMAIL, password: env.BOOTSTRAP_PASSWORD },
      })
    ).status(),
  ).toBe(200);
  const cleanupHeaders = {
    Origin: "http://localhost:5178",
    "X-CSRF-Token": (await page.context().cookies()).find(
      (cookie) => cookie.name === "rotafy_csrf",
    )!.value,
  };
  const cleanupCompany = (
    await (await page.request.get("/api/v1/nexus/companies")).json()
  ).find((company: { slug: string }) => company.slug === slug);
  expect(
    (
      await page.request.post(
        `/api/v1/nexus/companies/${cleanupCompany.id}/subscription/cancel`,
        { headers: cleanupHeaders, data: {} },
      )
    ).status(),
  ).toBe(204);
  expect(
    (
      await page.request.patch(`/api/v1/nexus/plans/${plan.id}`, {
        headers: cleanupHeaders,
        data: { is_active: false },
      })
    ).status(),
  ).toBe(200);
});

test("login responsivo e erro de credenciais", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Bem-vindo de volta" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/login-mobile.png",
    fullPage: true,
  });
  await page.getByLabel("Identificador da empresa").fill("inexistente");
  await page.getByLabel("E-mail", { exact: true }).fill("erro@example.com");
  await page.getByLabel("Senha", { exact: true }).fill("senha incorreta");
  await page.getByRole("button", { name: "Acessar painel" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Empresa, e-mail ou senha inválidos",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("recuperação de acesso da agência e Nexus sem envio real", async ({
  page,
}) => {
  for (const nexus of [false, true]) {
    await page.goto(nexus ? "/nexus" : "/");
    await page.getByRole("button", { name: "Esqueci minha senha" }).click();
    const dialog = page.getByRole("dialog", {
      name: "Recuperar acesso",
      exact: true,
    });
    if (!nexus)
      await dialog.getByLabel("Identificador da empresa").fill("empresa-teste");
    await dialog.getByLabel("E-mail cadastrado").fill("usuario@example.com");
    await page.route("**/api/v1/auth/forgot-password", async (route) => {
      expect(route.request().postDataJSON()).toEqual({
        email: "usuario@example.com",
        company: nexus ? null : "empresa-teste",
        nexus,
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message:
            "Se houver uma conta ativa com esses dados, enviaremos um link de recuperação.",
        }),
      });
    });
    await dialog
      .getByRole("button", { name: "Enviar link de recuperação" })
      .click();
    await expect(dialog.getByRole("status")).toContainText(
      "Se houver uma conta ativa",
    );
    await expect(
      dialog.getByRole("button", { name: "Enviar link de recuperação" }),
    ).toBeDisabled();
    await dialog.getByLabel("Fechar", { exact: true }).click();
    await page.unroute("**/api/v1/auth/forgot-password");
  }
});
