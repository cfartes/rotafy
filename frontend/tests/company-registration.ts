import type { Page } from "@playwright/test";

export async function openCompanyRegistration(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        email: "nexus@example.com",
        is_active: true,
        company_id: null,
      },
    }),
  );
  await page.route("**/api/v1/nexus/companies", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [] })
      : route.fallback(),
  );
  await page.route("**/api/v1/audit", (route) => route.fulfill({ json: [] }));
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Nova empresa", exact: true }).click();
}
