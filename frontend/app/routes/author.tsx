import { data, useRevalidator } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { AuthorForms } from "../features/authors/author-forms";
import { authorIds, mergeAuthors } from "../features/pagination/merge-pages";
import { useProgressivePage } from "../features/pagination/use-progressive-page";
import { SurveyRouteError } from "../features/surveys/route-error";
import { httpFailure } from "../lib/api";
import { getAuthor, getAuthorForms } from "../lib/api.server";
import {
  ERROR_HEADERS,
  errorMessages,
  failureStatus,
  requireApiData,
} from "../lib/api-errors";
import type { Route } from "./+types/author";

export async function loader({ request, params, url }: Route.LoaderArgs) {
  const after = url.searchParams.get("after_id");
  if (
    after !== null &&
    (!/^\d{1,19}$/.test(after) ||
      /^0+$/.test(after) ||
      url.searchParams.getAll("after_id").length > 1)
  )
    requireApiData(httpFailure(422));
  const author = requireApiData(
    await getAuthor(params.authorId, { signal: request.signal }),
  );
  const result = await getAuthorForms(
    author.id,
    after === null ? {} : { after_id: after },
    { signal: request.signal },
  );
  const failure = result.ok ? null : result;
  return data(
    { author, page: result.ok ? result.data : null, after, failure },
    {
      status: failure ? failureStatus(failure) : 200,
      headers: failure
        ? ERROR_HEADERS
        : {
            "Cache-Control": "private, no-store",
            ...(after !== null ? { "X-Robots-Tag": "noindex, follow" } : {}),
          },
    },
  );
}
export default function Author({
  loaderData: { author, page, after, failure },
}: Route.ComponentProps) {
  const progressive = useProgressivePage({
    page,
    identity: `author:${author.id}`,
    merge: mergeAuthors,
    ids: authorIds,
  });
  const displayed = progressive.page;
  const path = `/authors/${author.id}`;
  const revalidator = useRevalidator();
  return (
    <PageContainer>
      <title>{`${author.name} — Contributions — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Consultez les contributions publiques de ${author.name} aux formulaires du Grand Débat National.`}
      />
      <link
        rel="canonical"
        href={`https://cahierdedoleances.fr${path}${after === null ? "" : `?${new URLSearchParams({ after_id: after })}`}`}
      />
      {(failure || after !== null) && (
        <meta
          name="robots"
          content={failure ? "noindex, nofollow" : "noindex, follow"}
        />
      )}
      <h1>{author.name}</h1>
      <p className={css({ textStyle: "documentMetadata", mb: "8" })}>
        Contributions publiques au Grand Débat National
      </p>
      {failure && (
        <section aria-label="Erreur de chargement">
          <Alert variant="error" announcement="assertive">
            {errorMessages[failure.kind]}
          </Alert>
          <form
            method="get"
            action={path}
            onSubmit={(event) => {
              event.preventDefault();
              void revalidator.revalidate();
            }}
          >
            {after !== null && (
              <input type="hidden" name="after_id" value={after} />
            )}
            <Button type="submit" loading={revalidator.state !== "idle"}>
              Réessayer
            </Button>
          </form>
        </section>
      )}
      {displayed && (
        <AuthorForms
          page={displayed}
          path={path}
          after={after}
          onMore={progressive.loadMore}
          pending={progressive.pending}
        />
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
