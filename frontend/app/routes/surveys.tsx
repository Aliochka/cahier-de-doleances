import { data } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { SurveyRouteError } from "../features/surveys/route-error";
import { SurveyList } from "../features/surveys/survey-card";
import { listForms } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/surveys";

export async function loader({ request }: Route.LoaderArgs) {
  return data(requireApiData(await listForms({ signal: request.signal })), {
    headers: { "Cache-Control": "private, no-store" },
  });
}

export default function Surveys({ loaderData: forms }: Route.ComponentProps) {
  return (
    <PageContainer>
      <title>Enquêtes du Grand Débat — Cahier de doléances</title>
      <meta
        name="description"
        content="Découvrez les questionnaires historiques du Grand Débat National et parcourez leurs questions."
      />
      <link rel="canonical" href="https://cahierdedoleances.fr/enquetes" />
      <h1 className={css({ mb: "6", color: "#000" })}>Enquêtes</h1>
      <p className={css({ maxWidth: "reading", mb: "8" })}>
        Les formulaires du Grand Débat National invitent à découvrir les thèmes
        et les questions proposés aux citoyens. Retrouvez ici ces questionnaires
        historiques.
      </p>
      <SurveyList forms={forms} />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
