import { data, Link } from "react-router";
import { css } from "../../styled-system/css";
import { EmptyState } from "../components/layout/data-states";
import { PageContainer } from "../components/layout/page-container";
import { Statistics } from "../features/questions/statistics";
import { SurveyRouteError } from "../features/surveys/route-error";
import { getFormStats } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/dashboard";

export async function loader({ request, params }: Route.LoaderArgs) {
  return data(
    requireApiData(
      await getFormStats(params.formId, { signal: request.signal }),
    ),
    {
      headers: { "Cache-Control": "private, no-store" },
    },
  );
}
export default function Dashboard({
  loaderData: dashboard,
}: Route.ComponentProps) {
  return (
    <PageContainer>
      <title>{`Statistiques — ${dashboard.form.name} — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Consultez les résultats des questions à choix du questionnaire « ${dashboard.form.name} » du Grand Débat National.`}
      />
      <link
        rel="canonical"
        href={`https://cahierdedoleances.fr/forms/${dashboard.form.id}/dashboard`}
      />
      {dashboard.questions.every(
        (entry) => entry.stats.total_answers === 0,
      ) && <meta name="robots" content="noindex, follow" />}
      <nav
        aria-label="Navigation du tableau de bord"
        className={css({
          display: "flex",
          flexWrap: "wrap",
          gap: "6",
          mb: "6",
        })}
      >
        <Link to={`/forms/${dashboard.form.id}`}>← Retour au formulaire</Link>
        <Link to="/enquetes">Retour aux enquêtes</Link>
      </nav>
      <h1>{`Statistiques — ${dashboard.form.name}`}</h1>
      <p className={css({ mb: "8", maxWidth: "reading" })}>
        Les résultats des questions à choix du formulaire, dans l’ordre du
        questionnaire. Chaque graphique peut être ouvert et les valeurs sont
        disponibles dans les tableaux.
      </p>
      {dashboard.questions.length === 0 ? (
        <EmptyState>
          Ce formulaire ne contient aucune question statistique.
        </EmptyState>
      ) : (
        <div className={css({ display: "grid", gap: "12" })}>
          {dashboard.questions.map(({ question, stats }) => (
            <section
              key={question.id}
              aria-labelledby={`question-${question.id}`}
            >
              <h2 id={`question-${question.id}`}>
                <Link to={question.url}>{question.prompt}</Link>
              </h2>
              <p className={css({ color: "muted", mb: "4" })}>
                {question.type === "multi_choice"
                  ? "Choix multiples"
                  : "Choix unique"}
              </p>
              <Statistics stats={stats} deferChart headingLevel={3} />
            </section>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
