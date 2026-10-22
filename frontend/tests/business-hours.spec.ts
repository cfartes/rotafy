import { test, expect } from "@playwright/test";

test("company admin configures weekly shifts and timezone", async ({
  page,
}) => {
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        full_name: "Admin",
        company_id: "company",
        is_active: true,
        enabled_modules: ["whatsapp"],
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        is_active: true,
      };
    if (path === "/company/whatsapp/hours") {
      if (route.request().method() === "PUT")
        saved = route.request().postDataJSON();
      body = saved || {
        enabled: true,
        timezone: "America/Sao_Paulo",
        intervals: [{ day: 0, start: "09:00", end: "18:00" }],
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Horários de atendimento humano" }),
  ).toBeVisible();
  await page
    .getByLabel("Fuso horário do atendimento")
    .selectOption("America/Manaus");
  await page.getByLabel("Início 1", { exact: true }).fill("08:00");
  await page.getByLabel("Término 1", { exact: true }).fill("12:00");
  await page.getByRole("button", { name: "Adicionar horário" }).click();
  await page.getByLabel("Início 2", { exact: true }).fill("13:00");
  await page.getByLabel("Término 2", { exact: true }).fill("17:00");
  await page
    .getByRole("button", { name: "Salvar horários de atendimento" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Horários de atendimento salvos.",
  );
  expect(saved).toEqual({
    enabled: true,
    timezone: "America/Manaus",
    intervals: [
      { day: 0, start: "08:00", end: "12:00" },
      { day: 0, start: "13:00", end: "17:00" },
    ],
  });
  const checkbox = page.getByRole("checkbox", {
    name: "Informar quando estivermos fora do horário de atendimento",
  });
  expect((await checkbox.boundingBox())!.width).toBeLessThanOrEqual(22);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("quality alert opens negative feedback and review clears the alert", async ({
  page,
}) => {
  let reviewed = false;
  const metrics = {
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
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "attendant",
        role: "attendant",
        full_name: "Equipe",
        company_id: "company",
        is_active: true,
        enabled_modules: ["whatsapp"],
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        is_active: true,
      };
    if (path === "/nps/quality")
      body = {
        total: reviewed ? 0 : 1,
        rows: reviewed
          ? []
          : [
              {
                id: "feedback1",
                contact_name: "Maria",
                phone: "+5547999999999",
                kind: "service",
                score: 4,
                comment: "Demorou para responder.",
                trip_name: null,
              },
            ],
      };
    if (path === "/nps/quality/feedback1/review") {
      reviewed = true;
      await route.fulfill({ status: 204 });
      return;
    }
    if (path === "/nps/report")
      body = {
        summary: metrics,
        by_kind: { service: metrics, trip: metrics },
        evolution: [],
        rows: [],
        total: 0,
        page: 1,
      };
    if (path === "/nps/settings")
      body = { service_enabled: true, trip_enabled: true };
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await expect(
    page.getByRole("button", { name: "Configurações", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Ver avaliações de qualidade" })
    .click();
  const inbox = page.getByRole("region", {
    name: "Análise da equipe de qualidade",
  });
  await expect(inbox).toContainText("Demorou para responder.");
  await inbox
    .getByRole("button", { name: "Marcar avaliação de Maria como analisada" })
    .click();
  await expect(inbox).toHaveCount(0);
  expect(reviewed).toBe(true);
});
