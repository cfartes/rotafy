import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("Superadmin consulta contatos, consentimento, filtros e paginação", async ({
  page,
}) => {
  const queries: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me")
      data = {
        id: "nexus",
        full_name: "Administrador Nexus",
        role: "nexus",
        is_active: true,
        company_id: null,
      };
    if (path === "/nexus/demo-settings")
      data = {
        enabled: false,
        daily_limit: 100,
        version: 0,
        key_configured: false,
        captcha_configured: false,
      };
    if (path === "/nexus/demo-leads") {
      queries.push(url.search);
      const second = url.searchParams.get("page") === "2";
      data = {
        total: 21,
        items: Array.from({ length: second ? 1 : 20 }, (_, i) => ({
          id: `lead-${i}`,
          name: `Pessoa ${second ? 21 : i}`,
          company_name: "Empresa Exemplo",
          phone: "+5547999999999",
          created_at: "2026-11-11T13:00:00Z",
          marketing_consent: i !== 0,
          status: "pending",
          stage: "new",
          source: "https://nexusdataanalytics.com.br",
          campaign: { utm_campaign: "rotafy" },
          city: "Blumenau",
          state: "SC",
          browser: "Chrome",
          os: "Android",
          language: "pt-BR",
          timezone: "America/Sao_Paulo",
        })),
      };
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Leads da demonstração", exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(20);
  await expect(
    page.getByLabel("Situação de Pessoa 0", { exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("combobox", { name: "Autorização comercial", exact: true })
    .selectOption("true");
  await expect
    .poll(() =>
      queries.some((q) => q.includes("page=1") && q.includes("marketing=true")),
    )
    .toBeTruthy();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page
    .getByText("Configurar demonstração do site", { exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Gerar credencial do site", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../artifacts/demo-leads-mobile.png",
    fullPage: true,
  });
});

for (const role of ["nexus_staff", "admin"])
  test(`${role} não recebe o menu de leads`, async ({ page }) => {
    const forbidden: string[] = [];
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname.replace(
        "/api/v1",
        "",
      );
      let data: unknown = [];
      if (path === "/auth/me")
        data = {
          id: "user",
          full_name: "Usuário",
          role,
          is_active: true,
          company_id: role === "admin" ? "company" : null,
        };
      if (path === "/company")
        data = { id: "company", slug: "teste", trade_name: "Empresa" };
      if (path.startsWith("/nexus/demo-")) forbidden.push(path);
      await route.fulfill({ json: data });
    });
    await page.goto(role === "nexus_staff" ? "/nexus" : "/");
    await expect(
      page.getByRole("heading", { name: "Visão geral", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Leads da demonstração", exact: true }),
    ).toHaveCount(0);
    expect(forbidden).toEqual([]);
  });

test("salva chave com confirmação, persiste indicador ao reabrir e mantém ao salvar vazio", async ({
  page,
}) => {
  let config = {
    enabled: false,
    daily_limit: 100,
    version: 0,
    key_configured: true,
    captcha_configured: false,
  };
  const bodies: Record<string, unknown>[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me")
      data = {
        id: "nexus",
        full_name: "Administrador",
        role: "nexus",
        is_active: true,
        company_id: null,
      };
    if (path === "/nexus/demo-leads") data = { items: [], total: 0 };
    if (path === "/nexus/demo-settings") {
      if (route.request().method() === "PATCH") {
        const body = route.request().postDataJSON();
        bodies.push(body);
        config = {
          ...config,
          enabled: body.enabled,
          daily_limit: body.daily_limit,
          captcha_configured:
            config.captcha_configured || !!body.captcha_secret,
          version: config.version + 1,
        };
      }
      data = config;
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Leads da demonstração", exact: true })
    .click();
  await page
    .getByText("Configurar demonstração do site", { exact: true })
    .click();
  const key = page.locator('input[name="demo_captcha_secret"]');
  // Password managers may fill the DOM without firing React onChange.
  await key.evaluate((input: HTMLInputElement) => {
    input.value = "turnstile-fixture-secret";
  });
  await page
    .getByRole("button", { name: "Salvar configuração", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Configuração salva com sucesso" }),
  ).toBeVisible();
  await expect(key).toHaveValue("");
  await expect(
    page.getByRole("status").filter({ hasText: "CAPTCHA: chave cadastrada" }),
  ).toBeVisible();
  expect(bodies[0].captcha_secret).toBe("turnstile-fixture-secret");
  await page
    .getByRole("button", { name: "Salvar configuração", exact: true })
    .click();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[1]).not.toHaveProperty("captcha_secret");
  await page.reload();
  await page
    .getByRole("button", { name: "Leads da demonstração", exact: true })
    .click();
  await page
    .getByText("Configurar demonstração do site", { exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "CAPTCHA: chave cadastrada" }),
  ).toBeVisible();
  await expect(page.locator('input[name="demo_captcha_secret"]')).toHaveValue(
    "",
  );
});

test("rejeição ao ativar é visível no formulário e não apaga a chave digitada", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me")
      data = {
        id: "nexus",
        full_name: "Administrador",
        role: "nexus",
        is_active: true,
        company_id: null,
      };
    if (path === "/nexus/demo-leads") data = { items: [], total: 0 };
    if (path === "/nexus/demo-settings") {
      if (route.request().method() === "PATCH")
        return route.fulfill({
          status: 422,
          json: { detail: "Configure o WhatsApp da Nexus antes de ativar." },
        });
      data = {
        enabled: false,
        daily_limit: 100,
        version: 0,
        key_configured: true,
        captcha_configured: false,
      };
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Leads da demonstração", exact: true })
    .click();
  await page
    .getByText("Configurar demonstração do site", { exact: true })
    .click();
  await page
    .locator('input[name="demo_captcha_secret"]')
    .fill("turnstile-fixture-secret");
  await page.getByLabel("Habilitar demonstração pública").check();
  await page
    .getByRole("button", { name: "Salvar configuração", exact: true })
    .click();
  await expect(
    page
      .locator("details")
      .filter({
        has: page.getByText("Configurar demonstração do site", { exact: true }),
      })
      .getByRole("alert"),
  ).toContainText("WhatsApp da Nexus");
  await expect(page.locator('input[name="demo_captcha_secret"]')).toHaveValue(
    "turnstile-fixture-secret",
  );
  await expect(
    page.getByText("Configuração salva com sucesso", { exact: false }),
  ).toHaveCount(0);
});
