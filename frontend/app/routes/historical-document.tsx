import { useEffect } from "react";
import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { DocumentNavigation } from "../components/layout/document-navigation";
import { Alert } from "../components/ui/alert";
import { contributionStyles } from "../features/contributions/contribution-presentation";
import { SurveyRouteError } from "../features/surveys/route-error";
import { documentaryReading } from "../lib/api.server";
import { localPreviewRequest } from "../lib/local-preview.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/historical-document";

export async function loader({ request, url, params }: Route.LoaderArgs) {
  if (
    [...url.searchParams.keys()].some(
      (k) => k !== "unit" || url.searchParams.getAll(k).length !== 1,
    )
  )
    throw data({ kind: "request" }, { status: 422 });
  return data(
    requireApiData(
      await documentaryReading(
        params.release,
        params.documentId,
        url.searchParams.get("unit"),
        { signal: request.signal, preview: localPreviewRequest(request) },
      ),
    ),
    {
      headers: {
        "Cache-Control": "private, no-store",
        "X-Robots-Tag": "noindex, nofollow",
      },
    },
  );
}
export default function HistoricalDocument({
  loaderData: d,
}: Route.ComponentProps) {
  const anchor = d.blocks.find((b) => b.anchor)?.anchor;
  useEffect(() => {
    if (anchor)
      document.getElementById(anchor)?.scrollIntoView({ block: "start" });
  }, [anchor]);
  const navigation = {
    label: "Navigation entre cahiers",
    previous: d.previous,
    next: d.next,
    previousLabel: "← Cahier précédent",
    nextLabel: "Cahier suivant →",
  };
  return (
    <PageContainer>
      <title>{d.title} — Cahier de doléances</title>
      <meta name="robots" content="noindex, nofollow" />
      <p className={css({ textStyle: "documentNavigation", mb: "6" })}>
        <Link to="/parcourir/1789">← Catalogue des cahiers</Link>
      </p>
      <article className={css({ maxWidth: "reading" })}>
        <header>
          <p className={contributionStyles.metadata}>
            Cahiers de doléances — 1789
          </p>
          <h1
            className={css({
              textStyle: "documentTitle",
              my: "6",
              overflowWrap: "anywhere",
            })}
          >
            {d.title}
          </h1>
          {(d.place || d.orders.length > 0) && (
            <p className={contributionStyles.metadata}>
              {[d.place, ...d.orders].filter(Boolean).join(" · ")}
            </p>
          )}
          {d.preview && (
            <Alert variant="warning">
              Aperçu local. Ce cahier n’est pas publié.
            </Alert>
          )}
          {d.warnings.map((w) => (
            <Alert key={w.code} variant="warning">
              {w.message}
            </Alert>
          ))}
        </header>
        <DocumentNavigation {...navigation} />
        {anchor && (
          <p className={css({ textStyle: "documentMetadata", mb: "4" })}>
            Le passage retrouvé est surligné dans le texte intégral.
          </p>
        )}
        <section
          aria-label="Texte intégral du cahier"
          className={contributionStyles.reading}
        >
          {d.blocks.map((b) =>
            b.anchor ? (
              <mark
                key={b.anchor}
                id={b.anchor}
                className={css({
                  background: "warningSurface",
                  color: "text",
                  scrollMarginTop: "12",
                })}
              >
                {b.text}
              </mark>
            ) : (
              <span key={b === d.blocks[0] ? "prefix" : "suffix"}>
                {b.text}
              </span>
            ),
          )}
        </section>
        <DocumentNavigation {...navigation} />
        <footer
          className={css({
            borderTopWidth: "thin",
            borderColor: "border",
            pt: "6",
            mt: "8",
          })}
        >
          <h2 className={css({ textStyle: "documentSection", mb: "4" })}>
            Sources et référence
          </h2>
          {d.source_title !== d.title && (
            <p className={contributionStyles.metadata}>
              Titre source : {d.source_title}
            </p>
          )}
          <p className={contributionStyles.metadata}>{d.reference}</p>
          <ul
            className={css({
              mt: "4",
              display: "grid",
              gap: "3",
              textStyle: "documentLink",
            })}
          >
            {d.sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.label} (nouvel onglet)
                </a>
              </li>
            ))}
          </ul>
          <p className={css({ textStyle: "documentMetadata", mt: "5" })}>
            Transcription Stanford conservée sans correction. Les passages
            servent au repérage dans le texte ; ils ne sont pas des articles
            historiques autonomes.
          </p>
        </footer>
      </article>
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
