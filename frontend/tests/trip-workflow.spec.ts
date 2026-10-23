import { test, expect, type Page } from "@playwright/test";

async function setup(
  page: Page,
  role = "admin",
  itinerary?: { legs: any[]; mode: string },
) {
  const future = new Date(Date.now() + 7 * 86400000).toISOString();
  const trips = [
    ["open", "Transfer futuro", "scheduled"],
    ["closed", "Transfer concluído", "completed"],
    ["ongoing", "Transfer em andamento", "in_progress"],
    ["cancelled", "Transfer cancelado", "cancelled"],
    ["past", "Transfer passado", "scheduled"],
  ].map(([id, name, status]) => ({
    id,
    name,
    status,
    destination: "Navegantes",
    mode: "one_way",
    starts_at: id === "past" ? "2020-01-01T10:00:00Z" : future,
    ends_at: future,
    price_cents: 5000,
    vehicle_count: 1,
    capacity: 5,
  }));
  const leg = {
    id: "leg",
    origin: "Blumenau",
    destination: "Navegantes",
    starts_at: future,
    ends_at: future,
    stops: [],
  };
  const saved: unknown[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    let body: unknown = [];
    let status = 200;
    if (path === "/auth/me")
      body = {
        id: "user",
        company_id: "company",
        role,
        full_name: "Atendente Teste",
        email: "teste@example.com",
        is_active: true,
      };
    else if (path === "/company")
      body = {
        id: "company",
        trade_name: "Agência Teste",
        slug: "teste",
        is_active: true,
        primary_color: "#087f78",
        accent_color: "#ffffff",
      };
    else if (path === "/trips") body = trips;
    else if (/\/route$/.test(path))
      body = {
        legs: [
          {
            ...leg,
            position: 1,
            navigation_stages: [
              {
                maps_url: "https://www.google.com/maps/dir/?api=1",
                from_position: 0,
                to_position: 1,
              },
            ],
            points: [
              {
                position: 0,
                name: "Blumenau",
                address: "Terminal",
                scheduled_at: future,
                maps_url: "https://www.google.com/maps/dir/?api=1",
              },
            ],
          },
        ],
      };
    else if (/\/availability$/.test(path))
      body = {
        vehicles: [],
        suggested_allocation_id: null,
        can_book: true,
        message: "",
      };
    else if (/\/reservations$/.test(path)) {
      if (request.method() === "POST") {
        saved.push({ path, ...request.postDataJSON() });
        status = 201;
        body = { id: "reservation" };
      } else body = [];
    } else if (path.endsWith("/refresh-routes")) {
      saved.push({ path, ...request.postDataJSON() });
      body = { id: "open" };
    } else if (path.endsWith("/boarding-locations")) body = [];
    else if (path.startsWith("/trips/")) {
      const trip = trips.find((t) => t.id === path.split("/")[2]);
      body = {
        ...trip,
        edit_version: 3,
        route_snapshot: { id: "route", name: "Rota do transfer", version: 1 },
        legs: itinerary?.legs ?? [leg],
        mode: itinerary?.mode ?? trip?.mode,
        completion:
          trip?.status === "completed"
            ? {
                recorded_at: "2026-10-08T17:05:00Z",
                actor_name: "Motorista Teste",
              }
            : null,
        vehicles: [
          {
            id: "allocation",
            name: "Executivo",
            plate: "ABC1D23",
            capacity: 5,
            driver_id: "user",
            driver_name: "Motorista Teste",
            guides: [],
            journey_states:
              trip?.status === "completed"
                ? {
                    leg: {
                      status: "completed",
                      started_at: "2026-10-08T16:00:00Z",
                      arrived_at: "2026-10-08T17:05:00Z",
                      arrival_location: {
                        status: "captured",
                        latitude: -26.898,
                        longitude: -48.654,
                        accuracy_m: 10,
                        captured_at: "2026-10-08T17:04:55Z",
                        actor_name: "Motorista Teste",
                      },
                    },
                  }
                : {},
          },
        ],
      };
    }
    await route.fulfill({ status, json: body });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  return saved;
}

test("route refresh requires confirmation and is disabled for closed trips", async ({
  page,
}) => {
  let routeReads = 0;
  page.on("request", (request) => {
    if (/\/vehicles\/[^/]+\/route$/.test(new URL(request.url()).pathname))
      routeReads++;
  });
  const saved = await setup(page);
  await page.getByRole("button", { name: "Viagens", exact: true }).click();
  await page
    .locator("tbody tr")
    .filter({ hasText: "Transfer futuro" })
    .getByRole("button", { name: "Detalhes" })
    .click();
  const refresh = page.getByRole("button", {
    name: "Atualizar com a versão atual da Rota",
    exact: true,
  });
  await expect(refresh).toBeEnabled();
  page.once("dialog", (dialog) => dialog.dismiss());
  await refresh.click();
  expect(saved).toHaveLength(0);
  page.once("dialog", (dialog) => dialog.accept());
  await refresh.click();
  await expect.poll(() => saved.length).toBe(1);
  expect(saved[0]).toEqual({
    path: "/trips/open/refresh-routes",
    expected_version: 3,
  });
  await expect.poll(() => routeReads).toBeGreaterThan(1);
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await page
    .locator("tbody tr")
    .filter({ hasText: "Transfer concluído" })
    .getByRole("button", { name: "Detalhes" })
    .click();
  await expect(refresh).toBeDisabled();
});

test("trip list filters open, ongoing, completed and cancelled states", async ({
  page,
}) => {
  await setup(page);
  await page.getByRole("button", { name: "Viagens", exact: true }).click();
  const filter = page.getByLabel("Situação da viagem");
  await filter.selectOption("scheduled");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Transfer futuro");
  await filter.selectOption("open");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Transfer passado");
  await expect(page.locator("tbody")).not.toContainText("Transfer concluído");
  await filter.selectOption("completed");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Transfer concluído");
  await filter.selectOption("in_progress");
  await expect(page.locator("tbody")).toContainText("Transfer em andamento");
  await filter.selectOption("cancelled");
  await expect(page.locator("tbody")).toContainText("Transfer cancelado");
});

test("completed detail is wide, read only and shows arrival coordinates", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await setup(page);
  await page.getByRole("button", { name: "Viagens", exact: true }).click();
  await page.getByLabel("Situação da viagem").selectOption("completed");
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Detalhes da viagem" });
  await expect(
    dialog.getByRole("button", { name: "Reservas e lugares" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Abrir rota no Google Maps" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Navegar até a saída" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Abrir embarque · Ida" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("heading", { name: "Finalização e chegadas" }),
  ).toBeVisible();
  await expect(dialog).toContainText("08/10/2026, 14:05");
  await expect(dialog).toContainText("precisão 10 m");
  await expect(
    dialog.getByRole("link", { name: "Ver local da chegada no Google Maps" }),
  ).toHaveAttribute("href", /query=-26.898%2C-48.654/);
  expect((await dialog.boundingBox())!.width).toBeGreaterThanOrEqual(900);
  await page.screenshot({
    path: "../docs/screenshots/finalizacao-viagem-desktop.png",
  });
});

test("cancelled detail disables navigation and fits a phone screen", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Viagens", exact: true }).click();
  await page.getByLabel("Situação da viagem").selectOption("cancelled");
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("button", { name: "Reservas e lugares" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Abrir rota no Google Maps" }),
  ).toBeDisabled();
  expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "../docs/screenshots/finalizacao-viagem-mobile.png",
  });
});

