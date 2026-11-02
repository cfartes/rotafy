import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("fleet map fills the workspace and preserves the viewport when GPS updates", async ({ page }) => {
  let latitude = -9.6;
  await page.route("https://tile.openstreetmap.org/**", route => route.abort());
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me") data = { id: "admin", role: "admin", company_id: "company", full_name: "Admin", is_active: true, enabled_modules: ["tracking", "trips"] };
    if (path === "/company") data = { id: "company", slug: "empresa", trade_name: "Empresa" };
    if (path === "/tracking/vehicles") data = [
      { id: "session", vehicle_name: "Ônibus 1", plate: "ABC1D23", trip_name: "Praia", origin: "Centro", destination: "Praia", captured_at: new Date().toISOString(), latitude, longitude: -35.7, accuracy_m: 10 },
      { id: "waiting", vehicle_name: "Ônibus 2", plate: "DEF4G56", trip_name: "Praia", captured_at: null, latitude: null, longitude: null }
    ];
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Mapa da frota", exact: true }).click();
  const map = page.getByLabel("Mapa de veículos em viagem", { exact: true });
  await expect(map).toBeVisible();
  await expect(page.getByText("1 veículo(s) no mapa · 1 aguardando GPS")).toBeVisible();
  const rectangle = await map.boundingBox();
  expect(rectangle!.height).toBeGreaterThan(500);
  expect(Math.round(rectangle!.y)).toBe(80);
  await map.focus();
  const proxy = map.locator(".leaflet-proxy");
  const initial = await proxy.getAttribute("style");
  await map.press("ArrowRight");
  await expect.poll(() => proxy.getAttribute("style")).not.toBe(initial);
  const panned = await proxy.getAttribute("style");
  latitude = -9.7;
  await page.getByRole("button", { name: "Atualizar agora" }).click();
  await expect(page.getByRole("button", { name: "Atualizar agora" })).toBeEnabled();
  expect(await proxy.getAttribute("style")).toBe(panned);
  if (await page.getByRole("button", { name: "Tela cheia", exact: true }).count()) {
    await page.getByRole("button", { name: "Tela cheia", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sair da tela cheia" })).toBeVisible();
    await page.getByRole("button", { name: "Sair da tela cheia" }).click();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(async () => Math.round((await map.boundingBox())!.height)).toBe(776);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1)).toBe(true);
  await expect.poll(async () => Math.round((await map.boundingBox())!.y)).toBe(68);
  await page.getByRole("button", { name: "Usar somente necessários", exact: true }).click();
  await page.getByRole("button", { name: "Centralizar", exact: true }).click();
  const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({ path: "../artifacts/fleet-map-mobile.png", animations: "disabled" });
});
