import { openCompanyRegistration } from "./company-registration";
import { test, expect } from "@playwright/test";

test("first registration requires an explicit operational profile", async ({
  page,
}) => {
  let submitted: any;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    let status = 200,
      body: any = [];
    if (path === "/nexus/plans")
      body = [
        {
          id: "basic",
          name: "Basic",
          is_active: true,
          version_id: "v1",
          included_trips: 30,
          price_cents: 10000,
          extra_trip_cents: 1000,
        },
      ];
    else if (path === "/nexus/companies") {
      submitted = request.postDataJSON();
      body = {
        id: "company",
        slug: submitted.slug,
        trade_name: submitted.trade_name,
      };
      status = 201;
    } else if (path === "/auth/me") {
      status = 401;
      body = { detail: "Entre novamente" };
    }
    await route.fulfill({ status, json: body });
  });
  await openCompanyRegistration(page);
  const dialog = page.getByRole("dialog", { name: "Cadastrar empresa" });
  const profile = dialog.getByRole("combobox", {
    name: "Perfil operacional",
    exact: true,
  });
  await expect(profile).toHaveValue("");
  expect(
    await profile.evaluate(
      (element) => (element as HTMLSelectElement).validity.valueMissing,
    ),
  ).toBe(true);
  await dialog
    .getByLabel("Nome comercial", { exact: true })
    .fill("Transportes SC");
  await dialog
    .getByLabel("Razão social", { exact: true })
    .fill("Transportes SC LTDA");
  await dialog
    .getByLabel("Identificador de acesso", { exact: true })
    .fill("transportessc");
  await dialog.getByLabel("Telefone / WhatsApp").fill("47999999999");
  await dialog.getByLabel("CPF/CNPJ").fill("52998224725");
  await profile.selectOption("regular");
  await dialog
    .getByRole("combobox", { name: "Plano escolhido", exact: true })
    .selectOption("basic");
  await dialog
    .getByLabel("Nome completo", { exact: true })
    .fill("Administrador SC");
  await dialog.getByLabel("E-mail", { exact: true }).fill("admin@example.com");
  await dialog
    .getByLabel("Senha inicial", { exact: true })
    .fill("Senha de teste 2026!");
  await dialog
    .getByRole("button", { name: "Cadastrar empresa", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Empresa cadastrada" }),
  ).toBeVisible();
  expect(submitted.operational_profile).toBe("regular");
  expect(submitted.plan_id).toBe("basic");
});

test("Nexus edits the company profile with the previous value", async ({
  page,
}) => {
  let submitted: any;
  let company = {
    id: "company",
    slug: "transportes",
    trade_name: "Transportes",
    corporate_name: "Transportes LTDA",
    cnpj: "52998224725",
    contact_phone: null,
    operational_profile: "tourism",
    is_active: true,
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        full_name: "Nexus",
        role: "nexus",
        is_active: true,
        company_id: null,
      };
    else if (path === "/nexus/companies") body = [company];
    else if (path === "/nexus/companies/company/details") {
      submitted = request.postDataJSON();
      company = { ...company, ...submitted };
      body = company;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Empresas", exact: true }).click();
  await expect(
    page.getByText("Turismo e transfers", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Editar dados", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Editar empresa" });
  await dialog
    .getByRole("combobox", { name: "Perfil operacional", exact: true })
    .selectOption("regular");
  await dialog
    .getByRole("button", { name: "Salvar empresa", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  expect(submitted.operational_profile).toBe("regular");
  expect(submitted.expected_profile).toBe("tourism");
  await expect(
    page.getByText("Transporte regular", { exact: true }),
  ).toBeVisible();
});
