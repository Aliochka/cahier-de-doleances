import { useEffect, useState } from "react";
import { data, Link, useLocation } from "react-router";
import { css } from "../../styled-system/css";
import { DocumentNavigation } from "../components/layout/document-navigation";
import { PageContainer } from "../components/layout/page-container";
import { ContributionAnswers } from "../features/contributions/contribution-answers";
import { consultations } from "../features/surveys/catalogue";
import { SurveyRouteError } from "../features/surveys/route-error";
import { type ContributionDetail, httpFailure } from "../lib/api";
import { getContribution } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/contribution";

export async function loader({ request, params }: Route.LoaderArgs) {
  const contribution = requireApiData(
    await getContribution(params.formId, params.contributionId, {
      signal: request.signal,
    }),
  );
  if (
    contribution.form.id !== params.formId ||
    contribution.contribution.id !== params.contributionId
  )
    requireApiData(httpFailure(404));
  return data(contribution, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
export default function Contribution({ loaderData }: Route.ComponentProps) {
  return <ContributionContent detail={loaderData} />;
}
export function ContributionContent({
  detail,
  navigation,
}: {
  detail: ContributionDetail;
  navigation?: { previous: string | null; next: string | null };
}) {
  const { form, contribution, author, answers } = detail;
  // Ordinal routes supply their own destinations. Direct ID reads use the API's
  // neighbors, in the same questionnaire order, regardless of the entry point.
  const documentNavigation = navigation ?? {
    previous: detail.previous_id
      ? `/forms/${form.id}/contributions/${detail.previous_id}`
      : null,
    next: detail.next_id
      ? `/forms/${form.id}/contributions/${detail.next_id}`
      : null,
  };
  const consultation = consultations.find((item) =>
    Object.hasOwn(item.questionnaires, form.id),
  );
  const { hash } = useLocation();
  const [targetId, setTargetId] = useState("");
  useEffect(() => {
    const id = /^#answer-\d+$/.test(hash) ? hash.slice(1) : "";
    setTargetId(id);
    // pushState does not update native :target. Preserve CSS targeting without JS
    // and add focus/highlighting for React Router navigation, without scrolling.
    if (id) document.getElementById(id)?.focus({ preventScroll: true });
  }, [hash]);
  const path = `/forms/${form.id}/contributions/${contribution.id}`;
  return (
    <PageContainer>
      <title>{`Contribution n° ${contribution.id} — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Consultez les réponses complètes d’une contribution au questionnaire « ${form.name} ».`}
      />
      <link rel="canonical" href={`https://cahierdedoleances.fr${path}`} />
      <p className={css({ mb: "6" })}>
        <Link to={`/forms/${form.id}`}>← Retour au formulaire</Link>
      </p>
      <header className={css({ maxWidth: "reading", mb: "8" })}>
        <h1>Contribution n° {contribution.id}</h1>
        <dl
          aria-label="Métadonnées de la contribution"
          className={css({
            textStyle: "documentMetadata",
            display: "grid",
            gap: "3",
            "& > div": {
              display: "grid",
              gridTemplateColumns: {
                base: "minmax(0, 1fr)",
                sm: "minmax(0, 1fr) minmax(0, 3fr)",
              },
              columnGap: "4",
              overflowWrap: "anywhere",
            },
          })}
        >
          {consultation && (
            <div>
              <dt>Consultation</dt>
              <dd>{consultation.name}</dd>
            </div>
          )}
          <div>
            <dt>Questionnaire</dt>
            <dd>
              <Link to={`/forms/${form.id}`}>{form.name}</Link>
            </dd>
          </div>
          <div>
            <dt>Auteur</dt>
            <dd>
              {author ? (
                <Link to={`/authors/${author.id}`}>{author.name}</Link>
              ) : (
                "Auteur non renseigné"
              )}
            </dd>
          </div>
          {contribution.submitted_at && (
            <div>
              <dt>Date</dt>
              <dd>
                <time dateTime={contribution.submitted_at}>
                  {new Intl.DateTimeFormat("fr-FR", {
                    dateStyle: "long",
                    timeZone: "UTC",
                  }).format(
                    new Date(
                      `${contribution.submitted_at.slice(0, 10)}T00:00:00Z`,
                    ),
                  )}
                </time>
              </dd>
            </div>
          )}
        </dl>
      </header>
      <ContributionNavigation {...documentNavigation} />
      <ContributionAnswers answers={answers} targetId={targetId} />
      <ContributionNavigation {...documentNavigation} bottom />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";

function ContributionNavigation({
  previous,
  next,
  bottom = false,
}: {
  previous: string | null;
  next: string | null;
  bottom?: boolean;
}) {
  return (
    <DocumentNavigation
      label={`Contributions du questionnaire${bottom ? " en bas de page" : ""}`}
      previous={previous}
      next={next}
      previousLabel="← Contribution précédente"
      nextLabel="Contribution suivante →"
    />
  );
}
