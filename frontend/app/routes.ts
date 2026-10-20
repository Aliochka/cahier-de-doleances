import { index, type RouteConfig, route } from "@react-router/dev/routes";

if (process.env.FRONTEND_TEST_ROUTES === "1" && process.env.NETLIFY) {
  throw new Error("Test routes must never be built on Netlify");
}

export default [
  index("routes/home.tsx"),
  route("recherche", "routes/search.tsx"),
  route("enquetes", "routes/surveys.tsx"),
  route("authors/:authorId", "routes/author.tsx"),
  route(
    "forms/:formId/contributions/:contributionId",
    "routes/contribution.tsx",
  ),
  route("forms/:formId/contributions", "routes/form-contributions.tsx"),
  route("forms/:formId/dashboard", "routes/dashboard.tsx"),
  route("forms/:formId", "routes/form.tsx"),
  route("questions/:questionKey", "routes/question.tsx"),
  ...(process.env.FRONTEND_TEST_ROUTES === "1"
    ? [route("_test/api", "../tests/routes/api.tsx")]
    : []),
  ...(process.env.NODE_ENV === "development"
    ? [route("dev/components", "routes/dev.components.tsx")]
    : []),
] satisfies RouteConfig;
