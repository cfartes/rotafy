import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, role = "admin", profile = "tourism") {
  const routes: Record<string, any>[] = [];
  const trips: Record<string, any>[] = [];
  const submissions: Record<string, any>[] = [];
  const cities = [
    { id: 4202404, name: "Blumenau", uf: "SC" },
    { id: 4211306, name: "Navegantes", uf: "SC" },
  ];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    let body: unknown = [],
      status = 200;
    if (path === "/auth/me")
      body = {
        id: "user",
        company_id: "company",
        role,
        full_name: "Operador",
        email: "operador@example.com",
        is_active: true,
      };
    else if (path === "/company")
      body = {
        id: "company",
        trade_name: "Agência Teste",
        slug: "teste",
        operational_profile: profile,
        is_active: true,
      };
    else if (path === "/locations/states")
      body = [{ uf: "SC", name: "Santa Catarina" }];
    else if (path === "/locations/cities/SC") body = cities;
    else if (path === "/vehicles")
      body = [
        {
          id: "vehicle",
          name: "Executivo",
          plate: "ABC1D23",
          capacity: 15,
          is_active: true,
        },
      ];
    else if (path === "/operations/crew")
      body = [
        { id: "driver", full_name: "Motorista Teste", role: "driver" },
        { id: "driver2", full_name: "Segundo Motorista", role: "driver" },
        { id: "guide1", full_name: "Guia Um", role: "guide" },
        { id: "guide2", full_name: "Guia Dois", role: "guide" },
      ];
    else if (path === "/routes" && request.method() === "POST") {
      const data = request.postDataJSON();
      submissions.push({ path, data });
      body = { ...data, id: `route-${routes.length}`, version: 1 };
      routes.push(body as Record<string, any>);
      status = 201;
    } else if (path === "/routes") body = routes;
    else if (path.startsWith("/routes/") && request.method() === "PATCH") {
      const data = request.postDataJSON();
      const index = routes.findIndex((r) => r.id === path.split("/")[2]);
      body = {
        ...data,
        id: routes[index].id,
        version: routes[index].version + 1,
      };
      routes[index] = body as Record<string, any>;
      submissions.push({ path, data });
    } else if (path === "/trips" && request.method() === "POST") {
      const data = request.postDataJSON();
      submissions.push({ path, data });
      body = {
        ...data,
        id: `trip-${trips.length}`,
        status: "scheduled",
        starts_at: data.legs[0].starts_at,
        ends_at: data.legs.at(-1).ends_at,
        capacity: 15,
        vehicle_count: 1,
      };
      trips.push(body as Record<string, any>);
      status = 201;
    } else if (path === "/trips") body = trips;
    await route.fulfill({ status, json: body });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  return { routes, submissions };
}

