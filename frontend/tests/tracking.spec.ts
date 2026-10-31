import { test, expect } from "@playwright/test";

test("admin enables tracking and confirms the boarding location before proximity alerts", async ({ page }) => {
  let settings: any = { enabled: false, proximity_enabled: true, departure_enabled: false, radius_m: 5000, company_id: "company", updated_at: "2026-01-01T00:00:00Z" };
  let savedPoint: any;
  await page.route("https://tile.openstreetmap.org/**", route => route.abort());
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: any = [];
    if (path === "/auth/me") data = { id: "admin", role: "admin", company_id: "company", full_name: "Admin", is_active: true };
    if (path === "/company") data = { id: "company", slug: "empresa", trade_name: "Empresa A", operational_profile: "tourism" };
    if (path === "/tracking/settings") { if (route.request().method() === "PUT") { const payload = route.request().postDataJSON(); expect(Object.keys(payload).sort()).toEqual(["departure_enabled", "enabled", "proximity_enabled", "radius_m"]); settings = payload; } data = settings; }
    if (path === "/trips") data = [{ id: "trip", name: "Praia", status: "in_progress" }];
    if (path === "/tracking/vehicles") data = [{ id: "session", trip_id: "trip", trip_name: "Praia", vehicle_name: "Ônibus", plate: "ABC1D23", responsible: "Motorista", origin: "Maceió", destination: "Praia", captured_at: "2020-01-01T12:00:00Z", accuracy_m: 10 }];
    if (path === "/tracking/sessions/session/history") data = [{ latitude: -9.6, longitude: -35.7, captured_at: "2020-01-01T12:00:00Z" }];
    if (path === "/tracking/boardings") data = [{ reservation_id: "reservation", leg_id: "leg", contact_name: "Responsável", boarding_name: "Hotel", boarding_address: "Rua do Hotel", source_hash: "a".repeat(64), coordinates_valid: false, starts_at: "2027-01-01T12:00:00Z" }];
    if (path === "/tracking/boardings/reservation/leg") { savedPoint = route.request().postDataJSON(); data = { confirmed: true }; }
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Rastreamento", exact: true }).click();
  await page.getByLabel("Permitir rastreamento dos veículos durante as viagens").check();
  await page.getByLabel("Lembrar a saída de cada trecho", { exact: false }).check();
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect.poll(()=>settings.enabled && settings.departure_enabled).toBe(true);
  await expect(page.getByText(/Localização desatualizada/)).toBeVisible();
  await page.getByRole("button", { name: "Acompanhar no mapa" }).click();
  await expect(page.getByLabel("Mapa das posições coletadas")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar ponto no mapa" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Link do Google Maps com coordenadas ou latitude, longitude").fill("https://www.google.com/maps?q=-9.6,-35.7");
  await dialog.getByRole("button", { name: "Confirmar este ponto de embarque" }).click();
  await expect.poll(()=>savedPoint?.latitude).toBe(-9.6);
  expect(savedPoint.longitude).toBe(-35.7);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
