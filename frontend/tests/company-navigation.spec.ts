import { test, expect } from "@playwright/test";

test("admin opens company registration from workspace logo and saves contact", async ({ page }) => {
  let company = { id: "a", slug: "empresa", trade_name: "Empresa A", corporate_name: "Empresa A LTDA", cnpj: "52998224725", contact_phone: "+5547999999999", primary_color: "#123456", accent_color: "#abcdef", operational_profile: "tourism" };
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", company_id: "a", full_name: "Admin", is_active: true };
    if (path === "/company") {
      if (route.request().method() === "PATCH") {
        saved = route.request().postDataJSON();
        company = { ...company, ...saved };
      }
      body = company;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Editar cadastro da empresa" }).click();
  await expect(page.getByRole("heading", { name: "Cadastro da empresa", exact: true })).toBeVisible();
  await expect(page.getByLabel("Identificador de acesso", { exact: true })).toHaveAttribute("readonly", "");
  await page.getByLabel("Nome comercial", { exact: true }).fill("Empresa atualizada");
  await page.getByLabel("Telefone/WhatsApp", { exact: true }).fill("+5511999999999");
  await page.getByRole("button", { name: "Salvar cadastro", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cadastro da empresa", exact: true })).toHaveCount(0);
  expect(saved.contact_phone).toBe("+5511999999999");
  expect(saved.slug).toBeUndefined();
  await expect(page.locator(".workspace strong")).toHaveText("Empresa atualizada");
});

test("separate registrations and edit collaborator role", async ({ page }) => {
  const people: any[] = [
    {
      id: "guide",
      full_name: "Colaborador Teste",
      email: "guia@example.com",
      role: "guide",
      company_id: "company",
      is_active: true,
      contact_phone: "+5547999999999",
    },
  ];
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        full_name: "Admin",
        email: "admin@example.com",
        role: "admin",
        company_id: "company",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        operational_profile: "tourism",
        primary_color: "#0A2540",
        accent_color: "#0d7773",
      };
    if (path === "/users") body = people;
    if (path === "/users/guide" && route.request().method() === "PATCH") {
      saved = route.request().postDataJSON();
      Object.assign(people[0], saved);
      body = people[0];
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  const nav = page.getByRole("navigation");
  await expect(nav.getByRole("button").first()).toHaveText("Visão geral");
  await expect
    .poll(async () =>
      (await nav.getByRole("button").allTextContents()).filter(label => ["Equipe", "Veículos", "Rotas", "Pacotes", "Viagens", "Vender bilhete"].includes(label)),
    )
    .toEqual(["Equipe", "Veículos", "Rotas", "Pacotes", "Viagens", "Vender bilhete"]);
  await expect(
    nav.getByRole("button", { name: "Identidade da empresa", exact: true }),
  ).toHaveCount(0);
  await nav.getByRole("button", { name: "Viagens", exact: true }).click();
  await expect(
    page.getByText("Viagens comerciais", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".operations-tabs")).toHaveCount(0);
  await nav.getByRole("button", { name: "Pacotes", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Novo pacote", exact: true }),
  ).toBeVisible();
  await nav.getByRole("button", { name: "Veículos", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Novo veículo", exact: true }),
  ).toBeVisible();
  await nav.getByRole("button", { name: "Equipe", exact: true }).click();
  await page
    .getByRole("button", { name: "Editar colaborador", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Editar colaborador" });
  await dialog
    .getByLabel("Nome completo", { exact: true })
    .fill("Motorista Teste");
  await dialog.getByLabel("Função do colaborador").selectOption("driver");
  await dialog
    .getByRole("button", { name: "Salvar colaborador", exact: true })
    .click();
  await expect(
    page.getByText("Motorista Teste", { exact: true }),
  ).toBeVisible();
  expect(saved.role).toBe("driver");
});
