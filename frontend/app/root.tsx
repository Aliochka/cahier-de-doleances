import type { ReactNode } from "react";
import {
  Links,
  Outlet,
  Scripts,
  ScrollRestoration,
  useNavigation,
  useRevalidator,
} from "react-router";
import { css } from "../styled-system/css";
import type { Route } from "./+types/root";
import { LoadingState, RouteErrorState } from "./components/layout/data-states";
import { Footer } from "./components/layout/footer";
import { Header } from "./components/layout/header";
import { PageContainer } from "./components/layout/page-container";
import { apiPageHeaders } from "./lib/api-errors";
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
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  return (
    <>
      {(navigation.state !== "idle" || revalidator.state !== "idle") && (
        <PageContainer>
          <LoadingState
            active={navigation.state !== "idle" || revalidator.state !== "idle"}
          />
        </PageContainer>
      )}
      <Outlet />
    </>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  return (
    <PageContainer>
      <RouteErrorState error={error} />
    </PageContainer>
  );
}

export const headers = apiPageHeaders;
