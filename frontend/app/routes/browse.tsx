import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { SurveyRouteError } from "../features/surveys/route-error";
import { listCorpora } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import { localPreviewRequest } from "../lib/local-preview.server";
import type { Route } from "./+types/browse";

export async function loader({ request }: Route.LoaderArgs) {
  return data(
    requireApiData(
      await listCorpora({
        signal: request.signal,
        preview: localPreviewRequest(request),
      }),
    ),
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
export default function Browse({ loaderData: corpora }: Route.ComponentProps) {
  const historical = corpora.find((c) => c.id === "1789");
  return (
    <PageContainer>
      <title>Parcourir — Cahier de doléances</title>
      <h1 className={css({ textStyle: "documentTitle", mb: "6" })}>
        Parcourir les corpus
      </h1>
      <p
        className={css({
          textStyle: "editorialBody",
          maxWidth: "reading",
          mb: "8",
        })}
      >
        Deux façons de retrouver les textes : explorer les questionnaires ou
        parcourir les cahiers dans leur ordre documentaire.
      </p>
      <div className={css({ display: "grid", gap: "8", maxWidth: "reading" })}>
        <section
          className={css({
            borderTopWidth: "thin",
            borderColor: "border",
            pt: "6",
          })}
        >
          <h2 className={css({ textStyle: "documentSection", mb: "4" })}>
            <Link to="/enquetes">Grand Débat national — 2019</Link>
          </h2>
          <p className={css({ textStyle: "editorialBody" })}>
            Questionnaires, questions et contributions. Retrouvez chaque réponse
            dans son contexte.
          </p>
        </section>
        <section
          className={css({
            borderTopWidth: "thin",
            borderColor: "border",
            pt: "6",
          })}
        >
          <h2 className={css({ textStyle: "documentSection", mb: "4" })}>
            {historical?.available ? (
              <Link to="/parcourir/1789">Cahiers de doléances — 1789</Link>
            ) : (
              "Cahiers de doléances — 1789"
            )}
          </h2>
          <p className={css({ textStyle: "editorialBody" })}>
            {historical?.available
              ? "Catalogue des cahiers, sources et lecture intégrale."
              : "Le catalogue sera accessible après validation de la publication."}
          </p>
          {historical?.preview && (
            <Alert variant="warning">
              Aperçu local : ce corpus n’est pas publié.
            </Alert>
          )}
        </section>
      </div>
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
