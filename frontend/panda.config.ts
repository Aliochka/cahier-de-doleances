import { defineConfig } from "@pandacss/dev";

export default defineConfig({
  presets: ["@pandacss/preset-base", "@pandacss/preset-panda"],
  preflight: true,
  include: ["./app/**/*.{ts,tsx}"],
  exclude: [],
  outdir: "styled-system",
  jsxFramework: "react",
  theme: {
    extend: {
      tokens: {
        colors: {
          paper: { value: "#F4F1E5" },
          ink: { value: "#2B2A26" },
          blue: { value: "#203A8F" },
          stamp: { value: "#A83A3A" },
          metal: { value: "#C8C2B5" },
          archiveBackground: { value: "#f2f1ea" },
          archiveSurface: { value: "#fbfaf6" },
          archiveMuted: { value: "#6b6258" },
        },
        fonts: {
          body: { value: 'system-ui, -apple-system, "Segoe UI", sans-serif' },
          archive: {
            value: '"Special Elite", "Courier Prime", "Courier New", monospace',
          },
        },
        spacing: {
          1: { value: "0.25rem" },
          2: { value: "0.5rem" },
          3: { value: "0.75rem" },
          4: { value: "1rem" },
          6: { value: "1.5rem" },
          8: { value: "2rem" },
          10: { value: "2.5rem" },
        },
        fontSizes: {
          body: { value: "1rem" },
          title: { value: "clamp(2rem, 5vw, 3rem)" },
        },
        lineHeights: { body: { value: "1.6" }, title: { value: "1.2" } },
        radii: { panel: { value: "0.75rem" } },
        borders: { panel: { value: "1px solid {colors.metal}" } },
      },
      semanticTokens: {
        colors: {
          background: { value: "{colors.archiveBackground}" },
          surface: { value: "{colors.archiveSurface}" },
          text: { value: "{colors.ink}" },
          muted: { value: "{colors.archiveMuted}" },
          primary: { value: "{colors.blue}" },
          danger: { value: "{colors.stamp}" },
          border: { value: "{colors.metal}" },
        },
      },
      breakpoints: { sm: "40rem", md: "48rem", lg: "64rem" },
    },
  },
  globalCss: {
    html: { color: "text", background: "background", fontFamily: "body" },
    body: { margin: 0, fontSize: "body", lineHeight: "body" },
    a: { color: "primary", textDecoration: "underline" },
    ":focus-visible": {
      outline: "2px solid {colors.primary}",
      outlineOffset: "3px",
    },
  },
});
