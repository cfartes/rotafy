import { test, expect } from "@playwright/test";

test("cadastro exige todos os campos e explica o identificador sem caracteres especiais", async ({
  page,
}) => {
  await page.route("**/api/v1/public/plans", (route) =>
    route.fulfill({
      json: [
        {
          id: "10000000-0000-4000-8000-000000000001",
          name: "Basic",
          price_cents: 9900,
          included_trips: 10,
          extra_trip_cents: 1000,
        },
      ],
    }),
  );
  await page.goto("/cadastro");
  await expect(
    page.getByText("Todos os campos deste cadastro são obrigatórios.", {
      exact: false,
    }),
  ).toBeVisible();
  const fields = page.locator('form input:not([type="hidden"]), form select');
  for (const field of await fields.all())
    expect(
      await field.evaluate((el: HTMLInputElement) => el.required),
    ).toBeTruthy();
  const slug = page.getByLabel("Identificador de acesso");
  for (const value of [
    "empresa teste",
    "empresa_teste",
    "empresa-teste",
    "empresa@teste",
    "Empresateste",
    "empresáteste",
    " empresateste ",
  ]) {
    await slug.fill(value);
    expect(
      await slug.evaluate((el: HTMLInputElement) => el.checkValidity()),
    ).toBeFalsy();
  }
  await slug.fill("empresateste123");
  expect(
    await slug.evaluate((el: HTMLInputElement) => el.checkValidity()),
  ).toBeTruthy();
  await expect(page.locator("#company-slug-help")).toContainText(
    "Não use espaços",
  );
});
