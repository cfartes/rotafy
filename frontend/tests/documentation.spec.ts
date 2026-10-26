import { test, expect } from "@playwright/test";

test("central pública permite consultar e baixar os materiais sem autenticação", async ({
  page,
  request,
}) => {
  let authRequests = 0;
  await page.route("**/api/v1/auth/me", async (route) => {
    authRequests++;
    await route.fulfill({ status: 401, body: "{}" });
  });
  await page.goto("/ajuda");
  await expect(page.getByRole("heading", { name: /Conheça/ })).toBeVisible();
  await expect(page.getByText("Edição 2026.10 · Revisão 12 · Atualizado em 26/10/2026")).toBeVisible();
  expect(authRequests).toBe(0);
  await expect(page.getByRole("link", { name: /PowerPoint/ })).toHaveCount(0);
  for (const filename of [
    "manual.pdf",
    "apresentacao.pdf",
  ]) {
    const response = await request.get(`/documentacao/${filename}`);
    expect(response.ok()).toBeTruthy();
    const bytes = await response.body();
    expect(bytes.subarray(0, filename.endsWith("pdf") ? 4 : 2).toString()).toBe(
      filename.endsWith("pdf") ? "%PDF" : "PK",
    );
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("manual oferece busca, navegação e leitura em celular", async ({
  page,
}) => {
  await page.goto("/documentacao/manual.html");
  await expect(page.locator(".chapter")).toHaveCount(35);
  await expect(page.getByRole("heading", { name: "Menu automático e bilhetes antecipados" })).toBeVisible();
  await expect(page.locator("#automacoes-whatsapp").locator("..")).toContainText("30 segundos");
  await expect(page.locator("#automacoes-whatsapp").locator("..")).toContainText("dez minutos");
  const search = page.locator('input[type="search"]');
  await search.fill("csv/xlsx");
  const matches = await page.locator(".chapter:visible").count();
  expect(matches).toBeGreaterThan(0);
  expect(matches).toBeLessThan(26);
  await search.fill("zzzzinexistente");
  await expect(page.locator(".chapter:visible")).toHaveCount(0);
  await search.fill("");
  await expect(page.locator(".chapter:visible")).toHaveCount(35);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("apresentação disponibiliza os vinte e seis slides e downloads", async ({
  page,
}) => {
  await page.goto("/documentacao/apresentacao.html");
  await expect(page.locator(".slide")).toHaveCount(26);
  await expect(page.locator('a[href="apresentacao.pdf"]')).toBeVisible();
  await expect(page.getByRole("link", { name: /PowerPoint/ })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("manuais separados por perfil", async ({ page, request }) => {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      },
    }),
  );
  await page.goto("/nexus/ajuda");
  await expect(
    page.getByRole("heading", { name: "Manual do superadmin Nexus" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Ler manual online" }),
  ).toHaveAttribute("href", "/documentacao/manual-superadmin.html");
  await expect(page.getByRole("link", { name: "Baixar PowerPoint editável" })).toHaveAttribute("href", "/api/v1/nexus/documentation/apresentacao.pptx");
  await page.goto("/documentacao/manual-superadmin.html");
  await expect(page.locator(".chapter")).toHaveCount(15);
  await expect(page.getByRole("heading", { name: "10. Supervisão das conexões WhatsApp" })).toBeVisible();
  await expect(page.locator(".cover")).toContainText(
    "Manual do superadmin Nexus",
  );
  const pdf = await request.get("/documentacao/manual-superadmin.pdf");
  expect((await pdf.body()).subarray(0, 4).toString()).toBe("%PDF");
  await page.goto("/documentacao/manual.html");
  await expect(page.locator(".document")).not.toContainText(
    "Buscar sessão pelo telefone",
  );
  await expect(page.locator(".document")).not.toContainText(
    "Administração Nexus:",
  );
  await page.goto("/ajuda");
  await expect(
    page.getByRole("heading", { name: "Manual da empresa" }),
  ).toBeVisible();
  await expect(page.locator('a[href*="manual-superadmin"]')).toHaveCount(0);
});


test("equipe Nexus sem acesso completo não recebe o PowerPoint", async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: {
    id: "staff", role: "nexus_staff", full_name: "Equipe", company_id: null, is_active: true,
  }}));
  await page.goto("/nexus/ajuda");
  await expect(page.getByRole("heading", { name: "Manual do superadmin Nexus" })).toBeVisible();
  await expect(page.getByRole("link", { name: /PowerPoint/ })).toHaveCount(0);
});
