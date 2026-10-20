import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Alert } from "../../components/ui/alert";
import type { HybridSearchPage } from "../../lib/api";
import styles from "../forms/results.module.css";
import { ListNavigation, type MoreAction } from "../pagination/list-navigation";
import { type SearchState, searchUrl } from "./search-url";

const secondary = css({ fontSize: "secondary", color: "muted" });
export function SearchResults({
  results: page,
  state,
  onMore,
  pending,
  continuationError = false,
}: {
  results: HybridSearchPage;
  state: SearchState;
  onMore?: MoreAction;
  pending?: boolean;
  continuationError?: boolean;
}) {
  return (
    <section
      aria-labelledby="search-results-title"
      className={css({ maxWidth: "reading" })}
    >
      <h2 id="search-results-title" className={styles.questionTitle}>
        Les réponses citoyennes
      </h2>
      <p role="status" aria-atomic="true" className={secondary}>
        {page.items.length
          ? `${page.items.length} réponses affichées.`
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
          <ol aria-label="Réponses citoyennes" className={styles.questions}>
            {page.items.map((item) => (
              <li
                key={item.answer_id}
                data-progressive-id={item.answer_id}
                tabIndex={-1}
              >
                <article
                  className={styles.question}
                  aria-labelledby={`search-question-${item.answer_id}`}
                >
                  <p className={secondary}>À la question</p>
                  <h3
                    id={`search-question-${item.answer_id}`}
                    className={styles.questionTitle}
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
                </article>
              </li>
            ))}
          </ol>
        </>
      )}
      <ListNavigation
        label="Pagination des résultats"
        previous={
          page.previous_cursor
            ? searchUrl({ ...state, cursor: page.previous_cursor })
            : null
        }
        first={
          page.previous_cursor && page.first_cursor
            ? searchUrl({ ...state, cursor: page.first_cursor })
            : null
        }
        next={
          page.has_next && page.next_cursor
            ? searchUrl({ ...state, cursor: page.next_cursor })
            : null
        }
        pending={pending}
        onMore={onMore}
      />
      {!continuationError && !page.has_next && page.state !== "empty" && (
        <p className={secondary}>
          Vous êtes à la fin de cette sélection. Précisez ou reformulez votre
          recherche pour découvrir d’autres réponses.
        </p>
      )}
    </section>
  );
}
