import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const url of ["/", "/ajuda", "/privacidade", "/termos", "/cancelamento-reembolso", "/privacidade/solicitacao"]) {
  test(`acessibilidade WCAG nas páginas públicas: ${url}`, async ({ page }) => {
    await page.route("**/api/v1/auth/me", route => route.fulfill({ status: 401, json: {} }));
    await page.goto(url);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    expect(result.violations).toEqual([]);
  });
}

test("cookies necessários persistem sem rastreadores e preferências funcionam por teclado", async ({ page }) => {
  const external: string[] = [];
  page.on("request", request => { if (/google-analytics|googletagmanager|facebook.net|hotjar|clarity.ms/.test(request.url())) external.push(request.url()); });
  await page.goto("/privacidade");
  await page.getByRole("button", { name: "Gerenciar cookies", exact: true }).focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Preferências de cookies" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("checkbox")).toBeChecked();
  await expect(dialog.getByRole("checkbox")).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Usar somente necessários", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("complementary", { name: "Informações sobre cookies" })).toHaveCount(0);
  await page.getByRole("button", { name: "Preferências de cookies", exact: true }).click();
  await expect(dialog).toBeVisible();
  expect(external).toEqual([]);
});

test("solicitação LGPD envia somente os dados mínimos e mostra protocolo", async ({ page }) => {
  await page.route("**/api/v1/public/privacy-requests", async route => {
    expect(route.request().postDataJSON()).toEqual({ email: "pessoa@example.com", kind: "deletion", details: "Excluir dados da minha conta" });
    await route.fulfill({ status: 202, json: { protocol: "protocolo-teste", message: "Solicitação registrada para verificação." } });
  });
  await page.goto("/privacidade/solicitacao");
  await page.getByLabel("E-mail para retorno").fill("pessoa@example.com");
  await page.getByLabel("Tipo de solicitação").selectOption("deletion");
  await page.getByLabel("Como podemos ajudar? (opcional)").fill("Excluir dados da minha conta");
  await page.getByRole("button", { name: "Registrar solicitação de privacidade" }).click();
  await expect(page.getByRole("status")).toContainText("protocolo-teste");
});

test("admin navega por teclado e configura horários em tela acessível", async ({ page }) => {
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: unknown = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", full_name: "Admin", company_id: "company", is_active: true, enabled_modules: ["whatsapp"] };
    if (path === "/company") body = { id: "company", slug: "empresa", trade_name: "Empresa", is_active: true };
    if (path === "/company/whatsapp/hours") body = { enabled: true, timezone: "America/Sao_Paulo", intervals: [{ day: 0, start: "09:00", end: "18:00" }] };
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page.getByRole("button", { name: "Configurações", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Horários de atendimento humano" })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("campos livres são exibidos como texto, sem executar HTML no painel de privacidade", async ({ page }) => {
  const payload = '<img src=x onerror="window.privacyXss=true">';
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: unknown = [];
    if (path === "/auth/me") body = { id: "nexus", role: "nexus", full_name: "Nexus", company_id: null, is_active: true };
    if (path === "/nexus/integrations") body = { version: 0, email_from: "", whatsapp_queue_interval_seconds: 30 };
    if (path === "/nexus/privacy-requests") body = [{ id: "request", email: "pessoa@example.com", kind: "deletion", details: payload, status: "received", created_at: "2026-10-23T10:00:00Z" }];
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByText(payload, { exact: true })).toBeVisible();
  await expect(page.locator(".privacy-request img")).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { privacyXss?: boolean }).privacyXss)).toBeUndefined();
});