for (const role of ["admin", "attendant"])
  test(`${role} sells a ticket from side menu for the selected open trip`, async ({
    page,
  }) => {
    const saved = await setup(page, role);
    await page
      .getByRole("complementary")
      .getByRole("button", { name: "Vender bilhete", exact: true })
      .click();
    const select = page.getByLabel("Viagem para vender bilhete");
    await expect(select.locator("option")).toHaveCount(2);
    await select.selectOption("open");
    await page
      .getByRole("main")
      .getByRole("button", { name: "Vender bilhete", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Nova reserva familiar" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Nome do responsável").fill("Família Teste");
    await dialog.getByLabel("Telefone da família").fill("47999998888");
    await dialog
      .getByLabel("Nome do passageiro 1", { exact: true })
      .fill("Passageiro Teste");
    await dialog.getByRole("button", { name: "Salvar reserva" }).click();
    await expect(dialog).not.toBeVisible();
    expect(saved).toHaveLength(1);
    expect(saved[0]).toMatchObject({
      path: "/trips/open/reservations",
      contact_name: "Família Teste",
      status: "confirmed",
      passengers: [{ full_name: "Passageiro Teste" }],
    });
    await expect(
      page.getByRole("button", { name: "Voltar à venda de bilhetes" }),
    ).toHaveCount(0);
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Vender bilhete", exact: true })
      .click();
    await expect(select).toBeVisible();
  });

test("ticket sale is not offered to drivers or guides", async ({ page }) => {
  await setup(page, "driver");
  await expect(
    page
      .getByRole("complementary")
      .getByRole("button", { name: "Vender bilhete", exact: true }),
  ).toHaveCount(0);
});

test("ticket sale accepts one hotel field, checks Maps and requires a location", async ({
  page,
}) => {
  const saved = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  await page.getByLabel("Viagem para vender bilhete").selectOption("open");
  await page
    .getByRole("main")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Nova reserva familiar" });
  await dialog
    .getByLabel("Nome do respons\u00e1vel")
    .fill("Fam\u00edlia Hotel");
  await dialog.getByLabel("Telefone da fam\u00edlia").fill("47999998888");
  await dialog
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Cliente Hotel");
  const pickup = dialog.getByRole("combobox", {
    name: "Local de embarque",
    exact: true,
  });
  await pickup.fill("");
  await dialog.getByRole("button", { name: "Salvar reserva" }).click();
  expect(saved).toHaveLength(0);
  await pickup.fill("Hotel Central");
  const maps = dialog.getByRole("link", {
    name: "Conferir local de embarque no Google Maps (nova aba)",
  });
  const url = new URL((await maps.getAttribute("href"))!);
  expect(url.searchParams.get("query")).toContain("Hotel Central, Blumenau");
  expect(await maps.getAttribute("target")).toBe("_blank");
  await expect(
    dialog.getByLabel(/tipo de local|endere\u00e7o completo|ordem de visita/),
  ).toHaveCount(0);
  await dialog.locator(".reservation-pickup").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "../artifacts/review-reservation-desktop.png",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await dialog.locator(".reservation-pickup").scrollIntoViewIfNeeded();
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await page.screenshot({ path: "../artifacts/review-reservation-mobile.png" });
  await dialog.getByRole("button", { name: "Salvar reserva" }).click();
  await expect(dialog).not.toBeVisible();
  expect(saved[0]).toMatchObject({
    journeys: [
      {
        boarding_location: {
          name: "Hotel Central",
          address: "",
          complement: "",
          order: 1,
        },
      },
    ],
  });
});

test("package repeats pickup for daily tours and return, with an independent override", async ({
  page,
}) => {
  const legs = [
    { id: "out1", origin: "Maceió", destination: "Maragogi", stops: [] },
    { id: "back1", origin: "Maragogi", destination: "Maceió", stops: [] },
    { id: "out2", origin: "Maceió", destination: "Praia do Gunga", stops: [] },
    { id: "back2", origin: "Praia do Gunga", destination: "Maceió", stops: [] },
  ];
  const saved = await setup(page, "admin", { legs, mode: "multi_destination" });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  await page.getByLabel("Viagem para vender bilhete").selectOption("open");
  await page
    .getByRole("main")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Nova reserva familiar" });
  await dialog.getByLabel("Nome do responsável").fill("Família Passeio");
  await dialog.getByLabel("Telefone da família").fill("47999998888");
  await dialog
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Pessoa Teste");
  await dialog
    .getByRole("combobox", { name: "Local de embarque", exact: true })
    .fill("Hotel da Praia");
  await expect(
    dialog.getByLabel(
      "Usar este local nos passeios com saída de Maceió e no retorno",
    ),
  ).toBeChecked();
  await dialog
    .getByText("Ajustar locais por passeio (4)", { exact: true })
    .click();
  await expect(
    dialog.getByRole("combobox", {
      name: "Embarque · deslocamento 3",
      exact: true,
    }),
  ).toHaveValue("Hotel da Praia");
  await expect(
    dialog.getByRole("combobox", {
      name: "Desembarque · deslocamento 2",
      exact: true,
    }),
  ).toHaveValue("Hotel da Praia");
  await dialog
    .getByRole("combobox", {
      name: "Desembarque · deslocamento 4",
      exact: true,
    })
    .fill("Aeroporto de Maceió");
  await expect(
    dialog.getByLabel(
      "Usar este local nos passeios com saída de Maceió e no retorno",
    ),
  ).not.toBeChecked();
  await dialog.getByRole("button", { name: "Salvar reserva" }).click();
  await expect(dialog).not.toBeVisible();
  expect(saved[0]).toMatchObject({
    journeys: [
      { leg_id: "out1", boarding_location: { name: "Hotel da Praia" } },
      { leg_id: "back1", dropoff_location: { name: "Hotel da Praia" } },
      { leg_id: "out2", boarding_location: { name: "Hotel da Praia" } },
      { leg_id: "back2", dropoff_location: { name: "Aeroporto de Maceió" } },
    ],
  });
});

test("existing hotel preserves address, complement and order when selected by name", async ({
  page,
}) => {
  const saved = await setup(page);
  const location = {
    name: "Hotel Central",
    address: "Rua das Flores, 100",
    complement: "Recepção",
    order: 7,
  };
  await page.route("**/api/v1/trips/open/boarding-locations", (route) =>
    route.fulfill({
      json: [
        {
          leg_id: "leg",
          boarding_position: 0,
          dropoff_position: 1,
          boarding_location: location,
          dropoff_location: null,
        },
      ],
    }),
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  await page.getByLabel("Viagem para vender bilhete").selectOption("open");
  await page
    .getByRole("main")
    .getByRole("button", { name: "Vender bilhete", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Nova reserva familiar" });
  await dialog.getByLabel("Nome do responsável").fill("Família Reutilizada");
  await dialog.getByLabel("Telefone da família").fill("47999998888");
  await dialog
    .getByLabel("Nome do passageiro 1", { exact: true })
    .fill("Cliente Hotel");
  await expect(
    dialog.locator('datalist option[value="Hotel Central — Rua das Flores, 100"]'),
  ).toHaveCount(1);
  await dialog
    .getByRole("combobox", { name: "Local de embarque", exact: true })
    .fill("Hotel Central");
  await expect(
    dialog.getByRole("combobox", { name: "Local de embarque", exact: true }),
  ).toHaveValue("Hotel Central — Rua das Flores, 100");
  await dialog.getByRole("button", { name: "Salvar reserva" }).click();
  await expect(dialog).not.toBeVisible();
  expect(saved[0]).toMatchObject({
    journeys: [{ boarding_location: location }],
  });
});
