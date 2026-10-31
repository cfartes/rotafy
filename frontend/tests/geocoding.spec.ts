import { test, expect } from "@playwright/test";

test("full superadmin saves a server key without reading it back", async ({ page }) => {
  let config = { enabled: false, monthly_limit: 9000, used: 12, key_configured: false, version: 0 };
  let submission: any;
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "nexus", role: "nexus", company_id: null, full_name: "Nexus", is_active: true };
    if (path === "/nexus/integrations") body = { version: 0, whatsapp_queue_interval_seconds: 30, openwa_base_url: "", email_from: "" };
    if (path === "/nexus/geocoding") {
      if (route.request().method() === "PUT") {
        submission = route.request().postDataJSON();
        config = { ...config, enabled: true, key_configured: true, version: 1 };
      }
      body = config;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByLabel("Ativar localização automática", { exact: true }).check();
  await page.getByLabel("Chave Google Geocoding do backend", { exact: true }).fill("sample_test_key");
  await page.getByRole("button", { name: "Salvar localização automática", exact: true }).click();
  await expect(page.getByText("Chave cadastrada. Deixe vazio para mantê-la.", { exact: true })).toBeVisible();
  expect(submission).toEqual({ expected_version: 0, enabled: true, monthly_limit: 9000, api_key: "sample_test_key", clear_key: false });
  await expect(page.getByLabel("Chave Google Geocoding do backend", { exact: true })).toHaveValue("");
});

test("automatic boarding location uses Google link and does not prefill the OSM map", async ({ page }) => {
  await page.route("https://tile.openstreetmap.org/**", route => route.abort());
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", company_id: "company", full_name: "Admin", is_active: true };
    if (path === "/company") body = { id: "company", slug: "empresa", trade_name: "Empresa", operational_profile: "tourism" };
    if (path === "/tracking/settings") body = { enabled: true, proximity_enabled: true, departure_enabled: true, radius_m: 5000 };
    if (path === "/trips") body = [{ id: "trip", name: "Praia", status: "scheduled" }];
    if (path === "/tracking/boardings") body = [{ reservation_id: "reservation", leg_id: "leg", contact_name: "Maria", boarding_name: "Hotel", boarding_address: "Rua do Hotel, 100", source_hash: "a".repeat(64), coordinates_valid: true, coordinate_source: "google", latitude: -26.9, longitude: -49.0, starts_at: "2027-01-01T12:00:00Z" }];
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Rastreamento", exact: true }).click();
  await page.getByRole("combobox", { name: "Viagem", exact: true }).selectOption("trip");
  await expect(page.getByText(/Localizado automaticamente pelo Google Maps/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Ver no Google Maps", exact: true })).toHaveAttribute("href", "https://www.google.com/maps/search/?api=1&query=-26.9,-49");
  await page.getByRole("button", { name: "Corrigir local manualmente", exact: true }).click();
  await expect(page.getByRole("dialog").getByText(/Ponto selecionado:/)).toHaveCount(0);
});
