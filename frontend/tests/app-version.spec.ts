import { test, expect } from "@playwright/test";

test("a newer web release offers an update without reloading automatically", async ({ page }) => {
  await page.route("**/api/v1/**", route => route.fulfill({ json: route.request().url().endsWith("/auth/me") ? { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true } : [] }));
  await page.route("**/version.json?*", route => route.fulfill({ json: { version: "test-new-release" } }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Atualizar aplicativo", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "Atualizar aplicativo", exact: true }).click();
  await expect(page).not.toHaveURL(/_v=/);
  await expect(page.getByRole("button", { name: "Atualizar aplicativo", exact: true })).toBeEnabled();
});

test("failure to check the version preserves access without a false update warning", async ({ page }) => {
  await page.route("**/api/v1/**", route => route.fulfill({ json: route.request().url().endsWith("/auth/me") ? { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true } : [] }));
  await page.route("**/version.json?*", route => route.abort());
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Atualizar aplicativo", exact: true })).toHaveCount(0);
  await expect(page.locator("body")).not.toBeEmpty();
});
