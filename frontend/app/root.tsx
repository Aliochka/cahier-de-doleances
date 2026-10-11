import type { ReactNode } from "react";
import {
  isRouteErrorResponse,
  Links,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import type { Route } from "./+types/root";
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
        {children}
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
