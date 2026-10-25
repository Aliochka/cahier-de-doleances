import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import styles from "../features/forms/results.module.css";
import { loadSearch } from "../features/search/search-loader.server";
import { SearchPanel } from "../features/search/search-panel";
import { SurveyRouteError } from "../features/surveys/route-error";
import type { Route } from "./+types/search";

export async function loader({ request, url }: Route.LoaderArgs) {
  return loadSearch(request, url);
}

export default function Search({ loaderData }: Route.ComponentProps) {
  return (
    <PageContainer>
      <title>Recherche — Cahier de doléances</title>
      <meta
        name="description"
        content="Retrouvez la parole citoyenne du Grand Débat national. Recherchez une question ou un sujet et découvrez les réponses dans leur contexte."
      />
      <meta name="robots" content="noindex, follow" />
      <link rel="canonical" href="https://cahierdedoleances.fr/recherche" />
      <div className={css({ maxWidth: "reading" })}>
        <h1 className={styles.title}>Rechercher dans les paroles citoyennes</h1>
        <p className={css({ textStyle: "editorialBody", mb: "6" })}>
          Une question, un sujet, une préoccupation : découvrez les réponses des
          participants au Grand Débat national, dans leur contexte d’origine.
        </p>
      </div>
      <SearchPanel {...loaderData} />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
