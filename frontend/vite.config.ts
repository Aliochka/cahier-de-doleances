import netlifyReactRouter from "@netlify/vite-plugin-react-router";
import pandacss from "@pandacss/vite";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [pandacss(), reactRouter(), netlifyReactRouter()],
  // React Router uses Vite preview for prerendering during `build`.
  // Use the same IPv4 loopback address for listening and requests in Docker.
  preview: { host: "127.0.0.1" },
});
