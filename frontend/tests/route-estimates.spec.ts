import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function setup(page: Page, available = true, waitFirst = false) {
  const requests: Record<string, any>[] = [],
    saved: Record<string, any>[] = [],
    routes: Record<string, any>[] = [];
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me")
      data = {
        id: "admin",
        role: "admin",
        full_name: "Operador",
        company_id: "company",
        is_active: true,
        enabled_modules: ["routes", "trips"],
      };
    if (path === "/company")
      data = { id: "company", trade_name: "Empresa Teste", slug: "teste" };
    if (path === "/locations/states")
      data = [{ uf: "SC", name: "Santa Catarina" }];
    if (path === "/locations/cities/SC")
      data = [
        { id: 4202404, name: "Blumenau", uf: "SC" },
        { id: 4211306, name: "Navegantes", uf: "SC" },
      ];
    if (path === "/routes/estimate-availability")
      data = {
        available,
        message: "Cálculo não habilitado. Informe o tempo manualmente.",
      };
    if (path === "/routes/estimate") {
      const payload = route.request().postDataJSON();
      requests.push(payload);
      if (waitFirst && requests.length === 1) await gate;
      data = {
        distance_m: payload.origin_city_id === 4202404 ? 32100 : 35500,
        duration_minutes: payload.origin_city_id === 4202404 ? 46 : 61,
        source: "Google Maps",
      };
    }
    if (path === "/routes" && route.request().method() === "POST") {
      const payload = route.request().postDataJSON();
      saved.push(payload);
      routes.push({ ...payload, id: "route", version: 1 });
      await route.fulfill({ status: 201, json: routes[0] });
      return;
    }
    if (path === "/routes") data = routes;
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Usar somente necessários", exact: true })
    .click();
  await page.getByRole("button", { name: "Rotas", exact: true }).click();
  await page.getByRole("button", { name: "Nova Rota", exact: true }).click();
  return { requests, saved, release };
}

async function fill(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Nova Rota", exact: true });
  await dialog
    .getByLabel("Nome da Rota", { exact: true })
    .fill("Rota automática");
  await dialog
    .getByLabel("UF de origem da ida", { exact: true })
    .selectOption("SC");
  await dialog
    .getByLabel("Cidade de origem da ida", { exact: true })
    .selectOption("4202404");
  await dialog
    .getByLabel("UF de destino da ida", { exact: true })
    .selectOption("SC");
  await dialog
    .getByLabel("Cidade de destino da ida", { exact: true })
    .selectOption("4211306");
  const leg = dialog.locator("fieldset").first();
  await leg
    .getByLabel("Tempo adicional total nas paradas (minutos)", { exact: true })
    .fill("10");
  await leg
    .getByLabel("Endereço de saída", { exact: true })
    .fill("Rua Sete de Setembro, 100");
  await leg
    .getByRole("button", { name: "Adicionar parada", exact: true })
    .click();
  await leg.getByLabel("Parada 1", { exact: true }).fill("Hotel Centro");
  await leg
    .getByLabel("Endereço da parada 1", { exact: true })
    .fill("Rua do Hotel, 50, Blumenau SC");
  await leg
    .getByLabel("Endereço de chegada", { exact: true })
    .fill("Aeroporto, 200");
  return { dialog, leg };
}

