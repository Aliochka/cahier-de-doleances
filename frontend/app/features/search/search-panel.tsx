import { useEffect, useState } from "react";
import { Form, useNavigation, useRevalidator } from "react-router";
import { css } from "../../../styled-system/css";
import { LoadingState } from "../../components/layout/data-states";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import type { ApiFailure, HybridSearchPage } from "../../lib/api";
import { errorMessages } from "../../lib/api-errors";
import styles from "../forms/results.module.css";
import { mergeSearch, searchIds } from "../pagination/merge-pages";
import { useProgressivePage } from "../pagination/use-progressive-page";
import { SearchControls } from "./search-controls";
import { SearchResults } from "./search-results";
import type { SearchState } from "./search-url";

export function SearchPanel({
  state,
  result,
  failure,
  fieldError,
  otherOnly = false,
}: {
  state: SearchState;
  result: HybridSearchPage | null;
  failure: ApiFailure | null;
  fieldError?: string;
  otherOnly?: boolean;
}) {
  const progressive = useProgressivePage({
    page: result,
    identity: `search:${state.path ?? "global"}:${state.q}:${state.page_size}`,
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
      navigation.location?.pathname === (state.path ?? "/recherche") &&
      !navigation.location.state?.progressiveFrom) ||
    revalidator.state !== "idle";
  const restart =
    failure?.kind === "expired" ||
    (failure?.kind === "request" && state.cursor !== null);
  return (
    <>
      <SearchControls
        path={state.path}
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
          <Form
            method="get"
            action={state.path ?? "/recherche"}
            className={css({ mt: "4" })}
          >
            {state.path && <input type="hidden" name="tab" value="search" />}
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
            {state.path
              ? "Rechercher parmi les réponses à cette question"
              : "Un point de départ pour écouter et comprendre"}
          </h2>
          <p className={css({ textStyle: "editorialBody" })}>
            {state.path &&
              (otherOnly
                ? "La recherche porte uniquement sur les précisions libres « Autre » de cette question. "
                : "La recherche porte uniquement sur les réponses à cette question. ")}
            Demandez par exemple « Quelles difficultés rencontrent les habitants
            des zones rurales ? », ou saisissez simplement « Pouvoir d’achat ».
          </p>
          <p
            className={css({
              textStyle: "editorialBody",
              mt: "4",
              color: "muted",
            })}
          >
            {state.path
              ? "Vous pouvez lire"
              : "Chaque réponse est accompagnée de sa question. Vous pouvez ensuite lire"}{" "}
            la contribution complète pour retrouver le témoignage original.
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
    </>
  );
}
