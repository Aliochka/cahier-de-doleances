import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: "http://127.0.0.1:4173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "pnpm start:test",
      url: "http://127.0.0.1:4177",
      env: {
        PORT: "4177",
        HOST: "127.0.0.1",
        API_BASE_URL: "http://127.0.0.1:1",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "node tests/mock-api.mjs",
      url: "http://127.0.0.1:4176/reset",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm start:test",
      url: "http://127.0.0.1:4175",
      env: {
        PORT: "4175",
        HOST: "127.0.0.1",
        API_BASE_URL: "http://127.0.0.1:4176",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm start",
      url: "http://127.0.0.1:4173",
      env: { PORT: "4173", HOST: "127.0.0.1" },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm dev --port 4174",
      url: "http://127.0.0.1:4174/dev/components",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
