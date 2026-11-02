import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("histórico compacto identifica usuário, ação e registro sem executar HTML", async ({ page }) => {
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: unknown = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", full_name: "Administrador", company_id: "company", is_active: true, enabled_modules: [] };
    if (path === "/company") body = { id: "company", slug: "empresa", trade_name: "Empresa", is_active: true };
    if (path === "/audit") body = [
      { id: "12345678-evento", created_at: "2026-11-02T17:50:35Z", actor_id: "usuario-123", actor_name: "Claudio Fartes", actor_role: "admin", action: "route.created", target_id: "rota-456", target_name: "Blumenau → Balneário Camboriú" },
      { id: "segundo", created_at: "2026-11-02T16:00:00Z", actor_id: null, actor_name: null, action: "trip.created", target_id: "viagem-789", target_name: '<img src=x onerror="window.injected=true">' },
    ];
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page.getByRole("button", { name: "Usar somente necessários", exact: true }).click();
  await page.getByRole("button", { name: "Atividades", exact: true }).click();
  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader", { name: "Usuário", exact: true })).toBeVisible();
  await expect(table.getByText("Claudio Fartes")).toBeVisible();
  await expect(table.getByText("Rota cadastrada")).toBeVisible();
  await expect(table.getByText("14:50:35", { exact: false })).toBeVisible();
  await expect(table.getByText("Sistema / automação")).toBeVisible();
  expect(await table.locator("tbody tr").first().evaluate(element => element.getBoundingClientRect().height)).toBeLessThan(80);
  await page.screenshot({ path: "test-results/activity-desktop-compact.png" });
  await table.locator("summary").first().focus();
  await page.keyboard.press("Enter");
  await expect(table.getByText("usuario-123", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { injected?: boolean }).injected)).toBeUndefined();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "test-results/activity-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/activity-mobile.png" });
});
