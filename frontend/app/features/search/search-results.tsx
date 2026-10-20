import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import type { HybridSearchPage } from "../../lib/api";
import { type SearchState, searchUrl } from "./search-url";

const secondary = css({ fontSize: "secondary", color: "muted" });
export function SearchResults({
  page,
  state,
}: {
  page: HybridSearchPage;
  state: SearchState;
}) {
  return (
    <section
      aria-labelledby="search-results-title"
      className={css({ maxWidth: "reading" })}
    >
      <h2 id="search-results-title">Les réponses citoyennes</h2>
      <p role="status" aria-atomic="true" className={secondary}>
        {page.items.length
          ? `${page.items.length} réponses affichées dans cette page.`
          : page.state === "empty"
            ? "Aucun résultat pour cette recherche."
            : "Des sources ne sont plus accessibles."}
      </p>
      {page.warnings.length > 0 && (
        <Alert variant="warning" announcement="polite">
          Certaines réponses ne sont plus accessibles et ont été retirées de
          cette sélection.
        </Alert>
      )}
      {page.state === "empty" ? (
        <EmptyState>
          Aucun résultat pour cette recherche. Essayez de préciser votre sujet
          ou de reformuler votre question.
        </EmptyState>
      ) : page.state === "sources_unavailable" ? (
        <EmptyState>
          Les réponses de cette page ne sont plus consultables. Vous pouvez
          poursuivre la sélection ou relancer votre recherche.
        </EmptyState>
      ) : (
        <>
          <p className={css({ color: "muted", mb: "6" })}>
            Une sélection de réponses classées par pertinence, parmi les
            contributions du Grand Débat national. Ce n’est pas la totalité des
            réponses du corpus.
          </p>
          <ol
            aria-label="Réponses citoyennes"
            className={css({
              listStyle: "none",
              p: 0,
              display: "grid",
              gap: "6",
              mb: "8",
            })}
          >
            {page.items.map((item) => (
              <li key={item.answer_id}>
                <Card
                  className={css({ p: { base: "4", md: "6" } })}
                  aria-labelledby={`search-question-${item.answer_id}`}
                >
                  <p className={secondary}>À la question</p>
                  <h3
                    id={`search-question-${item.answer_id}`}
                    className={css({
                      fontFamily: "body",
                      fontSize: "body",
                      fontWeight: "semibold",
                      lineHeight: "body",
                      mt: "1",
                      mb: "5",
                    })}
                  >
                    <Link to={item.question.url}>{item.question.prompt}</Link>
                  </h3>
                  <blockquote
                    className={css({
                      m: 0,
                      pl: { base: "3", md: "4" },
                      borderLeftWidth: "emphasis",
                      borderLeftColor: "primary",
                      fontFamily: "body",
                      fontSize: "section",
                      lineHeight: "1.8",
                      overflowWrap: "anywhere",
                    })}
                  >
                    {item.texts.map((unit, index) => (
                      <div
                        key={`${unit.unit_type}-${unit.unit_index}`}
                        className={css({ "& + &": { mt: "5" } })}
                      >
                        {unit.unit_type === "other_text" && (
                          <p className={secondary}>
                            Autre précision
                            {item.texts.length > 1 ? ` ${index + 1}` : ""}
                          </p>
                        )}
                        <p className={css({ whiteSpace: "pre-wrap" })}>
                          {unit.text ||
                            "Texte à lire dans la contribution complète."}
                        </p>
                      </div>
                    ))}
                  </blockquote>
                  {item.is_truncated && (
                    <p
                      className={css({
                        fontSize: "secondary",
                        color: "muted",
                        mt: "4",
                      })}
                    >
                      Extrait abrégé. Retrouvez le texte intégral dans la
                      contribution d’origine.
                    </p>
                  )}
                  <footer
                    className={css({ mt: "6", display: "grid", gap: "3" })}
                  >
                    <p className={secondary}>
                      Enquête : <Link to={item.form.url}>{item.form.name}</Link>
                    </p>
                    <p>
                      <Link to={item.url}>Lire la contribution complète</Link>
                    </p>
                  </footer>
                </Card>
              </li>
            ))}
          </ol>
        </>
      )}
      {(page.previous_cursor || page.next_cursor) && (
        <nav
          aria-label="Pagination des résultats"
          className={css({
            display: "flex",
            flexWrap: "wrap",
            gap: "5",
            mb: "6",
          })}
        >
          {page.previous_cursor && (
            <Link to={searchUrl({ ...state, cursor: page.previous_cursor })}>
              Page précédente
            </Link>
          )}
          {page.previous_cursor && page.first_cursor && (
            <Link to={searchUrl({ ...state, cursor: page.first_cursor })}>
              Première page
            </Link>
          )}
          {page.has_next && page.next_cursor && (
            <Link to={searchUrl({ ...state, cursor: page.next_cursor })}>
              Page suivante
            </Link>
          )}
        </nav>
      )}
      {!page.has_next && page.state !== "empty" && (
        <p className={secondary}>
          Vous êtes à la fin de cette sélection. Précisez ou reformulez votre
          recherche pour découvrir d’autres réponses.
        </p>
      )}
    </section>
  );
}