async function createRoute(page: Page, roundTrip = false) {
  await page.getByRole("button", { name: "Rotas", exact: true }).click();
  await page.getByRole("button", { name: "Nova Rota", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Nova Rota" });
  await dialog
    .getByLabel("Nome da Rota", { exact: true })
    .fill("Transfer Aeroporto");
  if (roundTrip)
    await dialog
      .getByRole("combobox", { name: "Sentidos", exact: true })
      .selectOption("round_trip");
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
  const outbound = dialog.locator("fieldset").first();
  await outbound
    .getByLabel("Endereço de saída", { exact: true })
    .fill("Terminal Blumenau");
  await outbound
    .getByLabel("Endereço de chegada", { exact: true })
    .fill("Aeroporto Navegantes");
  await outbound
    .getByLabel("Deslocamento estimado (minutos)", { exact: true })
    .fill("60");
  await outbound
    .getByLabel("Tempo adicional total nas paradas (minutos)", { exact: true })
    .fill("20");
  await outbound
    .getByRole("button", { name: "Adicionar parada", exact: true })
    .click();
  await outbound.getByLabel("Parada 1", { exact: true }).fill("Hotel Centro");
  await outbound
    .getByLabel("Endereço da parada 1", { exact: true })
    .fill("Rua do Hotel, Blumenau SC");
  await expect(dialog.locator('input[type="datetime-local"]')).toHaveCount(0);
  if (roundTrip) {
    await dialog
      .getByRole("button", { name: "Gerar volta invertendo a ida" })
      .click();
    const inbound = dialog.locator("fieldset").nth(1);
    await expect(
      inbound.getByLabel("Cidade de origem da volta", { exact: true }),
    ).toHaveValue("4211306");
    await expect(
      inbound.getByRole("combobox", { name: "Finalidade", exact: true }),
    ).toHaveValue("dropoff");
  }
  await dialog
    .getByRole("button", { name: "Salvar Rota", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Transfer Aeroporto", exact: true }),
  ).toBeVisible();
}

test("reuse route for round-trip scheduling, with no individual stop times", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { submissions } = await setup(page);
  await createRoute(page, true);
  await page.screenshot({
    path: "../docs/screenshots/rotas-catalogo-desktop.png",
  });
  await page
    .getByRole("button", { name: "Viagens e pacotes", exact: true })
    .click();
  await page.getByRole("button", { name: "Nova viagem", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Nova viagem comercial" });
  await dialog
    .getByRole("combobox", { name: "Rota", exact: true })
    .selectOption("route-0");
  await expect(
    dialog.getByLabel("Nome da viagem", { exact: true }),
  ).toHaveValue("Transfer Aeroporto");
  await expect(
    dialog.getByLabel("Cidade de origem da ida", { exact: true }),
  ).toHaveCount(0);
  await dialog
    .getByLabel("Saída da ida", { exact: true })
    .fill("2027-01-10T08:00");
  await dialog
    .getByLabel("Saída da volta", { exact: true })
    .fill("2027-01-10T18:00");
  await expect(dialog).toContainText("10/01/2027, 09:20");
  await dialog
    .getByRole("combobox", { name: "Veículo 1", exact: true })
    .selectOption("vehicle");
  await dialog
    .getByRole("combobox", { name: "Motorista 1", exact: true })
    .selectOption("driver");
  await dialog
    .getByLabel("Segundo Motorista · motorista adicional · veículo 1", {
      exact: true,
    })
    .check();
  await dialog.getByLabel("Guia Um", { exact: true }).check();
  await dialog.getByLabel("Guia Dois", { exact: true }).check();
  await dialog
    .getByRole("button", { name: "Criar viagem", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  const sent = submissions.find((s) => s.path === "/trips")!.data;
  expect(sent.vehicles[0].driver_ids).toEqual(["driver", "driver2"]);
  expect(sent.vehicles[0].guide_ids).toEqual(["guide1", "guide2"]);
  expect(sent.route_id).toBe("route-0");
  expect(sent.route_version).toBe(1);
  expect(sent.legs[0].ends_at).toBe("2027-01-10T12:20:00.000Z");
  expect(sent.legs[1].ends_at).toBe("2027-01-10T22:20:00.000Z");
  expect(sent.legs[0].stops[0].scheduled_at).toBeNull();
  expect(sent.legs[0]).not.toHaveProperty("duration_minutes");
});

test("route catalog supports editing duration and deactivation", async ({
  page,
}) => {
  const { submissions } = await setup(page);
  await createRoute(page);
  await page.getByRole("button", { name: "Editar Rota", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Editar Rota" });
  await dialog
    .getByLabel("Deslocamento estimado (minutos)", { exact: true })
    .fill("90");
  await dialog.getByLabel("Rota ativa para novas viagens").uncheck();
  await dialog
    .getByRole("button", { name: "Salvar Rota", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".operation-card")).toContainText("Inativa");
  expect(submissions.at(-1)!.data.expected_version).toBe(1);
  expect(submissions.at(-1)!.data.legs[0].duration_minutes).toBe(90);
});

test("driver does not see route administration", async ({ page }) => {
  await setup(page, "driver");
  await expect(
    page.getByRole("button", { name: "Rotas", exact: true }),
  ).toHaveCount(0);
});

test("regular company schedules a simple trip without package controls", async ({
  page,
}) => {
  const { submissions } = await setup(page, "admin", "regular");
  await createRoute(page);
  await expect(
    page.getByText("Transporte regular", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Viagens", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Pacotes", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Nova viagem", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Nova viagem comercial" });
  await expect(
    dialog.getByRole("combobox", { name: "Pacote (opcional)", exact: true }),
  ).toHaveCount(0);
  await dialog
    .getByRole("combobox", { name: "Rota", exact: true })
    .selectOption("route-0");
  await dialog
    .getByLabel("Saída da ida", { exact: true })
    .fill("2027-01-10T08:00");
  await dialog
    .getByRole("combobox", { name: "Veículo 1", exact: true })
    .selectOption("vehicle");
  await dialog
    .getByRole("combobox", { name: "Motorista 1", exact: true })
    .selectOption("driver");
  await dialog
    .getByRole("button", { name: "Criar viagem", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  const sent = submissions.at(-1)!.data;
  expect(sent.package_id).toBeNull();
  expect(sent.mode).toBe("one_way");
});

test("route creation fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Rotas", exact: true }).click();
  await page.getByRole("button", { name: "Nova Rota", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Nova Rota" });
  const bounds = await dialog.boundingBox();
  expect(bounds!.width).toBeLessThanOrEqual(390);
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: "../docs/screenshots/rotas-cadastro-mobile.png",
  });
});
