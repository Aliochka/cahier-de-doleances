import { data } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { SurveyRouteError } from "../features/surveys/route-error";
import { SurveyCatalogue } from "../features/surveys/survey-catalogue";
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
      <title>Enquêtes — Cahier de doléances</title>
      <meta
        name="description"
        content="Explorez les consultations publiques et leurs questionnaires."
      />
      <link rel="canonical" href="https://cahierdedoleances.fr/enquetes" />
      <h1 className={css({ mb: "6", color: "text" })}>Enquêtes</h1>
      <p
        className={css({
          textStyle: "editorialBody",
          maxWidth: "reading",
          mb: "8",
        })}
      >
        Explorez les consultations publiques et leurs questionnaires.
      </p>
      <SurveyCatalogue forms={forms} />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
