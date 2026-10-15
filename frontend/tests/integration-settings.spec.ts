import { test, expect } from "@playwright/test";

test("automatic phone association saves on blur and displays background discovery", async ({
  page,
}) => {
  let saved = 0;
  const company: any = {
    id: "company",
    trade_name: "Empresa",
    slug: "empresa",
    is_active: true,
    session_id: null,
    enabled: false,
    contact_phone: "",
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        company_id: null,
        full_name: "Nexus",
        is_active: true,
      };
    if (path === "/nexus/integrations")
      body = {
        version: 0,
        openwa_key_configured: true,
        resend_key_configured: false,
        email_from: "",
        openwa_base_url: "https://example.com",
      };
    if (path === "/nexus/integrations/companies") body = [company];
    if (path.endsWith("/automatic-session")) {
      expect(route.request().postDataJSON()).toEqual({
        phone: "+5547999999999",
        automatic: true,
        enabled: true,
      });
      saved++;
      company.discovery = {
        phone: "+5547999999999",
        automatic: true,
        status: "waiting",
        send_enabled: true,
        attempts: 0,
      };
      body = {};
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await page
    .getByLabel("WhatsApp de envio de Empresa", { exact: true })
    .fill("+5547999999999");
  await page.getByLabel("WhatsApp de envio de Empresa", { exact: true }).blur();
  await expect.poll(() => saved).toBe(1);
  await expect(page.getByText(/Nova consulta a cada minuto/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Salvar sessão de Empresa" }),
  ).toHaveCount(0);
});

test("Nexus configures credentials and binds each company without exposing saved keys", async ({
  page,
}) => {
  let version = 0;
  const submissions: any[] = [];
  const sessionId = "11111111-1111-4111-8111-111111111111";
  let company = {
    id: "company",
    trade_name: "Agência A",
    slug: "agencia-a",
    is_active: true,
    session_id: null as string | null,
    enabled: false,
    discovery: {
      automatic: false,
      phone: "",
      status: "waiting",
      attempts: 0,
      send_enabled: false,
    },
  };
  const config = () => ({
    version,
    openwa_base_url: "https://openwa.187-77-58-10.sslip.io/api",
    openwa_key_configured: version > 0,
    resend_key_configured: version > 0,
    email_from: version ? "acesso@example.com" : "",
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      };
    else if (path === "/nexus/integrations") {
      if (request.method() === "PUT") {
        submissions.push(request.postDataJSON());
        version++;
      }
      body = config();
    } else if (path === "/nexus/integrations/companies") body = [company];
    else if (path === "/nexus/integrations/sessions")
      body = [{ id: sessionId, name: "Agência A", status: "READY" }];
    else if (path === "/nexus/integrations/companies/company") {
      submissions.push(request.postDataJSON());
      company = { ...company, ...request.postDataJSON() };
      body = company;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Consultar sessões OpenWA" }),
  ).toBeDisabled();
  await page
    .getByLabel("API_KEY do OpenWA", { exact: true })
    .fill("owa_placeholder_secret");
  await page
    .getByLabel("API_KEY do Resend", { exact: true })
    .fill("re_placeholder_secret");
  await page
    .getByLabel("E-mail remetente do Resend")
    .fill("acesso@example.com");
  await page
    .getByRole("button", { name: "Salvar configurações", exact: true })
    .click();
  await expect(
    page.getByText("Configuração salva.", { exact: true }),
  ).toBeVisible();
  expect(submissions[0].expected_version).toBe(0);
  await expect(
    page.getByLabel("API_KEY do OpenWA", { exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByLabel("API_KEY do Resend", { exact: true }),
  ).toHaveValue("");
  await page
    .getByRole("button", { name: "Salvar configurações", exact: true })
    .click();
  await expect.poll(() => submissions.length).toBe(2);
  expect(submissions[1].openwa_api_key).toBeUndefined();
  await page.getByRole("button", { name: "Consultar sessões OpenWA" }).click();
  await page
    .getByRole("combobox", { name: "Sessão OpenWA de Agência A", exact: true })
    .selectOption(sessionId);
  await page
    .getByLabel("Habilitar envios para Agência A", { exact: true })
    .check();
  await page
    .getByRole("button", { name: "Salvar sessão de Agência A", exact: true })
    .click();
  await expect(page.getByText("Sessão da empresa salva.")).toBeVisible();
  expect(submissions[2]).toEqual({ session_id: sessionId, enabled: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("company users do not see Nexus integration settings", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: any = [];
    if (path.endsWith("/auth/me"))
      body = {
        id: "admin",
        role: "admin",
        company_id: "company",
        full_name: "Admin",
        is_active: true,
      };
    if (path.endsWith("/company"))
      body = {
        id: "company",
        trade_name: "Agência",
        slug: "agencia",
        is_active: true,
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Configurações", exact: true }),
  ).toHaveCount(0);
});

test("phone discovery fills the ID but requires explicit save", async ({
  page,
}) => {
  const id = "11111111-1111-4111-8111-111111111111";
  let saved = 0;
  let failed = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [],
      status = 200;
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        company_id: null,
        full_name: "Nexus",
        is_active: true,
      };
    else if (path === "/nexus/integrations")
      body = {
        version: 0,
        openwa_key_configured: true,
        resend_key_configured: false,
        email_from: "",
        openwa_base_url: "https://example.com",
      };
    else if (path === "/nexus/integrations/companies")
      body = [
        {
          id: "company",
          trade_name: "Agência A",
          slug: "agencia",
          is_active: true,
          session_id: null,
          enabled: false,
          discovery: {
            automatic: false,
            phone: "",
            status: "waiting",
            attempts: 0,
            send_enabled: false,
          },
          contact_phone: "+5547999999999",
        },
      ];
    else if (path.endsWith("/find-session")) {
      expect(route.request().postDataJSON()).toEqual({
        phone: "+5547999999999",
      });
      if (failed) {
        status = 409;
        body = { detail: "Esta sessão já está associada a outra empresa." };
      } else
        body = {
          id,
          name: "Número da agência",
          phone: "+5547999999999",
          status: "CONNECTED",
        };
    } else if (path === "/nexus/integrations/companies/company") {
      saved++;
      body = {};
    }
    await route.fulfill({ status, json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await expect(
    page.getByLabel("WhatsApp de envio de Agência A", { exact: true }),
  ).toHaveValue("+5547999999999");
  await page
    .getByRole("button", {
      name: "Buscar sessão pelo telefone de Agência A",
      exact: true,
    })
    .click();
  await expect(
    page.getByLabel("ID da sessão de Agência A", { exact: true }),
  ).toHaveValue(id);
  await expect(page.getByRole("status")).toContainText("Sessão encontrada");
  expect(saved).toBe(0);
  await expect(
    page.getByLabel("Habilitar envios para Agência A", { exact: true }),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "Salvar sessão de Agência A", exact: true })
    .click();
  await expect.poll(() => saved).toBe(1);
  failed = true;
  await page
    .getByRole("button", {
      name: "Buscar sessão pelo telefone de Agência A",
      exact: true,
    })
    .click();
  await expect(page.getByRole("alert")).toContainText("outra empresa");
  expect(saved).toBe(1);
});
