import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Card } from "../../components/ui/card";
import type { AnswerSearchPage, CatalogSearchPage } from "../../lib/api";
import { type SearchState, searchUrl } from "./search-url";

export type SearchResultsData =
  | { type: "answers"; page: AnswerSearchPage }
  | { type: "catalog"; page: CatalogSearchPage };
const listStyle = css({
  listStyle: "none",
  p: 0,
  display: "grid",
  gap: "6",
  mb: "6",
});
const muted = css({ color: "muted", fontSize: "secondary", mb: "3" });
function NoResults() {
  return (
    <EmptyState>
      Aucun résultat pour cette recherche. Essayez de modifier les termes.
    </EmptyState>
  );
}
export function SearchResults({
  result,
  state,
}: {
  result: SearchResultsData;
  state: SearchState;
}) {
  if (result.type === "answers") {
    const page = result.page;
    return (
      <section aria-labelledby="answer-results-title">
        <h2 id="answer-results-title">Réponses citoyennes</h2>
        <p className={muted}>
          Les réponses sont présentées par identifiant décroissant. La recherche
          est limitée à 1 789 candidats et peut ne pas être exhaustive.
        </p>
        {page.items.length === 0 ? (
          <NoResults />
        ) : (
          <ol aria-label="Résultats Réponses" className={listStyle}>
            {page.items.map((item) => (
              <li key={item.id}>
                <Card>
                  <h3>
                    <Link to={item.question.url}>{item.question.prompt}</Link>
                  </h3>
                  <p className={muted}>
                    <Link to={`/forms/${item.form.id}`}>{item.form.name}</Link>
                  </p>
                  <p className={muted}>
                    {item.author ? (
                      item.author.is_anonymous ? (
                        item.author.name
                      ) : (
                        <Link to={`/authors/${item.author.id}`}>
                          {item.author.name}
                        </Link>
                      )
                    ) : (
                      "Auteur non renseigné"
                    )}
                    {item.submitted_at && (
                      <>
                        {" "}
                        ·{" "}
                        <time dateTime={item.submitted_at}>
                          {new Intl.DateTimeFormat("fr-FR", {
                            dateStyle: "long",
                            timeZone: "UTC",
                          }).format(
                            new Date(
                              `${item.submitted_at.slice(0, 10)}T00:00:00Z`,
                            ),
                          )}
                        </time>
                      </>
                    )}
                  </p>
                  <p
                    className={css({
                      whiteSpace: "pre-wrap",
                      overflowWrap: "anywhere",
                    })}
                  >
                    {item.text}
                  </p>
                  {item.is_truncated && (
                    <p className={muted}>
                      Extrait abrégé ; le texte complet est disponible dans la
                      contribution.
                    </p>
                  )}
                  <p className={css({ mt: "4" })}>
                    <Link
                      to={`/forms/${item.form.id}/contributions/${item.contribution_id}#answer-${item.id}`}
                    >
                      Voir la contribution complète
                    </Link>
                  </p>
                </Card>
              </li>
            ))}
          </ol>
        )}
        {page.has_next && page.next_cursor && (
          <nav aria-label="Pagination des réponses">
            <Link to={searchUrl({ ...state, cursor: page.next_cursor })}>
              Résultats suivants
            </Link>
          </nav>
        )}
      </section>
    );
  }
  const page = result.page;
  if (page.forms.length === 0 && page.questions.length === 0)
    return <NoResults />;
  return (
    <>
      <section
        aria-labelledby="form-results-title"
        className={css({ mb: "8" })}
      >
        <h2 id="form-results-title">Enquêtes</h2>
        {page.forms.length === 0 ? (
          <p>Aucune enquête dans ce lot.</p>
        ) : (
          <ol aria-label="Résultats Enquêtes" className={listStyle}>
            {page.forms.map((form) => (
              <li key={form.id}>
                <Card>
                  <p className={muted}>
                    Enquête · {form.questions_count} question
                    {form.questions_count > 1 ? "s" : ""}
                  </p>
                  <h3>
                    <Link to={`/forms/${form.id}`}>{form.name}</Link>
                  </h3>
                </Card>
              </li>
            ))}
          </ol>
        )}
        {page.has_next_forms && page.next_cursor_forms && (
          <nav aria-label="Pagination des enquêtes">
            <Link
              to={searchUrl({ ...state, cursor_forms: page.next_cursor_forms })}
            >
              Enquêtes suivantes
            </Link>
          </nav>
        )}
      </section>
      <section aria-labelledby="question-results-title">
        <h2 id="question-results-title">Questions</h2>
        {page.questions.length === 0 ? (
          <p>Aucune question dans ce lot.</p>
        ) : (
          <ol aria-label="Résultats Questions" className={listStyle}>
            {page.questions.map((question) => (
              <li key={question.id}>
                <Card>
                  <p className={muted}>
                    Question ·{" "}
                    <Link to={`/forms/${question.form.id}`}>
                      {question.form.name}
                    </Link>
                  </p>
                  <h3>
                    <Link to={question.url}>{question.prompt}</Link>
                  </h3>
                </Card>
              </li>
            ))}
          </ol>
        )}
        {page.has_next_questions && page.next_cursor_questions && (
          <nav aria-label="Pagination des questions">
            <Link
              to={searchUrl({
                ...state,
                cursor_questions: page.next_cursor_questions,
              })}
            >
              Questions suivantes
            </Link>
          </nav>
        )}
      </section>
    </>
  );
}
