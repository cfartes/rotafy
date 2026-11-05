import { readFile } from "node:fs/promises";
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function setup(page: Page, role = "admin") {
  let deleted = false;
  const periods: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace("/api/v1", "");
    let body: unknown = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role,
        full_name: "Administrador",
        company_id: "company",
        is_active: true,
        enabled_modules: [
          "team",
          "fleet",
          "trips",
          "routes",
          "sales",
          "reports",
          "integrations",
        ],
      };
    if (path === "/company")
      body = {
        id: "company",
        trade_name: "Empresa Teste",
        slug: "empresa",
        is_active: true,
      };
    if (path === "/reports/management")
      body = {
        summary: {
          commercial_trips: 0,
          displacements: 0,
          occupancy_pct: null,
          confirmed_families: 0,
          confirmed_passengers: 0,
          confirmed_value_cents: 0,
          paid_value_cents: 0,
          unpaid_value_cents: 0,
          average_ticket_cents: null,
        },
        daily: [],
        vehicles: [],
        trip_statuses: [],
        reservation_statuses: [],
        ranking: [],
        upcoming: [],
      };
    if (path === "/users")
      body = Array.from({ length: 45 }, (_, i) => ({
        id: String(i),
        full_name: `Pessoa ${String(i + 1).padStart(2, "0")}`,
        email: `p${i}@example.com`,
        role: "attendant",
        is_active: true,
      }));
    if (path === "/audit")
      body = Array.from({ length: 41 }, (_, i) => ({
        id: String(i),
        created_at: "2026-11-05T12:00:00Z",
        actor_name: `Operador ${i}`,
        action: "route.created",
        target_name: `Rota ${i}`,
        actor_role: "admin",
      }));
    if (path === "/dashboard") {
      periods.push(url.search);
      body = {
        summary: {
          completed_trips: 12,
          running_trips: 2,
          scheduled_trips: 4,
          cancelled_trips: 1,
        },
        active_routes: 3,
        sales: {
          confirmed_reservations: 10,
          passengers: 22,
          reserved_cents: 123400,
          paid_cents: 100000,
        },
        ranking: [
          {
            id: "r1",
            name: "Rota da praia",
            completed_trips: 12,
            removed: false,
          },
        ],
        upcoming: [
          {
            id: "t1",
            name: "Próxima viagem",
            destination: "Navegantes",
            starts_at: "2026-11-07T12:00:00Z",
          },
        ],
      };
    }
    if (path === "/routes")
      body = deleted
        ? []
        : [
            {
              id: "r1",
              name: "Rota da praia",
              version: 1,
              is_active: true,
              mode: "one_way",
              completed_trips: 12,
              legs: [
                {
                  origin: "Blumenau",
                  destination: "Navegantes",
                  origin_uf: "SC",
                  destination_uf: "SC",
                  duration_minutes: 60,
                  stop_minutes: 0,
                  stops: [],
                },
              ],
            },
          ];
    if (path === "/routes/r1" && request.method() === "DELETE") {
      deleted = true;
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page
    .getByRole("button", { name: "Usar somente necessários", exact: true })
    .click();
  return periods;
}

test("visão geral gerencial sem equipe nem integração; rota excluída preserva a orientação de histórico", async ({
  page,
}) => {
  const periods = await setup(page);
  await expect(
    page.getByRole("heading", { name: "Resultado da operação" }),
  ).toBeVisible();
  await expect(
    page.locator(".stat-card").getByText("Viagens concluídas", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Passageiros reservados", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("R$ 1.234,00", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Pessoas da equipe" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Adicionar pessoa", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Integração com parceiros" }),
  ).toHaveCount(0);
  await page
    .getByLabel("Início do período", { exact: true })
    .fill("2026-10-01");
  await page.getByLabel("Fim do período", { exact: true }).fill("2026-10-31");
  await page.getByRole("button", { name: "Atualizar indicadores" }).click();
  await expect
    .poll(() =>
      periods.some(
        (p) => p.includes("start=2026-10-01") && p.includes("end=2026-10-31"),
      ),
    )
    .toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({
    path: "../artifacts/company-dashboard-desktop.png",
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
    path: "../artifacts/company-dashboard-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await page.getByRole("button", { name: "Rotas", exact: true }).click();
  await expect(
    page.getByText("12 viagens concluídas", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Excluir Rota", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "histórico serão preservados",
  );
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Rota da praia", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Excluir Rota", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirmar exclusão", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Rota da praia", exact: true }),
  ).toHaveCount(0);
});

test("tabelas mostram vinte registros, navegam até o último e reiniciam com busca", async ({
  page,
}) => {
  await setup(page);
  await page.getByRole("button", { name: "Equipe", exact: true }).click();
  const table = page.getByRole("table");
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await expect(table.getByText("Pessoa 01", { exact: true })).toBeVisible();
  await expect(table.getByText("Pessoa 21", { exact: true })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await expect(table.getByText("Pessoa 21", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await expect(table.locator("tbody tr")).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "Próxima página", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Anterior", exact: true }).click();
  await page.getByRole("textbox", { name: "Buscar pessoa" }).fill("Pessoa 01");
  await expect(table.locator("tbody tr")).toHaveCount(1);
  await expect(table.getByText("Pessoa 01", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Buscar pessoa" }).fill("");
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await expect(
    page.getByRole("button", { name: "Anterior", exact: true }),
  ).toBeDisabled();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Atividades", exact: true }).click();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(20);
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(1);
});

test("relatórios paginam sem limitar o download completo", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/reports/operations?**", (route) =>
    route.fulfill({
      json: {
        generated_at: "2026-11-05T12:00:00Z",
        trips: [],
        reservations: [],
        presence: [],
        occupancy: Array.from({ length: 41 }, (_, i) => ({
          trip_name: `Viagem ${i + 1}`,
          vehicle_name: "Ônibus",
          leg_position: 1,
          origin: "Blumenau",
          destination: "Navegantes",
          capacity: 40,
          confirmed: 2,
          held: 0,
          available: 38,
        })),
      },
    }),
  );
  await page.route("**/api/v1/reports/export?**", (route) =>
    route.fulfill({
      contentType: "text/csv",
      headers: { "Content-Disposition": "attachment; filename=relatorio.csv" },
      body:
        "viagem\n" +
        Array.from({ length: 41 }, (_, i) => `Viagem ${i + 1}`).join("\n"),
    }),
  );
  await page.getByRole("button", { name: "Relatórios", exact: true }).click();
  await page.getByRole("button", { name: "Ocupação", exact: true }).click();
  const table = page.getByRole("table");
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await page
    .getByRole("button", { name: "Próxima página", exact: true })
    .click();
  await expect(table.getByText("Viagem 21", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportar CSV completo", exact: true })
    .click();
  expect(
    (await readFile((await (await download).path())!, "utf8")).split("\n"),
  ).toHaveLength(42);
});
