import { test, expect } from "@playwright/test";

test("restricted Nexus staff sees companies without financial or configuration requests", async ({
  page,
}) => {
  const forbidden: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "staff",
        full_name: "Equipe Nexus",
        email: "equipe@example.com",
        role: "nexus_staff",
        company_id: null,
        is_active: true,
      };
    else if (path === "/nexus/companies")
      body = [
        {
          id: "company",
          slug: "empresa",
          trade_name: "Empresa teste",
          corporate_name: "Empresa",
          is_active: true,
        },
      ];
    else if (path !== "/audit") forbidden.push(path);
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await expect(
    page.getByRole("button", { name: "Empresas", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Editar dados", exact: true }),
  ).toBeVisible();
  for (const name of [
    "Configurações",
    "Financeiro e cobranças",
    "Planos e assinaturas",
    "Relatórios",
    "Equipe Nexus",
    "Gerenciar plano",
  ]) {
    await expect(page.getByRole("button", { name, exact: true })).toHaveCount(
      0,
    );
  }
  expect(forbidden).toEqual([]);
});

test("full Nexus administrator creates restricted internal user", async ({
  page,
}) => {
  let created: any;
  let users = [
    {
      id: "nexus",
      full_name: "Nexus",
      email: "nexus@example.com",
      role: "nexus",
      is_active: true,
    },
  ];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { ...users[0], company_id: null };
    if (path === "/nexus/users") {
      if (route.request().method() === "POST") {
        created = route.request().postDataJSON();
        users = [...users, { ...created, id: "staff", is_active: true }];
        body = users[1];
      } else body = users;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Equipe Nexus", exact: true }).click();
  await page
    .getByRole("button", { name: "Adicionar usuário Nexus", exact: true })
    .click();
  await page.getByLabel("Nome completo", { exact: true }).fill("Pessoa Nexus");
  await page.getByLabel("E-mail", { exact: true }).fill("pessoa@example.com");
  await page.getByLabel("Senha inicial", { exact: true }).fill("SenhaSegura!");
  await expect(page.getByLabel("Perfil de acesso Nexus")).toHaveValue(
    "nexus_staff",
  );
  await page
    .getByRole("button", { name: "Cadastrar usuário Nexus", exact: true })
    .click();
  await expect(
    page.getByText("pessoa@example.com", { exact: false }),
  ).toBeVisible();
  expect(created.role).toBe("nexus_staff");
});
