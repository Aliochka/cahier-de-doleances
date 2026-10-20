import { useEffect, useState } from "react";
import { data, Link, useLocation } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { ContributionAnswers } from "../features/contributions/contribution-answers";
import styles from "../features/forms/results.module.css";
import { ListNavigation } from "../features/pagination/list-navigation";
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
      <title>{`Contribution au questionnaire « ${form.name} » — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Consultez les réponses complètes d’une contribution au questionnaire « ${form.name} » du Grand Débat National.`}
      />
      <link rel="canonical" href={`https://cahierdedoleances.fr${path}`} />
      <p className={css({ mb: "6" })}>
        <Link to={`/forms/${form.id}`}>
          ← Retour au formulaire : {form.name}
        </Link>
      </p>
      <h1 className={styles.title}>
        Contribution au questionnaire « {form.name} »
      </h1>
      <p className={css({ color: "muted", mb: "8" })}>
        {author ? (
          <Link to={`/authors/${author.id}`}>{author.name}</Link>
        ) : (
          "Auteur non renseigné"
        )}
        {contribution.submitted_at && (
          <>
            {" "}
            ·{" "}
            <time dateTime={contribution.submitted_at}>
              {contribution.submitted_at.slice(0, 10)}
            </time>
          </>
        )}
      </p>
      {navigation && <ContributionNavigation {...navigation} />}
      <ContributionAnswers answers={answers} targetId={targetId} />
      {navigation && <ContributionNavigation {...navigation} bottom />}
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
    <ListNavigation
      label={`Contributions du questionnaire${bottom ? " en bas de page" : ""}`}
      previous={previous}
      next={next}
      previousLabel="← Contribution précédente"
      nextLabel="Contribution suivante →"
    />
  );
}
