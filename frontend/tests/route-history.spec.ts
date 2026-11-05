import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function setup(page: Page, moduleEnabled = true, large = false) {
  const point = (id: number, session: string, captured: string) => ({
    id: String(id),
    session_id: session,
    captured_at: captured,
    received_at: captured,
    latitude: -26.9 - id * 0.001,
    longitude: -49.06 - id * 0.001,
    accuracy_m: id === 3 ? 150 : 10,
  });
  let points = [
    point(1, "first", "2026-11-03T13:00:00Z"),
    point(2, "first", "2026-11-03T13:01:00Z"),
    point(3, "first", "2026-11-03T13:20:00Z"),
    point(4, "second", "2026-11-03T13:21:00Z"),
    point(5, "second", "2026-11-03T13:22:00Z"),
  ];
  if (large)
    points = Array.from({ length: 10000 }, (_, index) =>
      point(
        index + 1,
        "single",
        new Date(
          Date.parse("2026-11-03T13:22:00Z") - (9999 - index) * 60000,
        ).toISOString(),
      ),
    );
  const journey = {
    allocation_id: "bus",
    leg_id: "outbound",
    vehicle_id: "vehicle",
    vehicle_name: "Ônibus 01",
    plate: "ABC1D23",
    origin: "Blumenau",
    destination: "Navegantes",
    position: 1,
    trip_name: "Praia",
    trip_status: "completed",
    session_count: new Set(points.map((p) => p.session_id)).size,
    position_count: points.length,
    tracking_started_at: points[0].captured_at,
    tracking_ended_at: points.at(-1)!.captured_at,
  };
  const back = {
    ...journey,
    leg_id: "return",
    origin: "Navegantes",
    destination: "Blumenau",
    position: 2,
    position_count: 0,
  };
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let data: unknown = [];
    if (path === "/auth/me")
      data = {
        id: "admin",
        full_name: "Administrador",
        role: "admin",
        company_id: "company",
        is_active: true,
        enabled_modules: moduleEnabled ? ["tracking", "trips"] : ["trips"],
      };
    if (path === "/company")
      data = { id: "company", slug: "empresa", trade_name: "Empresa" };
    if (path === "/tracking/history")
      data = {
        trips: [
          {
            id: "trip",
            name: "Praia",
            status: "completed",
            first_session_at: points[0].captured_at,
            last_position_at: points.at(-1)!.captured_at,
          },
        ],
        truncated: false,
        limit: 200,
        retention_days: 90,
      };
    if (path === "/tracking/history/trip") data = [journey, back];
    if (path === "/tracking/history/trip/distance") {
      const quality = {
        samples: points.length,
        valid_intervals: 2,
        gaps: 1,
        session_breaks: 1,
        rejected_accuracy: 1,
        rejected_jumps: 1,
        invalid_timestamps: 0,
        retention_limited: false,
        timing_unknown: false,
        partial: true,
        has_tracking: true,
      };
      data = {
        journeys: [
          { ...journey, ...quality, distance_m: 12345 },
          {
            ...back,
            ...quality,
            samples: 0,
            valid_intervals: 0,
            gaps: 0,
            session_breaks: 0,
            rejected_accuracy: 0,
            rejected_jumps: 0,
            distance_m: null,
          },
        ],
        distance_m: 12345,
        partial: true,
        trip_status: "completed",
        untracked_journeys: 0,
        retention_days: 90,
        gap_minutes: 10,
        max_accuracy_m: 100,
        max_speed_kmh: 160,
      };
    }
    if (path === "/tracking/history/trip/bus/outbound")
      data = {
        ...journey,
        positions: points,
        truncated: false,
        sample_limit: 10000,
        gap_minutes: 10,
        retention_days: 90,
      };
    if (path === "/tracking/history/trip/bus/return")
      data = {
        ...back,
        positions: [],
        truncated: false,
        sample_limit: 10000,
        gap_minutes: 10,
        retention_days: 90,
      };
    await route.fulfill({ json: data });
  });
  return { journey, back };
}

