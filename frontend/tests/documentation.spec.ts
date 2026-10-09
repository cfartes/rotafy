import { test, expect } from "@playwright/test";

test("central pública permite consultar e baixar os materiais sem autenticação", async ({
  page,
  request,
}) => {
  let authRequests = 0;
  await page.route("**/api/v1/auth/me", async (route) => {
    authRequests++;
    await route.fulfill({ status: 401, body: "{}" });
  });
  await page.goto("/ajuda");
  await expect(page.getByRole("heading", { name: /Conheça/ })).toBeVisible();
  expect(authRequests).toBe(0);
  for (const filename of [
    "manual.pdf",
    "apresentacao.pdf",
    "apresentacao.pptx",
  ]) {
    const response = await request.get(`/documentacao/${filename}`);
    expect(response.ok()).toBeTruthy();
    const bytes = await response.body();
    expect(bytes.subarray(0, filename.endsWith("pdf") ? 4 : 2).toString()).toBe(
      filename.endsWith("pdf") ? "%PDF" : "PK",
    );
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("manual oferece busca, navegação e leitura em celular", async ({
  page,
}) => {
  await page.goto("/documentacao/manual.html");
  await expect(page.locator(".chapter")).toHaveCount(26);
  const search = page.locator('input[type="search"]');
  await search.fill("csv/xlsx");
  const matches = await page.locator(".chapter:visible").count();
  expect(matches).toBeGreaterThan(0);
  expect(matches).toBeLessThan(26);
  await search.fill("zzzzinexistente");
  await expect(page.locator(".chapter:visible")).toHaveCount(0);
  await search.fill("");
  await expect(page.locator(".chapter:visible")).toHaveCount(26);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("apresentação disponibiliza os vinte slides e downloads", async ({
  page,
}) => {
  await page.goto("/documentacao/apresentacao.html");
  await expect(page.locator(".slide")).toHaveCount(20);
  await expect(page.locator('a[href="apresentacao.pdf"]')).toBeVisible();
  await expect(page.locator('a[href="apresentacao.pptx"]')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
