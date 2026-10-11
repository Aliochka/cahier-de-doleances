import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import { Footer } from "./footer";
import { Header } from "./header";
import { PageContainer } from "./page-container";

it("identifie l'accueil actif et annonce les destinations à venir sans faux liens", () => {
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
  for (const name of ["Recherche", "Enquêtes"]) {
    const destination = screen.getByText(name);
    expect(destination).toHaveAttribute("aria-disabled", "true");
    expect(destination).not.toHaveAttribute("href");
  }
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByTestId("container")).toHaveTextContent("Contenu");
  expect(screen.getByRole("contentinfo")).toHaveTextContent(
    "© Cahier de doléances",
  );
});
