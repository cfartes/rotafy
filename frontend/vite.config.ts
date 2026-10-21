import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import { execFileSync } from "node:child_process";

const release = process.env.APP_RELEASE || `git-${execFileSync("git", ["rev-parse", "--short=12", "HEAD"], { encoding: "utf8" }).trim()}`;

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(release) },
  plugins: [
    { name: "release-manifest", generateBundle() { this.emitFile({ type: "asset", fileName: "version.json", source: JSON.stringify({ version: release }) }); },
      configureServer(server) { server.middlewares.use("/version.json", (_request, response) => { response.setHeader("Cache-Control", "no-store"); response.setHeader("Content-Type", "application/json"); response.end(JSON.stringify({ version: release })); }); } },
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      injectRegister: "script",
      manifest: {
        name: "Nexus Rotafy",
        short_name: "Rotafy",
        description: "Viagens e embarque",
        lang: "pt-BR",
        start_url: "/",
        scope: "/",
        display: "standalone",
        theme_color: "#0A2540",
        background_color: "#f4f7fa",
        icons: [
          { src: "/pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,svg,webmanifest}"],
        globIgnores: ["documentacao/**"],
        navigateFallbackDenylist: [/^\/api\//, /^\/documentacao\//],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: false,
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { proxy: { "/api": "http://127.0.0.1:8018" } },
});
