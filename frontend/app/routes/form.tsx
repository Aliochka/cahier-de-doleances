import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { QuestionList } from "../features/surveys/question-list";
import { SurveyRouteError } from "../features/surveys/route-error";
import { getForm } from "../lib/api.server";
import { ERROR_HEADERS, requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/form";

export async function loader({ request, params }: Route.LoaderArgs) {
  if (new URL(request.url).searchParams.has("contrib")) {
    return data(
      { mode: "contribution" as const, formId: params.formId },
      { status: 501, headers: ERROR_HEADERS },
    );
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
      {loaderData.mode === "contribution" ? (
        <>
          <title>
            Consultation de contribution indisponible — Cahier de doléances
          </title>
          <meta name="robots" content="noindex, nofollow" />
          <h1 className={css({ mb: "6" })}>
            Consultation de contribution indisponible
          </h1>
          <Alert>
            La consultation d’une contribution complète n’est pas encore
            disponible dans cette interface. Cette adresse historique est
            conservée ; aucun contenu de contribution n’est affiché ici.
          </Alert>
          <p className={css({ mt: "6" })}>
            <Link to={`/forms/${encodeURIComponent(loaderData.formId)}`}>
              Consulter le questionnaire
            </Link>
          </p>
        </>
      ) : (
        <>
          <title>{`${loaderData.form.name} — Cahier de doléances`}</title>
          <meta
            name="description"
            content={`Découvrez les ${loaderData.form.questions_count} questions du questionnaire « ${loaderData.form.name} » du Grand Débat National.`}
          />
          <link
            rel="canonical"
            href={`https://cahierdedoleances.fr/forms/${loaderData.form.id}`}
          />
          <h1 className={css({ mb: "6" })}>{loaderData.form.name}</h1>
          <p className={css({ color: "muted", mb: "8" })}>
            {loaderData.form.questions_count} question
            {loaderData.form.questions_count !== 1 ? "s" : ""} · Grand Débat
            National
          </p>
          <QuestionList questions={loaderData.form.questions} />
        </>
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
