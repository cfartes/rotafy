import { test, expect } from "@playwright/test";

for (const daily of [false, true]) {
  test(`create and schedule a complete package (${daily ? "daily outings" : "sequence"})`, async ({
    page,
  }) => {
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    const cities = [
      { id: 4202404, name: "Blumenau", uf: "SC" },
      { id: 4211306, name: "Navegantes", uf: "SC" },
    ];
    const routeLeg = (reverse: boolean) => ({
      origin_city_id: cities[reverse ? 1 : 0].id,
      destination_city_id: cities[reverse ? 0 : 1].id,
      origin: cities[reverse ? 1 : 0].name,
      destination: cities[reverse ? 0 : 1].name,
      origin_uf: "SC",
      destination_uf: "SC",
      origin_address: "Terminal",
      destination_address: "Hotel",
      duration_minutes: 60,
      stop_minutes: 15,
      stops: [
        {
          name: "Hotel Centro",
          address: "Rua Central",
          kind: "both",
          scheduled_at: null,
        },
      ],
    });
    const savedRoute = {
      id: "route",
      name: "Circuito SC",
      mode: "round_trip",
      version: 1,
      is_active: true,
      legs: [routeLeg(false), routeLeg(true)],
    };
    const packages: any[] = [],
      trips: any[] = [],
      submissions: any[] = [];
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(),
        path = new URL(request.url()).pathname.replace("/api/v1", "");
      let body: any = [],
        status = 200;
      if (path === "/auth/me")
        body = {
          id: "user",
          company_id: "company",
          role: "admin",
          full_name: "Operador",
          is_active: true,
        };
      else if (path === "/company")
        body = {
          id: "company",
          trade_name: "Agência",
          slug: "teste",
          is_active: true,
        };
      else if (path === "/locations/states")
        body = [{ uf: "SC", name: "Santa Catarina" }];
      else if (path === "/locations/cities/SC") body = cities;
      else if (path === "/routes") body = [savedRoute];
      else if (path === "/vehicles")
        body = [
          {
            id: "bus",
            name: "Ônibus",
            plate: "ABC1D23",
            capacity: 46,
            is_active: true,
          },
        ];
      else if (path === "/operations/crew")
        body = [{ id: "driver", full_name: "Motorista", role: "driver" }];
      else if (path === "/packages" && request.method() === "POST") {
        const data = request.postDataJSON();
        submissions.push({ path, data });
        body = {
          ...data,
          id: "package",
          version: 1,
          itinerary: {
            ...data.itinerary,
            steps: data.itinerary.steps.map((s: any) => ({
              ...s,
              leg: savedRoute.legs[s.route_leg_position - 1],
            })),
          },
        };
        packages.push(body);
        status = 201;
      } else if (path === "/packages") body = packages;
      else if (path === "/trips" && request.method() === "POST") {
        const data = request.postDataJSON();
        submissions.push({ path, data });
        body = {
          ...data,
          id: "trip",
          status: "scheduled",
          starts_at: data.legs[0].starts_at,
          ends_at: data.legs.at(-1).ends_at,
          vehicle_count: 1,
          capacity: 46,
        };
        trips.push(body);
        status = 201;
      } else if (path === "/trips") body = trips;
      await route.fulfill({ status, json: body });
    });
    await page.goto("/");
    await page
      .getByRole("button", { name: "Viagens e pacotes", exact: true })
      .click();
    await page.getByRole("button", { name: "Pacotes", exact: true }).click();
    await page
      .getByRole("button", { name: "Novo pacote", exact: true })
      .click();
    const catalog = page.getByRole("dialog", { name: "Novo pacote" });
    await catalog.getByLabel("Nome", { exact: true }).fill("Fim de semana SC");
    await catalog.getByLabel("Destino", { exact: true }).fill("Litoral SC");
    await catalog
      .getByLabel("Valor por passageiro (R$)", { exact: true })
      .fill("500,00");
    await catalog.getByLabel("Pacote com roteiro de vários destinos").check();
    if (daily) {
      await catalog
        .getByRole("combobox", { name: "Formato do pacote", exact: true })
        .selectOption("daily");
      await catalog
        .getByRole("combobox", {
          name: "Rota de ida e volta do passeio 1",
          exact: true,
        })
        .selectOption("route");
      await catalog
        .getByRole("button", { name: "Adicionar passeio", exact: true })
        .click();
      await catalog
        .getByRole("combobox", {
          name: "Rota de ida e volta do passeio 2",
          exact: true,
        })
        .selectOption("route");
      await catalog.getByLabel("Dia do passeio 2", { exact: true }).fill("4");
      await expect(
        catalog.getByRole("combobox", { name: /Finalidade/ }),
      ).toHaveCount(0);
      await page.setViewportSize({ width: 390, height: 844 });
      expect(
        await catalog.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.setViewportSize({ width: 1440, height: 1000 });
    } else {
      await catalog
        .getByLabel("Nome do destino 1", { exact: true })
        .fill("Navegantes");
      await catalog
        .getByLabel("UF de destino comercial 1", { exact: true })
        .selectOption("SC");
      await catalog
        .getByLabel("Cidade de destino comercial 1", { exact: true })
        .selectOption("4211306");
      await catalog
        .getByRole("combobox", { name: "Rota do deslocamento 1", exact: true })
        .selectOption("route:1");
      await catalog
        .getByRole("combobox", { name: "Rota do deslocamento 2", exact: true })
        .selectOption("route:2");
      const firstPurpose = catalog.getByRole("combobox", {
        name: "Finalidade do deslocamento 1",
        exact: true,
      });
      await firstPurpose.selectOption("");
      await catalog
        .getByRole("button", { name: "Salvar", exact: true })
        .click();
      await expect(catalog.getByRole("alert")).toContainText(
        "Destino 1 (Navegantes)",
      );
      expect(submissions).toHaveLength(0);
      await firstPurpose.selectOption("1");
      const secondPurpose = catalog.getByRole("combobox", {
        name: "Finalidade do deslocamento 2",
        exact: true,
      });
      await secondPurpose.selectOption("1");
      await catalog
        .getByRole("button", { name: "Salvar", exact: true })
        .click();
      await expect(catalog.getByRole("alert")).toContainText(
        "marque a chegada somente uma vez",
      );
      expect(submissions).toHaveLength(0);
      await secondPurpose.selectOption("");
    }
    await catalog.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(catalog).not.toBeVisible();
    expect(
      submissions[0].data.itinerary.steps[1].destination_position,
    ).toBeNull();
    await page
      .getByLabel("Módulos de operação")
      .getByRole("button", { name: "Viagens", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Nova viagem", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Nova viagem comercial" });
    await dialog
      .getByRole("combobox", { name: "Pacote (opcional)", exact: true })
      .selectOption("package");
    const initialDate = dialog.getByLabel("Data inicial do pacote", {
      exact: true,
    });
    for (const partial of ["0002-10-20", "0020-10-20", "0202-10-20", ""]) {
      await initialDate.fill(partial);
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByLabel("Saída do deslocamento 1", { exact: true }),
      ).toHaveValue("");
      expect(browserErrors).toEqual([]);
    }
    await initialDate.fill("2026-10-20");
    await expect(
      dialog.getByLabel("Saída do deslocamento 1", { exact: true }),
    ).toHaveValue("2026-10-20T08:00");
    await initialDate.fill("2027-02-01");
    const firstDeparture = dialog.getByLabel("Saída do deslocamento 1", {
      exact: true,
    });
    await firstDeparture.fill("0020-02-01T08:00");
    await expect(dialog).toBeVisible();
    expect(browserErrors).toEqual([]);
    await initialDate.fill("2027-02-02");
    await initialDate.fill("2027-02-01");
    await expect(dialog).toContainText("Não há venda de destinos separados");
    await expect(
      dialog.getByLabel("Saída do deslocamento 1", { exact: true }),
    ).toHaveValue("2027-02-01T08:00");
    await expect(
      dialog.getByLabel("Saída do deslocamento 2", { exact: true }),
    ).toHaveValue(daily ? "2027-02-01T16:00" : "2027-02-02T16:00");
    await expect(dialog.getByLabel("Rota", { exact: true })).toHaveCount(0);
    await dialog
      .getByRole("combobox", { name: "Veículo 1", exact: true })
      .selectOption("bus");
    await dialog
      .getByRole("combobox", { name: "Motorista 1", exact: true })
      .selectOption("driver");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await dialog.locator("form").evaluate((element) => {
      element.scrollTop = 0;
    });
    await page.screenshot({
      path: "../docs/screenshots/pacote-roteiro-desktop.png",
    });
    await page.setViewportSize({ width: 390, height: 844 });
    const bounds = await dialog.boundingBox();
    expect(bounds!.width).toBeLessThanOrEqual(390);
    expect(
      await dialog.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: "../docs/screenshots/pacote-roteiro-mobile.png",
    });
    await dialog
      .getByRole("button", { name: "Criar viagem", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
    const sent = submissions.at(-1).data;
    expect(sent.mode).toBe("multi_destination");
    expect(sent.package_version).toBe(1);
    expect(sent.legs).toHaveLength(daily ? 4 : 2);
    expect(sent.legs[1].origin_city_id).toBe(4211306);
    expect(sent.legs[0].ends_at).toBe("2027-02-01T12:15:00.000Z");
    expect(sent.legs[1].starts_at).toBe(
      daily ? "2027-02-01T19:00:00.000Z" : "2027-02-02T19:00:00.000Z",
    );
    if (daily) {
      expect(submissions[0].data.itinerary.destinations).toHaveLength(2);
      expect(
        submissions[0].data.itinerary.steps.map(
          (s: any) => s.destination_position,
        ),
      ).toEqual([1, null, 2, null]);
      expect(sent.legs[2].starts_at).toBe("2027-02-04T11:00:00.000Z");
      expect(sent.legs[3].starts_at).toBe("2027-02-04T19:00:00.000Z");
    }
  });
}
