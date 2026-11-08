import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { ListNavigation } from "../features/pagination/list-navigation";
import { contributionStyles } from "../features/contributions/contribution-presentation";
import { SurveyRouteError } from "../features/surveys/route-error";
import { documentaryCatalogue } from "../lib/api.server";
import { localPreviewRequest } from "../lib/local-preview.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/historical-catalogue";

export async function loader({ request, url }: Route.LoaderArgs) {
  const raw = url.searchParams.get("page") ?? "1";
  if (
    !/^[1-9]\d{0,3}$/.test(raw) ||
    [...url.searchParams.keys()].some(
      (k) => k !== "page" || url.searchParams.getAll(k).length !== 1,
    )
  )
    throw data({ kind: "request" }, { status: 422 });
  return data(
    requireApiData(
      await documentaryCatalogue(Number(raw), {
        signal: request.signal,
        preview: localPreviewRequest(request),
      }),
    ),
    {
      headers: {
        "Cache-Control": "private, no-store",
        "X-Robots-Tag": "noindex, nofollow",
      },
    },
  );
}
export default function Catalogue({ loaderData: page }: Route.ComponentProps) {
  return (
    <PageContainer>
      <title>Cahiers de doléances de 1789 — Catalogue</title>
      <meta name="robots" content="noindex, nofollow" />
      <p className={css({ textStyle: "documentNavigation", mb: "6" })}>
        <Link to="/parcourir">← Parcourir les corpus</Link>
      </p>
      <h1 className={css({ textStyle: "documentTitle", mb: "6" })}>
        Cahiers de doléances — 1789
      </h1>
      <p
        className={css({
          textStyle: "editorialBody",
          maxWidth: "reading",
          mb: "6",
        })}
      >
        Les cahiers sont présentés dans l’ordre documentaire de l’édition des
        Archives parlementaires.
      </p>
      {page.preview && (
        <Alert variant="warning">
          Aperçu local. Les cahiers ne sont pas publiés.
        </Alert>
      )}
      <p className={contributionStyles.metadata}>
        {page.total} cahiers · Page {page.page}
      </p>
      <ol
        className={contributionStyles.list}
        aria-label="Catalogue des cahiers"
      >
        {page.items.map((d) => (
          <li key={d.document_id} className={contributionStyles.entry}>
            <h2 className={contributionStyles.question}>
              <Link to={d.url}>{d.title}</Link>
            </h2>
            {(d.place || d.orders.length > 0) && (
              <p className={contributionStyles.metadata}>
                {[d.place, ...d.orders].filter(Boolean).join(" · ")}
              </p>
            )}
            <details className={contributionStyles.metadata}>
              <summary>Référence historique</summary>
              <p className={css({ mt: "2" })}>{d.reference}</p>
            </details>
          </li>
        ))}
      </ol>
      <ListNavigation
        label="Pagination du catalogue"
        previous={page.page > 1 ? `?page=${page.page - 1}` : null}
        first={page.page > 1 ? "?page=1" : null}
        next={page.has_next ? `?page=${page.page + 1}` : null}
        nextLabel="Cahiers suivants →"
      />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
