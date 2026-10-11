import { index, type RouteConfig, route } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  ...(process.env.NODE_ENV === "development"
    ? [route("dev/components", "routes/dev.components.tsx")]
    : []),
] satisfies RouteConfig;
