import type { ReactNode } from "react";
import {
  Links,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLocation,
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
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link
          rel="preload"
          href="/fonts/special-elite-latin-400.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preload"
          href="/fonts/literata-latin-400.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
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
  const location = useLocation();
  const progressiveNavigation =
    typeof navigation.location?.state?.progressiveFrom === "string" &&
    navigation.location.pathname === location.pathname;
  const localSearchProgress =
    location.pathname === "/recherche" &&
    (!navigation.location || navigation.location.pathname === "/recherche");
  return (
    <>
      {!localSearchProgress &&
        !progressiveNavigation &&
        (navigation.state !== "idle" || revalidator.state !== "idle") && (
          <PageContainer>
            <LoadingState
              active={
                navigation.state !== "idle" || revalidator.state !== "idle"
              }
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
