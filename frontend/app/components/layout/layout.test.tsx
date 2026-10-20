import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import { Footer } from "./footer";
import { Header } from "./header";
import { PageContainer } from "./page-container";

it("identifie l'accueil actif et propose les destinations disponibles", () => {
  render(
    <MemoryRouter>
      <Header />
      <main>
        <PageContainer data-testid="container">Contenu</PageContainer>
      </main>
      <Footer />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("link", { name: "Accueil — Cahier de doléances" }),
  ).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Recherche" })).toHaveAttribute(
    "href",
    "/recherche",
  );
  expect(screen.getByRole("link", { name: "Enquêtes" })).toHaveAttribute(
    "href",
    "/enquetes",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByTestId("container")).toHaveTextContent("Contenu");
  expect(screen.getByRole("contentinfo")).toHaveTextContent(
    "© Cahier de doléances",
  );
});

it("indique la page Enquêtes active", () => {
  render(
    <MemoryRouter initialEntries={["/enquetes"]}>
      <Header />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Enquêtes" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

it("situe un formulaire dans la section Enquêtes sans le déclarer comme la page Enquêtes", () => {
  render(
    <MemoryRouter initialEntries={["/forms/9007199254740993"]}>
      <Header />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Enquêtes" })).toHaveAttribute(
    "aria-current",
    "location",
  );
});

it("indique la recherche active même avec des paramètres", () => {
  render(
    <MemoryRouter initialEntries={["/recherche?q=école&cursor=opaque"]}>
      <Header />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Recherche" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
