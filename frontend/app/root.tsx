import type { ReactNode } from "react";
import {
  isRouteErrorResponse,
  Links,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import { css } from "../styled-system/css";
import type { Route } from "./+types/root";
import { Footer } from "./components/layout/footer";
import { Header } from "./components/layout/header";
import { PageContainer } from "./components/layout/page-container";
import "./styles/global.css";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:," />
        <Links />
      </head>
      <body>
        <a
          href="#main-content"
          className={css({
            position: "fixed",
            top: "2",
            left: "2",
            transform: "translateY(-200%)",
            zIndex: "modal",
            background: "surface",
            p: "3",
            border: "panel",
            _focus: { transform: "translateY(0)" },
          })}
        >
          Aller au contenu principal
        </a>
        <Header />
        <main
          id="main-content"
          tabIndex={-1}
          className={css({ flex: "1", minWidth: 0 })}
        >
          {children}
        </main>
        <Footer />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const missing = isRouteErrorResponse(error) && error.status === 404;
  const title = missing ? "Page introuvable" : "Une erreur est survenue";
  return (
    <PageContainer>
      <title>{`${title} — Cahier de doléances`}</title>
      <meta name="robots" content="noindex, nofollow" />
      <h1>{title}</h1>
      <p>
        {missing
          ? "Cette page n’existe pas."
          : "Veuillez réessayer dans quelques instants."}
      </p>
      <a href="/">Retour à l’accueil</a>
    </PageContainer>
  );
}
