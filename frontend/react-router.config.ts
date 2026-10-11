import type { Config } from "@react-router/dev/config";

export default {
  ssr: true,
  buildDirectory:
    process.env.FRONTEND_TEST_ROUTES === "1" ? "build-test" : "build",
  prerender: ["/"],
} satisfies Config;
