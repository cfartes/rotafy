import { test, expect } from "@playwright/test";

test("help links to the APK version actually published on the VPS", async ({ page }) => {
  await page.route("**/api/v1/public/mobile-version?*", route => route.fulfill({ json: { android: { version: "1.7.0", download_url: "/api/v1/public/mobile/download?package_id=br.com.nexusdataanalytics.rotafy&build=12" } } }));
  await page.goto("/ajuda");
  await expect(page.getByRole("link", { name: "Baixar APK Android", exact: true })).toHaveAttribute("href", "/api/v1/public/mobile/download?package_id=br.com.nexusdataanalytics.rotafy&build=12");
  await expect(page.getByText("1.7.0", { exact: true })).toBeVisible();
});

test("help does not advertise a broken download when no APK is published", async ({ page }) => {
  await page.route("**/api/v1/public/mobile-version?*", route => route.fulfill({ json: { android: null } }));
  await page.goto("/ajuda");
  await expect(page.getByRole("status")).toContainText("assim que a Nexus publicar");
  await expect(page.getByRole("link", { name: "Baixar APK Android", exact: true })).toHaveCount(0);
});
