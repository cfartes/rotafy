import { test, expect } from "@playwright/test";
import { openCompanyRegistration } from "./company-registration";

test("public registration is unavailable from login and direct link", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 401, json: { detail: "Entre novamente" } }),
  );
  await page.goto("/");
  await expect(page.locator('a[href="/cadastro"]')).toHaveCount(0);
  await page.goto("/cadastro");
  await expect(
    page.getByRole("heading", { name: "Cadastro pela equipe Nexus" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cadastrar empresa" }),
  ).toHaveCount(0);
});

test("sales creates the company once then sends welcome without recreating it on failure", async ({
  page,
}) => {
  let created = 0,
    attempts = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [],
      status = 200;
    if (path === "/nexus/plans")
      body = [
        {
          id: "basic",
          name: "Basic",
          is_active: true,
          version_id: "v1",
          included_trips: 30,
          price_cents: 9990,
          extra_trip_cents: 1000,
        },
      ];
    if (path === "/nexus/companies" && route.request().method() === "POST") {
      created++;
      const data = route.request().postDataJSON();
      body = { ...data, id: "company" };
      status = 201;
    }
    if (
      path === "/nexus/companies/company/welcome" &&
      route.request().method() === "POST"
    ) {
      attempts++;
      expect(route.request().postDataJSON().channel).toBe("email");
      if (attempts === 1) {
        status = 503;
        body = { detail: "Configure o e-mail" };
      } else body = { status: "queued" };
    }
    await route.fulfill({ status, json: body });
  });
  await openCompanyRegistration(page);
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Nome comercial", { exact: true })
    .fill("Empresa Teste");
  await dialog
    .getByLabel("Raz\u00e3o social", { exact: true })
    .fill("Empresa Teste LTDA");
  await dialog
    .getByLabel("Identificador de acesso", { exact: true })
    .fill("empresateste");
  await dialog.getByLabel("CPF/CNPJ").fill("52998224725");
  await dialog.getByLabel("Telefone / WhatsApp").fill("+5547999999999");
  await dialog
    .getByLabel("Perfil operacional", { exact: true })
    .selectOption("tourism");
  await dialog
    .getByRole("combobox", { name: "Plano escolhido", exact: true })
    .selectOption("basic");
  await dialog
    .getByLabel("Nome completo", { exact: true })
    .fill("Administrador Teste");
  await dialog
    .getByLabel("E-mail", { exact: true })
    .fill("cliente@example.com");
  await dialog
    .getByLabel("Senha inicial", { exact: true })
    .fill("SenhaSegura!");
  await dialog.getByLabel("CEP", { exact: true }).fill("88372822");
  await dialog.getByLabel("Endereço", { exact: true }).fill("Rua de Teste");
  await dialog.getByLabel("Número", { exact: true }).fill("200");
  await dialog.getByLabel("Bairro", { exact: true }).fill("Centro");
  await dialog.getByLabel("Cidade", { exact: true }).fill("Navegantes");
  await dialog.getByLabel("UF", { exact: true }).selectOption("SC");
  await dialog
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enviar acesso por e-mail", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Configure o e-mail");
  await page
    .getByRole("button", { name: "Enviar acesso por e-mail", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Envio solicitado");
  expect(created).toBe(1);
  expect(attempts).toBe(2);
});
