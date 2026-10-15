import { test, expect } from "@playwright/test";

test("nova senha exige oito caracteres, maiúscula e caractere especial", async ({
  page,
}) => {
  await page.route("**/api/v1/public/plans", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto("/cadastro");
  const password = page.getByLabel("Senha inicial", { exact: true });
  for (const value of ["Abcdef!", "abcdefg!", "Abcdefgh", "Abcdefg "]) {
    await password.fill(value);
    expect(
      await password.evaluate((el: HTMLInputElement) => el.checkValidity()),
    ).toBeFalsy();
  }
  for (const value of ["Abcdefg!", "Ábcdefg!", "Abcdefg€"]) {
    await password.fill(value);
    expect(
      await password.evaluate((el: HTMLInputElement) => el.checkValidity()),
    ).toBeTruthy();
  }
});

test("cada campo mantém sua própria opção de visualização", async ({
  page,
}) => {
  await page.route("**/api/v1/public/plans", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto("/cadastro");
  const password = page.getByLabel("Senha inicial", { exact: true });
  const confirmation = page.getByLabel("Confirmar senha", { exact: true });
  await password.fill("Senha de teste 123!");
  await confirmation.fill("Senha de teste 123!");
  await page
    .getByRole("button", { name: "Mostrar senha", exact: true })
    .first()
    .click();
  await expect(password).toHaveAttribute("type", "text");
  await expect(confirmation).toHaveAttribute("type", "password");
});

test("mostrar e ocultar senha preserva valor e não envia o formulário", async ({
  page,
}) => {
  let loginRequests = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (route.request().url().endsWith("/auth/login")) loginRequests++;
    await route.fulfill({ status: 401, json: {} });
  });
  await page.goto("/");
  const password = page.getByLabel("Senha", { exact: true });
  await password.fill("Senha de teste 123!");
  await expect(password).toHaveAttribute("type", "password");
  await page
    .getByRole("button", { name: "Mostrar senha", exact: true })
    .click();
  await expect(password).toHaveAttribute("type", "text");
  await expect(password).toHaveValue("Senha de teste 123!");
  await page
    .getByRole("button", { name: "Ocultar senha", exact: true })
    .click();
  await expect(password).toHaveAttribute("type", "password");
  await expect(password).toHaveValue("Senha de teste 123!");
  expect(loginRequests).toBe(0);
});
