import { test, expect } from "@playwright/test";

test("APK publishing retries a timed-out block and confirms the new release", async ({ page }) => {
  const id = "12345678-1234-4234-8234-123456789012";
  const offsets: number[] = [];
  let lostResponse = false, published = false;
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    let data: any = [];
    if (path === "/auth/me") data = { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true };
    if (path === "/nexus/integrations") data = { version: 1, openwa_key_configured: true, resend_key_configured: true, email_from: "nexus@example.com" };
    if (path === "/nexus/mobile-release") data = published ? [{ version: "1.8.0", build: 13, package_id: "app.rotafy", sha256: "a".repeat(64), download_url: "/api/v1/public/mobile/download?build=13", published_at: "2026-10-21T12:00:00Z" }] : [];
    if (path === "/nexus/mobile-release/uploads") data = { id, chunk_bytes: 16 };
    if (path === `/nexus/mobile-release/uploads/${id}`) {
      const offset = Number(url.searchParams.get("offset")); offsets.push(offset);
      if (!lostResponse) { lostResponse = true; await route.fulfill({ status: 504, body: "Gateway Timeout" }); return; }
      data = { offset: offset + (route.request().postDataBuffer()?.length || 0) };
    }
    if (path.endsWith("/complete")) { published = true; data = { version: "1.8.0", build: 13 }; }
    await route.fulfill({ json: data });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByLabel("Novo APK Android").setInputFiles({ name: "rotafy-1.8.0.apk", mimeType: "application/vnd.android.package-archive", buffer: Buffer.alloc(48, 1) });
  await page.getByRole("button", { name: "Publicar atualização Android", exact: true }).click();
  await expect(page.getByText(/Versão 1.8.0 publicada/)).toBeVisible();
  expect(offsets).toEqual([0, 0, 16, 32]);
  await expect(page.getByText("Versão disponível: 1.8.0 · compilação 13")).toBeVisible();
});

test("a proxy error gives an HTTP code instead of a generic upload failure", async ({ page }) => {
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/uploads")) { await route.fulfill({ status: 413, body: "Payload Too Large" }); return; }
    const data = path.endsWith("/auth/me") ? { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true } : path.endsWith("/nexus/integrations") ? { version: 1, openwa_key_configured: true, resend_key_configured: true, email_from: "nexus@example.com" } : [];
    await route.fulfill({ json: data });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await page.getByLabel("Novo APK Android").setInputFiles({ name: "release.apk", mimeType: "application/vnd.android.package-archive", buffer: Buffer.alloc(1) });
  await page.getByRole("button", { name: "Publicar atualização Android", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("HTTP 413");
});
