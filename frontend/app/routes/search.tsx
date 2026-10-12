import { useEffect, useState } from "react";
import { data, Form, useRevalidator } from "react-router";
import { css } from "../../styled-system/css";
import { EmptyState } from "../components/layout/data-states";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { SearchControls } from "../features/search/search-controls";
import {
  SearchResults,
  type SearchResultsData,
} from "../features/search/search-results";
import type { SearchState } from "../features/search/search-url";
import { SurveyRouteError } from "../features/surveys/route-error";
import { type ApiFailure, httpFailure } from "../lib/api";
import { searchAnswers, searchCatalog } from "../lib/api.server";
import { ERROR_HEADERS, errorMessages, failureStatus } from "../lib/api-errors";
import type { Route } from "./+types/search";

export async function loader({ request, url }: Route.LoaderArgs) {
  const query = url.searchParams;
  const raw = query.get("q") ?? "";
  const tab = query.get("tab") ?? "answers";
  const state: SearchState = {
    q: raw.trim(),
    tab: tab === "catalog" ? "catalog" : "answers",
    cursor: query.get("cursor"),
    cursor_forms: query.get("cursor_forms"),
    cursor_questions: query.get("cursor_questions"),
  };
  const duplicates = [
    "q",
    "tab",
    "cursor",
    "cursor_forms",
    "cursor_questions",
  ].some((key) => query.getAll(key).length > 1);
  const relevantCursors =
    state.tab === "answers"
      ? [state.cursor]
      : [state.cursor_forms, state.cursor_questions];
  const invalid =
    raw.length > 512 ||
    duplicates ||
    !["answers", "catalog"].includes(tab) ||
    relevantCursors.some(
      (cursor) => cursor !== null && (!cursor || cursor.length > 1024),
    );
  let failure: ApiFailure | null = invalid ? httpFailure(422) : null;
  let result: SearchResultsData | null = null;
  if (!failure && state.q) {
    if (state.tab === "answers") {
      const response = await searchAnswers(
        {
          q: state.q,
          ...(state.cursor !== null ? { cursor: state.cursor } : {}),
        },
        { signal: request.signal },
      );
      if (response.ok) result = { type: "answers", page: response.data };
      else failure = response;
    } else {
      const response = await searchCatalog(
        {
          q: state.q,
          ...(state.cursor_forms !== null
            ? { cursor_forms: state.cursor_forms }
            : {}),
          ...(state.cursor_questions !== null
            ? { cursor_questions: state.cursor_questions }
            : {}),
        },
        { signal: request.signal },
      );
      if (response.ok) result = { type: "catalog", page: response.data };
      else failure = response;
    }
  }
  return data(
    {
      state,
      result,
      failure,
      fieldError:
        raw.length > 512
          ? "La recherche est limitée à 512 caractères."
          : undefined,
    },
    {
      status: failure ? failureStatus(failure) : 200,
      headers: failure
        ? ERROR_HEADERS
        : {
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, follow",
          },
    },
  );
}

export default function Search({ loaderData: current }: Route.ComponentProps) {
  const { state, failure, result, fieldError } = current;
  const [draft, setDraft] = useState(state.q);
  useEffect(() => setDraft(state.q), [state.q]);
  const revalidator = useRevalidator();
  const [previous, setPrevious] = useState<{
    result: SearchResultsData;
    state: SearchState;
  } | null>(null);
  useEffect(() => {
    if (result) setPrevious({ result, state });
  }, [result, state]);
  // Keep only the last successful page in this mounted route, and label it after failure.
  const retained = failure ? previous : null;
  const visible = result ? { result, state } : retained;
  return (
    <PageContainer>
      <title>Recherche — Cahier de doléances</title>
      <meta
        name="description"
        content="Recherchez les réponses citoyennes, les questions et les enquêtes historiques du Grand Débat National."
      />
      <meta
        name="robots"
        content={failure ? "noindex, nofollow" : "noindex, follow"}
      />
      <link rel="canonical" href="https://cahierdedoleances.fr/recherche" />
      <h1>Recherche</h1>
      <p className={css({ maxWidth: "reading", mb: "6" })}>
        Explorez les réponses citoyennes ou retrouvez les questions et enquêtes
        du Grand Débat National.
      </p>
      <SearchControls
        state={state}
        draft={draft}
        onDraftChange={setDraft}
        error={fieldError}
      />
      {failure && (
        <section aria-label="Erreur de recherche" className={css({ mb: "8" })}>
          <h2>
            {["unavailable", "network", "configuration"].includes(failure.kind)
              ? "Service indisponible"
              : "La recherche n’a pas abouti"}
          </h2>
          <Alert variant="error" announcement="assertive">
            {errorMessages[failure.kind]}
          </Alert>
          <Form
            method="get"
            action="/recherche"
            onSubmit={(event) => {
              event.preventDefault();
              void revalidator.revalidate();
            }}
          >
            <input type="hidden" name="q" value={state.q} />
            <input type="hidden" name="tab" value={state.tab} />
            {state.tab === "answers" && state.cursor !== null && (
              <input type="hidden" name="cursor" value={state.cursor} />
            )}
            {state.tab === "catalog" && (
              <>
                {state.cursor_forms !== null && (
                  <input
                    type="hidden"
                    name="cursor_forms"
                    value={state.cursor_forms}
                  />
                )}
                {state.cursor_questions !== null && (
                  <input
                    type="hidden"
                    name="cursor_questions"
                    value={state.cursor_questions}
                  />
                )}
              </>
            )}
            <Button type="submit" loading={revalidator.state !== "idle"}>
              Réessayer
            </Button>
          </Form>
          {retained && (
            <p>
              Le lot précédent reste affiché : « {retained.state.q} »,{" "}
              {retained.state.tab === "answers"
                ? "Réponses"
                : "Questions et enquêtes"}
              .
            </p>
          )}
        </section>
      )}
      <p
        role="status"
        aria-label="État des résultats"
        aria-atomic="true"
        className={css({ color: "muted", mb: "4" })}
      >
        {result
          ? `${(result.type === "answers" ? result.page.items.length : result.page.forms.length + result.page.questions.length) === 0 ? "Aucun résultat" : "Résultats affichés"} pour « ${state.q} » — ${state.tab === "answers" ? "Réponses" : "Questions et enquêtes"}.`
          : failure
            ? "La recherche n’a pas abouti."
            : "Saisissez des mots-clés pour commencer."}
      </p>
      {!failure && !state.q && (
        <EmptyState>
          Saisissez des mots-clés pour commencer votre recherche.
        </EmptyState>
      )}
      {visible && (
        <SearchResults result={visible.result} state={visible.state} />
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
