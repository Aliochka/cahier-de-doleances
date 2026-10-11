import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "./home";

test("presents the project and provides page metadata", () => {
  render(<Home />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Cahier de doléances" }),
  ).toBeVisible();
  expect(
    screen.getByText(/contributions citoyennes du Grand Débat National et/),
  ).toBeVisible();
  expect(document.title).toBe("Cahier de doléances — Les voix du Grand Débat");
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    "Explorez les contributions citoyennes du Grand Débat National avec Cahier de doléances.",
  );
});
