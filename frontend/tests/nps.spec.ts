import { test, expect, type Page } from "@playwright/test";

async function mock(page: Page, role = "admin", modules = ["whatsapp"]) {
  const requests: URL[] = [];
  const saved: unknown[] = [];
  let config = { service_enabled: false, trip_enabled: false };
  const metrics = {
    surveys: 3,
    sent: 3,
    responses: 2,
    response_rate: 66.7,
    nps: 0,
    average: 5,
    promoters: 1,
    passives: 0,
    detractors: 1,
  };
  const empty = {
    surveys: 0,
    sent: 0,
    responses: 0,
    response_rate: null,
    nps: null,
    average: null,
    promoters: 0,
    passives: 0,
    detractors: 0,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "user",
        role,
        full_name: "Equipe",
        company_id: "company",
        is_active: true,
        enabled_modules: modules,
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        is_active: true,
      };
    if (path === "/nps/settings") {
      if (route.request().method() === "PUT") {
        config = route.request().postDataJSON();
        saved.push(config);
      }
      body = config;
    }
    if (path === "/nps/trips")
      body = [{ id: "trip1", name: "Passeio Maragogi" }];
    if (path === "/nps/report") {
      requests.push(url);
      if (url.searchParams.get("output")) {
        await route.fulfill({
          body:
            url.searchParams.get("output") === "pdf"
              ? "%PDF-1.7\n"
              : "Tipo;Nota\nViagem;0\n",
          contentType:
            url.searchParams.get("output") === "pdf"
              ? "application/pdf"
              : "text/csv",
        });
        return;
      }
      const selected = url.searchParams.get("trip_id") ? empty : metrics;
      body = {
        summary: selected,
        by_kind: { service: selected, trip: empty },
        evolution: [{ month: "2026-10", ...selected }],
        total: selected.surveys,
        page: 1,
        rows: selected.surveys
          ? [
              {
                id: "survey1",
                kind: "service",
                contact_name: "Maria",
                phone: "+5547999999999",
                trip_name: null,
                status: "answered",
                score: 0,
                comment:
                  "Precisamos de mais agilidade <script>alert(1)</script>",
                created_at: "2026-10-22T15:00:00Z",
                answered_at: "2026-10-22T16:00:00Z",
                error_code: null,
              },
            ]
          : [],
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  return { requests, saved };
}

test("admin configures NPS and consults KPIs, filters and exports without exposing scripts", async ({
  page,
}) => {
  const { requests, saved } = await mock(page);
  await page
    .getByRole("button", { name: "NPS e satisfação", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Avaliações dos clientes" }),
  ).toBeVisible();
  await expect(page.locator(".nps-cards")).toContainText("66,7%");
  await expect(page.locator(".nps-table").last()).toContainText(
    "<script>alert(1)</script>",
  );
  await expect(
    page
      .locator(".nps-table")
      .last()
      .getByRole("cell", { name: "0", exact: true }),
  ).toBeVisible();
  await page
    .getByText("Configurar pesquisas automáticas", { exact: true })
    .click();
  await page.getByLabel("Enviar NPS após concluir atendimento humano").check();
  await page
    .getByLabel("Enviar NPS duas horas após concluir a viagem completa")
    .check();
  await page.getByRole("button", { name: "Salvar configuração NPS" }).click();
  await expect
    .poll(() => saved.at(-1))
    .toEqual({ service_enabled: true, trip_enabled: true });
  await page.getByLabel("Viagem ou pacote").selectOption("trip1");
  await page.getByLabel("Tipo de pesquisa").selectOption("trip");
  await page.getByRole("button", { name: "Consultar NPS" }).click();
  await expect(
    page.getByText("Nenhuma pesquisa encontrada para este filtro."),
  ).toBeVisible();
  await expect(page.locator(".nps-cards")).toContainText("—");
  const csvDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  expect((await csvDownload).suggestedFilename()).toMatch(/^nps-.*\.csv$/);
  const pdfDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Emitir PDF" }).click();
  expect((await pdfDownload).suggestedFilename()).toMatch(/^nps-.*\.pdf$/);
  expect(requests.at(-1)?.searchParams.get("trip_id")).toBe("trip1");
  expect(requests.at(-1)?.searchParams.get("kind")).toBe("trip");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("attendant reads NPS without editing configuration", async ({ page }) => {
  await mock(page, "attendant");
  await page
    .getByRole("button", { name: "NPS e satisfação", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Avaliações dos clientes" }),
  ).toBeVisible();
  await expect(
    page.getByText("Configurar pesquisas automáticas", { exact: true }),
  ).toHaveCount(0);
});

for (const scenario of [
  { role: "driver", modules: ["whatsapp"] },
  { role: "admin", modules: ["team"] },
]) {
  test(`NPS respects role and modules ${scenario.role}-${scenario.modules}`, async ({
    page,
  }) => {
    await mock(page, scenario.role, scenario.modules);
    await expect(
      page.getByRole("button", { name: "Sair da conta" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "NPS e satisfação", exact: true }),
    ).toHaveCount(0);
  });
}
