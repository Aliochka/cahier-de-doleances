import { useEffect, useState } from "react";
import {
  data,
  Form,
  redirect,
  useNavigation,
  useRevalidator,
} from "react-router";
import { css } from "../../styled-system/css";
import { LoadingState } from "../components/layout/data-states";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import styles from "../features/forms/results.module.css";
import { mergeSearch, searchIds } from "../features/pagination/merge-pages";
import { useProgressivePage } from "../features/pagination/use-progressive-page";
import { SearchControls } from "../features/search/search-controls";
import { SearchResults } from "../features/search/search-results";
import { type SearchState, searchUrl } from "../features/search/search-url";
import { SurveyRouteError } from "../features/surveys/route-error";
import {
  type ApiFailure,
  type HybridSearchPage,
  httpFailure,
} from "../lib/api";
import { search } from "../lib/api.server";
import { errorMessages, failureStatus } from "../lib/api-errors";
import type { Route } from "./+types/search";

const headers = {
  "Cache-Control": "private, no-store",
  "X-Robots-Tag": "noindex, follow",
};
export async function loader({ request, url }: Route.LoaderArgs) {
  const params = url.searchParams;
  const raw = params.get("q") ?? "";
  const size = params.get("page_size");
  const state: SearchState = {
    q: raw.normalize("NFC").trim(),
    cursor: params.get("cursor"),
    page_size: size === null ? 20 : Number(size),
  };
  const invalid =
    Array.from(raw).length > 512 ||
    [...params.keys()].some(
      (key) =>
        !["q", "cursor", "page_size"].includes(key) ||
        params.getAll(key).length !== 1,
    ) ||
    (size !== null && !/^(?:[1-9]|1[0-9]|20)$/.test(size)) ||
    (state.cursor !== null &&
      (!state.q || !state.cursor || state.cursor.length > 1024));
  let failure: ApiFailure | null = invalid ? httpFailure(422) : null;
  let result: HybridSearchPage | null = null;
  if (!failure && state.q) {
    const response = await search(
      {
        q: state.q,
        page_size: state.page_size,
        ...(state.cursor !== null ? { cursor: state.cursor } : {}),
      },
      { signal: request.signal },
    );
    if (response.ok) {
      if (
        response.data.q !== state.q ||
        response.data.page_size !== state.page_size
      )
        failure = { ok: false, kind: "invalid_response" };
      else {
        result = response.data;
        // Une seule redirection. Toutes les navigations suivantes portent déjà un curseur.
        if (state.cursor === null && result.first_cursor)
          throw redirect(searchUrl({ ...state, cursor: result.first_cursor }), {
            status: 303,
            headers,
          });
      }
    } else failure = response;
  }
  return data(
    {
      state,
      result,
      failure,
      fieldError:
        Array.from(raw).length > 512
          ? "La recherche est limitée à 512 caractères."
          : failure?.kind === "request"
            ? "Vérifiez votre question et les paramètres de recherche."
            : undefined,
    },
    { status: failure ? failureStatus(failure) : 200, headers },
  );
}

export default function Search({
  loaderData: { state, result, failure, fieldError },
}: Route.ComponentProps) {
  const progressive = useProgressivePage({
    page: result,
    identity: `search:${state.q}:${state.page_size}`,
    merge: mergeSearch,
    ids: searchIds,
  });
  const displayed = progressive.page;
  const visible =
    displayed && failure
      ? { ...displayed, has_next: false, next_cursor: null }
      : displayed;
  const [draft, setDraft] = useState(state.q);
  useEffect(() => setDraft(state.q), [state.q]);
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const pending =
    (navigation.state !== "idle" &&
      navigation.location?.pathname === "/recherche" &&
      !navigation.location.state?.progressiveFrom) ||
    revalidator.state !== "idle";
  const restart =
    failure?.kind === "expired" ||
    (failure?.kind === "request" && state.cursor !== null);
  return (
    <PageContainer>
      <title>Recherche — Cahier de doléances</title>
      <meta
        name="description"
        content="Retrouvez la parole citoyenne du Grand Débat national. Recherchez une question ou un sujet et découvrez les réponses dans leur contexte."
      />
      <meta name="robots" content="noindex, follow" />
      <link rel="canonical" href="https://cahierdedoleances.fr/recherche" />
      <div className={css({ maxWidth: "reading" })}>
        <h1 className={styles.title}>Rechercher dans les paroles citoyennes</h1>
        <p className={css({ mb: "6" })}>
          Une question, un sujet, une préoccupation : découvrez les réponses des
          participants au Grand Débat national, dans leur contexte d’origine.
        </p>
      </div>
      <SearchControls
        draft={draft}
        onDraftChange={setDraft}
        error={fieldError}
        pending={pending}
      />
      <div className={css({ maxWidth: "reading" })}>
        <LoadingState active={pending} />
      </div>
      {failure && (
        <section
          aria-label="Erreur de recherche"
          className={css({ maxWidth: "reading", mb: "8" })}
        >
          <h2 className={styles.questionTitle}>
            {failure.kind === "expired"
              ? "Cette sélection a expiré"
              : ["unavailable", "network", "configuration"].includes(
                    failure.kind,
                  )
                ? "Recherche indisponible"
                : "La recherche n’a pas abouti"}
          </h2>
          <Alert variant="error" announcement="assertive">
            {["server_timeout", "timeout"].includes(failure.kind)
              ? "La recherche prend trop de temps. Réessayez ou précisez votre question."
              : errorMessages[failure.kind]}
          </Alert>
          <Form method="get" action="/recherche" className={css({ mt: "4" })}>
            <input type="hidden" name="q" value={state.q} />
            {state.page_size !== 20 && (
              <input type="hidden" name="page_size" value={state.page_size} />
            )}
            {!restart && state.cursor && (
              <input type="hidden" name="cursor" value={state.cursor} />
            )}
            <Button type="submit" loading={pending}>
              {restart ? "Relancer la recherche" : "Réessayer"}
            </Button>
          </Form>
        </section>
      )}
      {!failure && !state.q && (
        <section
          aria-labelledby="search-welcome"
          className={css({
            maxWidth: "reading",
            borderTopWidth: "thin",
            borderColor: "border",
            py: "8",
          })}
        >
          <h2 id="search-welcome" className={styles.questionTitle}>
            Un point de départ pour écouter et comprendre
          </h2>
          <p>
            Demandez par exemple « Quelles difficultés rencontrent les habitants
            des zones rurales ? », ou saisissez simplement « Pouvoir d’achat ».
          </p>
          <p className={css({ mt: "4", color: "muted" })}>
            Chaque réponse est accompagnée de sa question. Vous pouvez ensuite
            lire la contribution complète pour retrouver le témoignage original.
          </p>
        </section>
      )}
      {visible && (
        <SearchResults
          results={visible}
          state={state}
          pending={progressive.pending}
          continuationError={!!failure}
          onMore={failure ? undefined : progressive.loadMore}
        />
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
