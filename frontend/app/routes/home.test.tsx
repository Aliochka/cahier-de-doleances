import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, test } from "vitest";
import Home from "./home";

test("presents the project and provides page metadata", () => {
  render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("heading", { level: 1, name: "Cahier de doléances" }),
  ).toBeVisible();
  expect(screen.getByText(/Des paroles citoyennes à découvrir/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Explorer les enquêtes" }),
  ).toHaveAttribute("href", "/enquetes");
  expect(
    screen.getByRole("link", { name: "Rechercher dans les contributions" }),
  ).toHaveAttribute("href", "/recherche");
  expect(document.title).toBe("Cahier de doléances — Les paroles citoyennes");
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    "Explorez les enquêtes et recherchez dans les contributions citoyennes avec Cahier de doléances.",
  );
});
