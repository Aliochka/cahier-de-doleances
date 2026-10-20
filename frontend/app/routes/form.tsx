import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { FormQuestions } from "../features/forms/form-questions";
import styles from "../features/forms/results.module.css";
import { SurveyRouteError } from "../features/surveys/route-error";
import { httpFailure } from "../lib/api";
import { getForm } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/form";

export async function loader({ request, params }: Route.LoaderArgs) {
  if (new URL(request.url).searchParams.has("contrib")) {
    requireApiData(httpFailure(404));
  }
  const form = requireApiData(
    await getForm(params.formId, { signal: request.signal }),
  );
  return data(
    { mode: "form" as const, form },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}

export default function Form({ loaderData }: Route.ComponentProps) {
  return (
    <PageContainer>
      <p className={css({ mb: "6" })}>
        <Link to="/enquetes">← Retour aux enquêtes</Link>
      </p>
      <title>{`${loaderData.form.name} — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Découvrez les ${loaderData.form.questions_count} questions du questionnaire « ${loaderData.form.name} » du Grand Débat National.`}
      />
      <link
        rel="canonical"
        href={`https://cahierdedoleances.fr/forms/${loaderData.form.id}`}
      />
      <header className={styles.header}>
        <h1 className={styles.title}>{loaderData.form.name}</h1>
        <p className={styles.meta}>
          {/\(questions rapides\)\s*$/iu.test(loaderData.form.name) && (
            <>Questionnaire rapide · </>
          )}
          {loaderData.form.questions_count} question
          {loaderData.form.questions_count !== 1 ? "s" : ""} · Grand Débat
          national
        </p>
        <p className={styles.introduction}>
          Les réponses de participants volontaires, présentées question par
          question. Ces contributions ne constituent pas un sondage
          représentatif de la population.
        </p>
      </header>
      <ContributionsLink formId={loaderData.form.id} />
      {loaderData.form.statistics_availability.status !== "available" &&
        loaderData.form.questions.length > 0 && (
          <Alert variant="info">
            Les résultats statistiques sont momentanément indisponibles. Le
            questionnaire et les pages de ses questions restent consultables.
          </Alert>
        )}
      <FormQuestions form={loaderData.form} />
      <ContributionsLink formId={loaderData.form.id} />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";

function ContributionsLink({ formId }: { formId: string }) {
  return (
    <p className={styles.contributionsAction}>
      <Link
        to={`/forms/${formId}/contributions`}
        className={styles.contributionsButton}
      >
        Voir les contributions à ce questionnaire
      </Link>
    </p>
  );
}
