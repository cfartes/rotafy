import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, nexus = false) {
  const saved: any[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "u",
        role: nexus ? "nexus" : "admin",
        full_name: "Operador",
        company_id: nexus ? null : "c",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "c",
        slug: "empresa",
        trade_name: "Empresa Exemplo",
        operational_profile: "tourism",
        is_active: true,
      };
    if (path === "/dashboard")
      body = {
        summary: {
          completed_trips: 0,
          running_trips: 0,
          scheduled_trips: 0,
          cancelled_trips: 0,
        },
        active_routes: 0,
        sales: {
          confirmed_reservations: 0,
          passengers: 0,
          reserved_cents: 0,
          paid_cents: 0,
        },
        ranking: [],
        upcoming: [],
      };
    if (path === "/nexus/companies")
      body = [
        {
          id: "c",
          slug: "empresaexemplo",
          trade_name: "Empresa Exemplo de Turismo",
          corporate_name: "Empresa Exemplo LTDA",
          operational_profile: "tourism",
          is_active: true,
        },
      ];
    if (path === "/vehicles")
      body = [
        {
          id: "v",
          name: "Ônibus Executivo 01",
          plate: "SAD0106",
          capacity: 46,
          is_active: true,
        },
      ];
    if (path === "/packages")
      body = [
        {
          id: "p",
          name: "Balneário Camboriú",
          destination: "Balneário Camboriú",
          price_cents: 10000,
          description: "Pacote de demonstração",
          is_active: true,
        },
      ];
    if (path === "/company/whatsapp/hours") {
      if (route.request().method() === "PUT")
        saved.push(route.request().postDataJSON());
      body = saved.at(-1) || {
        enabled: true,
        timezone: "America/Sao_Paulo",
        intervals: [
          { day: 0, start: "08:00", end: "18:00" },
          { day: 1, start: "09:00", end: "18:00" },
        ],
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto(nexus ? "/nexus" : "/");
  await page
    .getByRole("button", { name: "Usar somente necessários", exact: true })
    .click();
  return saved;
}

for (const screen of ["Empresas", "Veículos", "Pacotes"]) {
  test(`${screen}: colunas legíveis e ações acessíveis em celular`, async ({
    page,
  }) => {
    await setup(page, screen === "Empresas");
    await page.getByRole("button", { name: screen, exact: true }).click();
    const table = page.locator(".table-scroll table").first();
    const scroll = table.locator("..");
    const value =
      screen === "Empresas"
        ? table.getByText("Ativo", { exact: true })
        : screen === "Veículos"
          ? table.getByRole("cell", { name: "SAD0106", exact: true })
          : table.getByRole("cell", { name: /R.*100,00/ });
    for (const width of [360, 320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(value).toBeAttached();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        await value.evaluate((node) => {
          const r = document.createRange();
          r.selectNodeContents(
            [...node.childNodes]
              .filter(
                (n) => n.nodeType === Node.TEXT_NODE && n.textContent?.trim(),
              )
              .at(-1) || node,
          );
          return r.getClientRects().length;
        }),
      ).toBe(1);
      if (width <= 390) {
        expect(
          await scroll.evaluate((node) => node.scrollWidth > node.clientWidth),
        ).toBe(true);
        await expect(scroll).toHaveAttribute("tabindex", "0");
        await scroll.focus();
        await page.keyboard.press("ArrowRight");
        await expect
          .poll(() => scroll.evaluate((node) => node.scrollLeft))
          .toBeGreaterThan(0);
        await scroll.evaluate((node) => {
          node.scrollLeft = node.scrollWidth;
        });
        await expect(
          table
            .getByRole("button", {
              name: screen === "Empresas" ? "Editar dados" : "Editar",
              exact: true,
            })
            .first(),
        ).toBeInViewport();
      }
    }
    await page.setViewportSize({ width: 360, height: 900 });
    await scroll.evaluate((node) => {
      node.scrollLeft = 0;
    });
    await page.screenshot({
      path: `../artifacts/mobile-layout-${screen}.png`,
      animations: "disabled",
    });
    await scroll.evaluate((node) => {
      node.scrollLeft = node.scrollWidth;
    });
    await table
      .getByRole("button", {
        name: screen === "Empresas" ? "Editar dados" : "Editar",
        exact: true,
      })
      .first()
      .click();
    await expect(
      page.getByRole("dialog", {
        name:
          screen === "Empresas"
            ? "Editar empresa"
            : screen === "Veículos"
              ? "Editar veículo"
              : "Editar pacote",
        exact: true,
      }),
    ).toBeVisible();
  });
}

test("horários mantêm dia separado e início/término juntos sem alterar os valores", async ({
  page,
}) => {
  const saved = await setup(page);
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  const row = page.locator(".business-hours-row").first();
  for (const width of [360, 320, 390, 700]) {
    await page.setViewportSize({ width, height: 900 });
    const day = await row
      .getByRole("combobox", { name: "Dia da semana 1", exact: true })
      .boundingBox();
    const start = await row
      .getByLabel("Início 1", { exact: true })
      .boundingBox();
    const end = await row
      .getByLabel("Término 1", { exact: true })
      .boundingBox();
    expect(day!.width).toBeGreaterThan(start!.width * 1.8);
    expect(Math.abs(start!.y - end!.y)).toBeLessThan(2);
    expect(start!.y).toBeGreaterThan(day!.y);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 360, height: 900 });
  await row.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "../artifacts/mobile-layout-horarios.png" });
  await row.getByLabel("Início 1", { exact: true }).fill("07:30");
  await page
    .getByRole("button", {
      name: "Salvar horários de atendimento",
      exact: true,
    })
    .click();
  await expect.poll(() => saved.at(-1)?.intervals[0].start).toBe("07:30");
  await page
    .getByRole("button", { name: "Remover horário 2", exact: true })
    .click();
  await expect(page.locator(".business-hours-row")).toHaveCount(1);
});

test("paginação permanece acessível ao deslizar a tabela", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/vehicles", (route) =>
    route.fulfill({
      json: Array.from({ length: 21 }, (_, i) => ({
        id: `v${i}`,
        name: `Veículo ${i + 1}`,
        plate: `DEM${String(i).padStart(4, "0")}`,
        capacity: 46,
        is_active: true,
      })),
    }),
  );
  await page.getByRole("button", { name: "Veículos", exact: true }).click();
  const table = page.locator(".operations-table-vehicles");
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await page.setViewportSize({ width: 360, height: 900 });
  const scroll = table.locator("..");
  await scroll.evaluate((node) => {
    node.scrollLeft = node.scrollWidth;
  });
  const nav = scroll.getByRole("navigation", { name: "Paginação da tabela" });
  await nav.evaluate((node) =>
    window.scrollTo(0, window.scrollY + node.getBoundingClientRect().top - 400),
  );
  const next = nav.getByRole("button", { name: "Próxima página", exact: true });
  await expect(next).toBeInViewport();
  await next.click();
  await expect(table.locator("tbody tr")).toHaveCount(1);
});
