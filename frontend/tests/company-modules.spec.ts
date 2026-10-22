import { test, expect } from "@playwright/test";

const company = {
  id: "company",
  slug: "empresa",
  trade_name: "Empresa parceira",
  operational_profile: "tourism",
  is_active: true,
};
const catalog = {
  modules: [
    { id: "team", name: "Equipe", description: "Colaboradores", requires: [] },
    { id: "fleet", name: "Veículos", description: "Frota", requires: [] },
    {
      id: "trips",
      name: "Viagens",
      description: "Deslocamentos",
      requires: ["team", "fleet"],
    },
    { id: "routes", name: "Rotas", description: "Percursos", requires: [] },
    {
      id: "packages",
      name: "Pacotes",
      description: "Destinos",
      requires: ["routes", "trips"],
    },
    {
      id: "boarding",
      name: "Bilhetes e embarque",
      description: "QR Code",
      requires: ["trips"],
    },
    {
      id: "whatsapp",
      name: "WhatsApp",
      description: "Mensagens",
      requires: [],
    },
    {
      id: "integrations",
      name: "Integrações",
      description: "Parceiros",
      requires: ["team"],
    },
  ],
  presets: {
    full: [
      "team",
      "fleet",
      "trips",
      "routes",
      "packages",
      "boarding",
      "whatsapp",
      "integrations",
    ],
    integrated: [
      "team",
      "fleet",
      "trips",
      "boarding",
      "whatsapp",
      "integrations",
    ],
  },
};

test("superadmin selects the integrated preset and dependent modules stay consistent", async ({
  page,
}) => {
  let current = { enabled_modules: catalog.presets.full, version: 1 };
  let submitted: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      };
    if (path === "/nexus/companies") body = [company];
    if (path === "/nexus/modules") body = catalog;
    if (path === "/nexus/companies/company/modules") {
      if (route.request().method() === "PUT") {
        submitted = route.request().postDataJSON();
        current = { enabled_modules: submitted.enabled_modules, version: 2 };
      }
      body = current;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Módulos por empresa", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Empresa", exact: true })
    .selectOption("company");
  await page
    .getByRole("button", { name: "WhatsApp e embarque integrado" })
    .click();
  await expect(
    page.getByRole("checkbox", { name: /^Pacotes/ }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: /^Bilhetes e embarque/ }),
  ).toBeChecked();
  await page.getByRole("checkbox", { name: /^Equipe/ }).uncheck();
  await expect(
    page.getByRole("checkbox", { name: /^Viagens/ }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: /^Integrações/ }),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "WhatsApp e embarque integrado" })
    .click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Salvar módulos" }).click();
  await expect.poll(() => submitted?.expected_version).toBe(1);
  expect(new Set(submitted.enabled_modules)).toEqual(
    new Set(catalog.presets.integrated),
  );
});

test("integrated company sees enabled menus and can issue a scoped partner key", async ({
  page,
}) => {
  let submitted: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        full_name: "Admin",
        company_id: company.id,
        enabled_modules: catalog.presets.integrated,
        is_active: true,
      };
    if (path === "/company") body = company;
    if (path === "/users")
      body = [
        {
          id: "technical",
          full_name: "Integração Parceiro",
          email: "api@example.com",
          role: "attendant",
          is_active: true,
        },
      ];
    if (path === "/integrations/service-keys/scopes")
      body = [{ id: "trips:read", name: "Consultar viagens e deslocamentos" }];
    if (
      path === "/integrations/service-keys" &&
      route.request().method() === "POST"
    ) {
      submitted = route.request().postDataJSON();
      body = { id: "key", token: "ri.company.example-secret" };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Rotas", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Pacotes", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Vender bilhete", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Viagens", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Integração com parceiros", exact: true })
    .click();
  await page.getByLabel("Nome da integração").fill("Parceiro de teste");
  await page
    .getByLabel("Usuário técnico (atendente)")
    .selectOption("technical");
  await page
    .getByRole("checkbox", { name: /Consultar viagens e deslocamentos/ })
    .check();
  await page.getByRole("button", { name: "Criar chave de integração" }).click();
  await expect(page.getByLabel(/Chave criada/)).toHaveValue(
    "ri.company.example-secret",
  );
  expect(submitted).toEqual({
    name: "Parceiro de teste",
    user_id: "technical",
    valid_days: 90,
    scopes: ["trips:read"],
  });
  await page.getByRole("button", { name: "Ocultar chave" }).click();
  await expect(page.getByLabel(/Chave criada/)).toHaveCount(0);
});
