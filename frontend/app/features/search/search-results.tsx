import { Link } from "react-router";
import { css, cx } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Alert } from "../../components/ui/alert";
import type { HybridSearchPage } from "../../lib/api";
import {
  CitizenText,
  contributionStyles,
} from "../contributions/contribution-presentation";
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
  const questionScoped = !!state.path;
  const TextContainer = questionScoped ? "div" : "blockquote";
  return (
    <section
      aria-labelledby="search-results-title"
      className={css({ maxWidth: "reading" })}
    >
      <h2
        id="search-results-title"
        className={css({ fontSize: "subtitle", lineHeight: "body", mb: "4" })}
      >
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
          {questionScoped
            ? "Aucun résultat pour cette recherche. Essayez d’autres mots-clés."
            : "Aucun résultat pour cette recherche. Essayez de préciser votre sujet ou de reformuler votre question."}
        </EmptyState>
      ) : page.state === "sources_unavailable" ? (
        <EmptyState>
          Les réponses de cette page ne sont plus consultables. Vous pouvez
          poursuivre la sélection ou relancer votre recherche.
        </EmptyState>
      ) : (
        <>
          <p
            className={css({
              textStyle: "editorialBody",
              color: "muted",
              mb: "6",
            })}
          >
            {questionScoped ? (
              "Une sélection limitée de réponses classées selon les mots recherchés. Elle ne représente pas toutes les correspondances dans les réponses à cette question."
            ) : (
              <>
                Une sélection de réponses classées par pertinence, parmi les
                contributions du Grand Débat national. Ce n’est pas la totalité
                des réponses du corpus.
              </>
            )}
          </p>
          <ol
            aria-label="Réponses citoyennes"
            className={contributionStyles.list}
          >
            {page.items.map((item) => (
              <li
                key={item.answer_id}
                data-progressive-id={item.answer_id}
                tabIndex={-1}
              >
                <article
                  className={contributionStyles.entry}
                  aria-labelledby={`search-${questionScoped ? "answer" : "question"}-${item.answer_id}`}
                >
                  {questionScoped ? (
                    <header className={css({ mb: "4" })}>
                      <p
                        id={`search-answer-${item.answer_id}`}
                        className={contributionStyles.metadata}
                      >
                        Réponse {item.answer_id}
                      </p>
                    </header>
                  ) : (
                    <>
                      <p className={contributionStyles.metadata}>
                        Réponse {item.answer_id} · À la question
                      </p>
                      <h3
                        id={`search-question-${item.answer_id}`}
                        className={contributionStyles.question}
                      >
                        <Link to={item.question.url}>
                          {item.question.prompt}
                        </Link>
                      </h3>
                    </>
                  )}
                  <TextContainer className={css({ m: "0" })}>
                    {item.texts.map((unit, index) => (
                      <div
                        key={`${unit.unit_type}-${unit.unit_index}`}
                        className={css({ "& + &": { mt: "5" } })}
                      >
                        {unit.unit_type === "other_text" && (
                          <p className={contributionStyles.metadata}>
                            Autre précision
                            {item.texts.length > 1 ? ` ${index + 1}` : ""}
                          </p>
                        )}
                        <CitizenText>
                          {unit.text ||
                            "Texte à lire dans la contribution complète."}
                        </CitizenText>
                      </div>
                    ))}
                  </TextContainer>
                  {item.is_truncated && (
                    <p
                      className={cx(
                        contributionStyles.metadata,
                        css({ mt: "4" }),
                      )}
                    >
                      Extrait abrégé. Retrouvez le texte intégral dans la
                      contribution d’origine.
                    </p>
                  )}
                  <footer
                    className={css({
                      mt: questionScoped ? "4" : "6",
                      display: "grid",
                      gap: "3",
                    })}
                  >
                    {!questionScoped && (
                      <p className={contributionStyles.metadata}>
                        Enquête :{" "}
                        <Link to={item.form.url}>{item.form.name}</Link>
                      </p>
                    )}
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
          {questionScoped ? (
            "Vous êtes à la fin de cette sélection. Précisez ou modifiez vos mots-clés pour découvrir d’autres réponses."
          ) : (
            <>
              Vous êtes à la fin de cette sélection. Précisez ou reformulez
              votre recherche pour découvrir d’autres réponses.
            </>
          )}
        </p>
      )}
    </section>
  );
}
