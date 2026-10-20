import { RouterContextProvider } from "react-router";
import { expect, it, vi } from "vitest";
import { getForm } from "../lib/api.server";
import { loader } from "./dashboard";

vi.mock("../lib/api.server", () => ({ getForm: vi.fn() }));
it("redirige en 308 sans appel API et conserve les paramètres historiques", () => {
  const url = new URL(
    "http://localhost/forms/9007199254740995/dashboard?contrib=2",
  );
  const response = loader({
    params: { formId: "9007199254740995" },
    url,
    request: new Request(url),
    context: new RouterContextProvider(),
    pattern: "/forms/:formId/dashboard",
  });
  expect(response.status).toBe(308);
  expect(response.headers.get("Location")).toBe(
    "/forms/9007199254740995?contrib=2",
  );
  expect(getForm).not.toHaveBeenCalled();
});
