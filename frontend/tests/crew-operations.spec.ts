import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("admin changes the departure gate and compares an immutable route in an isolated map", async ({ page }) => {
  let policy = { early_start_enabled: true, early_start_minutes: 30 }, mapLoads = 0;
  await page.route("https://**", route => route.abort());
  // Opaque frames cannot access loopback resources; model the public HTTPS deployment.
  await page.route("https://rotafy.test/**", async route => {
    const response = await route.fetch({ url: route.request().url().replace("https://rotafy.test", process.env.E2E_BASE_URL || "http://localhost:5178") });
    await route.fulfill({ response });
  });
  await page.route("https://maps.googleapis.com/maps/api/js?**", async route => {
    mapLoads++;
    await route.fulfill({ contentType: "application/javascript", body: `
      try { parent.document.body; document.body.dataset.parentAccess='allowed'; } catch { document.body.dataset.parentAccess='blocked'; }
      window.google={maps:{Map:class{fitBounds(){} getZoom(){return 14} setZoom(){}},
        LatLngBounds:class{extend(){} isEmpty(){return false}},Polyline:class{},Marker:class{},SymbolPath:{CIRCLE:0},
        Geocoder:class{async geocode(){return {results:[{geometry:{location_type:"ROOFTOP",location:{lat:()=>-26.9,lng:()=>-49.0}}}]}}},
        event:{addListenerOnce(m,n,f){f()}}}}; window.routeMapReady();
    ` });
  });
  const nginx = readFileSync("nginx.conf", "utf8");
  const framePolicy = nginx.match(/location = \/route-comparison-map\.html \{[\s\S]*?Content-Security-Policy "([^"]+)"/)![1];
  await page.route("**/route-comparison-map.html", route => route.fulfill({ body: readFileSync("public/route-comparison-map.html", "utf8"), headers: { "Content-Type": "text/html", "Content-Security-Policy": framePolicy, "Referrer-Policy": "origin" } }));
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me") data = { id: "admin", role: "admin", full_name: "Admin", company_id: "company", is_active: true };
    if (path === "/company") data = { id: "company", slug: "empresa", trade_name: "Empresa", operational_profile: "tourism" };
    if (path === "/company/operation-settings") { if (route.request().method() === "PUT") policy = route.request().postDataJSON(); data = policy; }
    if (path === "/trips") data = [{ id: "trip", name: "Viagem finalizada", status: "completed" }];
    if (path === "/tracking/settings") data = { enabled: true, proximity_enabled: true, departure_enabled: false, radius_m: 5000 };
    if (path === "/tracking/routes") data = [{ allocation_id: "vehicle", leg_id: "leg", vehicle_name: "Ônibus", plate: "ABC1D23", position: 1, origin: "Centro", destination: "Praia" }];
    if (path === "/tracking/routes/map") data = { browser_key: "test_web_maps_key" };
    if (path === "/tracking/routes/vehicle/leg") data = {
      created_at: "2026-11-02T12:00:00Z", sample_limit: 10000,
      planned_points: [{ name: "Hotel do roteiro original", address: "Rua A, 10", query: "Rua A, 10, Blumenau", kind: "boarding", position: 0, scheduled_at: null }, { name: "Praia", address: "Rua B, 20", query: "Rua B, 20, Blumenau", position: 1, scheduled_at: "2026-11-02T14:00:00Z" }],
      positions: [{ latitude: -26.9, longitude: -49, accuracy_m: 10, captured_at: "2026-11-02T12:01:00Z" }, { latitude: -26.91, longitude: -49.01, accuracy_m: 10, captured_at: "2026-11-02T12:02:00Z" }],
      events: [{ recorded_at: "2026-11-02T12:01:00Z", action: "board", passengers: 2 }]
    };
    await route.fulfill({ json: data });
  });
  await page.goto("https://rotafy.test/");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByLabel("Antecedência máxima para iniciar (minutos)").fill("");
  await page.getByLabel("Iniciar viagem antecipada", { exact: true }).uncheck();
  await expect(page.getByLabel("Antecedência máxima para iniciar (minutos)")).toBeDisabled();
  await page.getByRole("button", { name: "Salvar regra de início" }).click();
  await expect.poll(() => policy.early_start_enabled).toBe(false);
  expect(policy.early_start_minutes).toBe(30);
  await page.getByLabel("Iniciar viagem antecipada", { exact: true }).check();
  await page.getByLabel("Antecedência máxima para iniciar (minutos)").fill("90");
  await page.getByRole("button", { name: "Salvar regra de início" }).click();
  await expect.poll(() => policy.early_start_minutes).toBe(90);
  await page.getByRole("button", { name: "Rastreamento", exact: true }).click();
  await page.getByLabel("Viagem para comparar").selectOption("trip");
  await page.getByLabel("Veículo e trecho").selectOption("vehicle/leg");
  await expect(page.getByText("Hotel do roteiro original", { exact: true })).toBeVisible();
  expect(mapLoads).toBe(0);
  await page.getByRole("button", { name: "Carregar comparação no Google Maps" }).click();
  const map = page.frameLocator('iframe[title="Mapa da rota planejada e do percurso GPS"]');
  await expect(map.locator("#status")).toContainText("2/2 pontos planejados localizados");
  await expect(map.locator("body")).toHaveAttribute("data-parent-access", "blocked");
  expect(mapLoads).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("heading", { name: "Rota planejada × percurso realizado" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "../artifacts/crew-operations-mobile.png" });
});