test("calcula automaticamente ida e volta, soma paradas e salva somente o plano operacional", async ({
  page,
}) => {
  const state = await setup(page);
  const { dialog, leg } = await fill(page);
  await expect(
    leg.getByLabel("Deslocamento estimado (minutos)", { exact: true }),
  ).toHaveValue("46");
  await expect(leg.getByText("32,10 km", { exact: true })).toBeVisible();
  await expect(leg.getByText("56 min", { exact: true })).toBeVisible();
  expect(state.requests[0].stop_addresses).toEqual([
    "Rua do Hotel, 50, Blumenau SC",
  ]);
  expect(Object.keys(state.requests[0]).sort()).toEqual([
    "destination_address",
    "destination_city_id",
    "origin_address",
    "origin_city_id",
    "stop_addresses",
  ]);
  await dialog
    .getByRole("combobox", { name: "Sentidos", exact: true })
    .selectOption("round_trip");
  await dialog
    .getByRole("button", { name: "Gerar volta invertendo a ida", exact: true })
    .click();
  const back = dialog.locator("fieldset").nth(1);
  await expect(
    back.getByLabel("Deslocamento estimado (minutos)", { exact: true }),
  ).toHaveValue("61");
  await expect(back.getByText("35,50 km", { exact: true })).toBeVisible();
  await expect(back.getByText("71 min", { exact: true })).toBeVisible();
  expect(state.requests).toHaveLength(2);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await leg.getByRole("region", { name: "Previsão da ida", exact: true }).screenshot({ path: "../artifacts/route-estimate-panel.png", animations: "disabled" });
  await page.screenshot({
    path: "../artifacts/route-estimate-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../artifacts/route-estimate-mobile.png",
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "Salvar Rota", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(state.saved[0].legs.map((l: any) => l.duration_minutes)).toEqual([
    46, 61,
  ]);
  expect(JSON.stringify(state.saved)).not.toContain("distance_m");
  await page
    .getByRole("button", { name: "Consultar distância e tempo", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "Previsão da rota · Rota automática",
    exact: true,
  });
  await expect(preview.getByText("32,10 km", { exact: true })).toBeVisible();
  await expect(
    preview.getByRole("button", { name: "Usar tempo calculado", exact: true }),
  ).toHaveCount(0);
});

test("preserva ajustes manuais durante resposta pendente e ao recalcular", async ({
  page,
}) => {
  const state = await setup(page, true, true);
  const { dialog, leg } = await fill(page);
  await expect.poll(() => state.requests.length).toBe(1);
  await expect(
    dialog.getByRole("button", { name: "Salvar Rota", exact: true }),
  ).toBeDisabled();
  const duration = leg.getByLabel("Deslocamento estimado (minutos)", {
    exact: true,
  });
  await duration.fill("80");
  await expect(
    dialog.getByRole("button", { name: "Salvar Rota", exact: true }),
  ).toBeEnabled();
  state.release();
  await expect(leg.getByText("32,10 km", { exact: true })).toBeVisible();
  await expect(duration).toHaveValue("80");
  await leg
    .getByRole("button", { name: "Recalcular percurso", exact: true })
    .click();
  await expect.poll(() => state.requests.length).toBe(2);
  await expect(
    leg.getByText("Seu tempo manual foi preservado.", { exact: false }),
  ).toBeVisible();
  await expect(duration).toHaveValue("80");
  await leg
    .getByRole("button", { name: "Usar tempo calculado", exact: true })
    .click();
  await expect(duration).toHaveValue("46");
  await leg
    .getByLabel("Tempo adicional total nas paradas (minutos)", { exact: true })
    .fill("20");
  await expect(leg.getByText("66 min", { exact: true })).toBeVisible();
  expect(state.requests).toHaveLength(2);
});

test("resposta antiga não altera duração após mudar o percurso", async ({
  page,
}) => {
  const state = await setup(page, true, true);
  const { leg } = await fill(page);
  await expect.poll(() => state.requests.length).toBe(1);
  await leg
    .getByLabel("Cidade de origem da ida", { exact: true })
    .selectOption("4211306");
  await expect(leg.getByText("32,10 km", { exact: true })).toHaveCount(0);
  await expect(
    leg.getByLabel("Deslocamento estimado (minutos)", { exact: true }),
  ).toHaveValue("61");
  state.release();
  await expect(leg.getByText("35,50 km", { exact: true })).toBeVisible();
  await expect(
    leg.getByLabel("Deslocamento estimado (minutos)", { exact: true }),
  ).toHaveValue("61");
});

test("sem serviço automático o cadastro manual permanece disponível", async ({
  page,
}) => {
  const state = await setup(page, false);
  const { dialog, leg } = await fill(page);
  await leg
    .getByLabel("Deslocamento estimado (minutos)", { exact: true })
    .fill("70");
  await expect(
    leg.getByText("Cálculo não habilitado.", { exact: false }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Salvar Rota", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(state.requests).toHaveLength(0);
  expect(state.saved[0].legs[0].duration_minutes).toBe(70);
});

test("falha do provedor libera o salvamento com duração manual", async ({
  page,
}) => {
  const state = await setup(page);
  await page.route("**/api/v1/routes/estimate", (route) =>
    route.fulfill({
      status: 503,
      json: {
        detail: "Não foi possível calcular. Informe o tempo manualmente.",
      },
    }),
  );
  const { dialog, leg } = await fill(page);
  await expect(leg.getByRole("alert")).toContainText(
    "Informe o tempo manualmente",
  );
  await leg
    .getByLabel("Deslocamento estimado (minutos)", { exact: true })
    .fill("75");
  await dialog
    .getByRole("button", { name: "Salvar Rota", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(state.saved[0].legs[0].duration_minutes).toBe(75);
});
