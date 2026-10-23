import { test, expect } from "@playwright/test";

for (const path of ["/", "/nexus"]) {
  test(`login compacto e aviso expansível: ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.route("**/api/v1/auth/me", route => route.fulfill({ status: 401, json: {} }));
    await page.goto(path);
    await expect(page.locator("#login-privacy .legal-footer")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    await page.getByLabel("E-mail", { exact: true }).fill("pessoa@example.com");
    await page.getByRole("button", { name: "Mostrar informações sobre o uso dos dados" }).click();
    await expect(page.getByText("Finalidade:")).toBeVisible();
    await page.getByRole("button", { name: "Ocultar informações sobre o uso dos dados" }).click();
    await expect(page.getByLabel("E-mail", { exact: true })).toHaveValue("pessoa@example.com");
    const links = page.locator(".legal-footer a");
    for (const link of await links.all()) await expect(link).toHaveAttribute("target", "_blank");
    await page.getByRole("button", { name: "Usar somente necessários", exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    await page.screenshot({ path: `test-results/login-${path === "/" ? "company" : "nexus"}.png` });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("políticas compactas abrem a seção solicitada", async ({ page }) => {
  await page.goto("/privacidade#cookies");
  await expect(page.locator("details#cookies")).toHaveAttribute("open", "");
  await expect(page.locator("details#dados")).not.toHaveAttribute("open");
  await page.locator("details#dados summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("details#dados")).toHaveAttribute("open", "");
});
