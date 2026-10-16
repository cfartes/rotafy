import { test, expect } from "@playwright/test";

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
      (await nav.getByRole("button").allTextContents()).slice(1, 6),
    )
    .toEqual(["Equipe", "Veículos", "Rotas", "Viagens", "Vender bilhete"]);
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
