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
        content="Recherchez dans les corpus de paroles citoyennes disponibles et retrouvez chaque texte dans son contexte."
      />
      <meta name="robots" content="noindex, follow" />
      <link rel="canonical" href="https://cahierdedoleances.fr/recherche" />
      <div className={css({ maxWidth: "reading" })}>
        <h1 className={styles.title}>Rechercher dans les paroles citoyennes</h1>
        <p className={css({ textStyle: "editorialBody", mb: "6" })}>
          Une question, un sujet, une préoccupation : découvrez les paroles
          citoyennes, dans leur contexte d’origine.
        </p>
      </div>
      <SearchPanel {...loaderData} />
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