test("histórico reúne GPS encerrado, separa lacunas e limpa o mapa ao trocar de trecho", async ({
  page,
}) => {
  await setup(page);
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.setViewportSize({ width: 1366, height: 1000 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Usar somente necessários", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Histórico de trajetos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Viagem executada", exact: true })
    .selectOption("trip");
  await page
    .getByRole("combobox", { name: "Veículo e trecho registrado", exact: true })
    .selectOption("bus/outbound");
  const map = page.getByRole("region", {
    name: "Mapa do percurso registrado",
    exact: true,
  });
  await expect(map).toBeVisible();
  const mileage = page.getByRole("region", {
    name: "Quilometragem registrada",
    exact: true,
  });
  await expect(
    mileage.getByRole("heading", { name: "Quilometragem estimada pelo GPS" }),
  ).toBeVisible();
  await expect(mileage.locator("dl dd").nth(0)).toHaveText("12,35 km");
  await expect(mileage.locator("dl dd").nth(1)).toHaveText("12,35 km");
  await expect(mileage.locator("dl dd").nth(2)).toHaveText("Percurso parcial");
  await expect(
    mileage.getByText("1 salto(s) incompatível(is)", { exact: false }),
  ).toBeVisible();
  await expect(
    mileage.getByText("1 posição(ões) com precisão acima de 100", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    mileage
      .getByRole("table", { name: "Quilometragem por veículo" })
      .locator("tbody tr"),
  ).toHaveCount(1);
  await expect(page.getByText("3 segmento(s) de coleta")).toBeVisible();
  await expect(
    page.getByText("Há posições com precisão superior a 100 metros", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(map.locator("canvas")).toHaveCount(1);
  await expect(
    map.getByRole("img", { name: /^Primeira posição/ }),
  ).toBeVisible();
  await expect(map.getByRole("img", { name: /^Última posição/ })).toBeVisible();
  for (let i = 0; i < 3; i++)
    await page
      .getByRole("button", { name: "Centralizar percurso", exact: true })
      .click();
  await expect(map.locator("canvas")).toHaveCount(1);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  expect(
    requests.some((url) => /tracking\/vehicles|maps\.googleapis/.test(url)),
  ).toBe(false);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: "../artifacts/route-history-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../artifacts/route-history-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("combobox", { name: "Veículo e trecho registrado", exact: true })
    .selectOption("bus/return");
  await expect(
    page.getByText("Nenhuma posição GPS disponível", { exact: false }),
  ).toBeVisible();
  await expect(map).toHaveCount(0);
  await expect(mileage.locator("dl dd").nth(0)).toHaveText("12,35 km");
  await expect(mileage.locator("dl dd").nth(1)).toHaveText("Não calculável");
  await page
    .getByRole("combobox", { name: "Viagem executada", exact: true })
    .selectOption("");
  await expect(mileage).toHaveCount(0);
});

test("menu depende do módulo de rastreamento", async ({ page }) => {
  await setup(page, false);
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Histórico de trajetos", exact: true }),
  ).toHaveCount(0);
});

test("dez mil amostras usam canvas e mantêm somente os marcadores extremos", async ({
  page,
}) => {
  await setup(page, true, true);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Histórico de trajetos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Viagem executada", exact: true })
    .selectOption("trip");
  await page
    .getByRole("combobox", { name: "Veículo e trecho registrado", exact: true })
    .selectOption("bus/outbound");
  await expect(page.getByText("10.000", { exact: true })).toBeVisible();
  const map = page.getByRole("region", {
    name: "Mapa do percurso registrado",
    exact: true,
  });
  await expect(map.locator("canvas")).toHaveCount(1);
  await expect(map.locator("path[role=img]")).toHaveCount(2);
  await expect(page.getByText("1 segmento(s) de coleta")).toBeVisible();
});

test("quilometragem zero é diferente de dados insuficientes", async ({
  page,
}) => {
  const { journey, back } = await setup(page);
  const quality = {
    samples: 2,
    valid_intervals: 1,
    gaps: 0,
    session_breaks: 0,
    rejected_accuracy: 0,
    rejected_jumps: 0,
    invalid_timestamps: 0,
    retention_limited: false,
    timing_unknown: false,
    partial: false,
    has_tracking: true,
    distance_m: 0,
  };
  await page.route("**/api/v1/tracking/history/trip/distance", (route) =>
    route.fulfill({
      json: {
        journeys: [
          { ...journey, ...quality },
          { ...back, ...quality },
        ],
        distance_m: 0,
        partial: false,
        trip_status: "completed",
        untracked_journeys: 0,
        retention_days: 90,
        gap_minutes: 10,
        max_accuracy_m: 100,
        max_speed_kmh: 160,
      },
    }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Histórico de trajetos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Viagem executada", exact: true })
    .selectOption("trip");
  await page
    .getByRole("combobox", { name: "Veículo e trecho registrado", exact: true })
    .selectOption("bus/outbound");
  const mileage = page.getByRole("region", {
    name: "Quilometragem registrada",
    exact: true,
  });
  await expect(mileage.locator("dl dd").nth(0)).toHaveText("0,00 km");
  await expect(mileage.locator("dl dd").nth(1)).toHaveText("0,00 km");
  await expect(mileage.locator("dl dd").nth(2)).toHaveText(
    "Sem lacunas detectadas",
  );
  await expect(
    mileage.getByText("Não calculável", { exact: true }),
  ).toHaveCount(0);
});

test("falha no cálculo não impede abrir o mapa e permite nova tentativa", async ({
  page,
}) => {
  await setup(page);
  let fail = true;
  await page.route("**/api/v1/tracking/history/trip/distance", (route) =>
    fail
      ? route.fulfill({ status: 503, json: { detail: "Indisponível" } })
      : route.fallback(),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Histórico de trajetos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Viagem executada", exact: true })
    .selectOption("trip");
  await page
    .getByRole("combobox", { name: "Veículo e trecho registrado", exact: true })
    .selectOption("bus/outbound");
  await expect(
    page.getByRole("region", {
      name: "Mapa do percurso registrado",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Não foi possível calcular a quilometragem.", {
      exact: false,
    }),
  ).toBeVisible();
  fail = false;
  await page
    .getByRole("button", { name: "Tentar calcular novamente", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Quilometragem registrada", exact: true }),
  ).toBeVisible();
});
