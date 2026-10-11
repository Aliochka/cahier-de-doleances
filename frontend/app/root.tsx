import type { ReactNode } from "react";
import {
  isRouteErrorResponse,
  Links,
  Outlet,
  Scripts,
  ScrollRestoration,
  useNavigation,
  useRevalidator,
} from "react-router";
import { css } from "../styled-system/css";
import type { Route } from "./+types/root";
import { ErrorState, LoadingState } from "./components/layout/data-states";
import { Footer } from "./components/layout/footer";
import { Header } from "./components/layout/header";
import { PageContainer } from "./components/layout/page-container";
import type { ApiErrorKind } from "./lib/api";
import { ERROR_HEADERS, errorMessages } from "./lib/api-errors";
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
  const revalidator = useRevalidator();
  let kind: ApiErrorKind = "application";
  if (isRouteErrorResponse(error)) {
    const payload: unknown = error.data;
    if (
      typeof payload === "object" &&
      payload !== null &&
      "kind" in payload &&
      typeof payload.kind === "string" &&
      Object.hasOwn(errorMessages, payload.kind)
    ) {
      // The own-key check restricts this value to our public, safe error taxonomy.
      kind = payload.kind as ApiErrorKind;
    } else if (error.status === 404) kind = "missing";
    else if (error.status === 503) kind = "unavailable";
  }
  return (
    <PageContainer>
      <ErrorState
        kind={kind}
        retry={() => void revalidator.revalidate()}
        pending={revalidator.state !== "idle"}
      />
      <LoadingState active={revalidator.state !== "idle"} />
    </PageContainer>
  );
}

export function headers({ errorHeaders, loaderHeaders }: Route.HeadersArgs) {
  const headers = new Headers(errorHeaders ?? loaderHeaders);
  if (errorHeaders) {
    for (const [name, value] of Object.entries(ERROR_HEADERS))
      headers.set(name, value);
  }
  return headers;
}
