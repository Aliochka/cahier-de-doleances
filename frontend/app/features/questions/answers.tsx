import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { AnswerPage } from "../../lib/api";

export function Answers({
  page,
  path,
  cursor,
}: {
  page: AnswerPage;
  path: string;
  cursor: string | null;
}) {
  return (
    <section aria-labelledby="answers-title">
      <h2 id="answers-title">Réponses à la question</h2>
      {page.items.length === 0 ? (
        <EmptyState>Aucune réponse consultable dans ce lot.</EmptyState>
      ) : (
        <ol
          aria-label="Réponses à la question"
          className={css({
            listStyle: "none",
            p: 0,
            display: "grid",
            gap: "8",
          })}
        >
          {page.items.map((answer) => (
            <li
              key={answer.id}
              className={css({
                borderTopWidth: "thin",
                borderColor: "border",
                pt: "6",
                minWidth: 0,
              })}
            >
              <p className={css({ color: "muted", mb: "3" })}>
                {answer.author?.name ?? "Auteur non renseigné"}
                {answer.submitted_at && (
                  <>
                    {" "}
                    ·{" "}
                    <time dateTime={answer.submitted_at}>
                      {new Intl.DateTimeFormat("fr-FR", {
                        dateStyle: "long",
                        timeZone: "UTC",
                      }).format(
                        new Date(
                          `${answer.submitted_at.slice(0, 10)}T00:00:00Z`,
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
                {answer.text}
              </p>
              {answer.is_truncated && (
                <p className={css({ color: "muted", mt: "3" })}>
                  Texte abrégé dans cette liste. La consultation intégrale d’une
                  réponse sera disponible ultérieurement.
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
      <nav
        aria-label="Lots de réponses"
        className={css({
          display: "flex",
          flexWrap: "wrap",
          gap: "6",
          mt: "8",
        })}
      >
        {cursor !== null && (
          <Link to={path}>Retour aux premières réponses</Link>
        )}
        {page.has_next && page.next_cursor !== null && (
          <Link
            to={`${path}?${new URLSearchParams({ cursor: page.next_cursor })}`}
          >
            Voir les réponses suivantes
          </Link>
        )}
      </nav>
    </section>
  );
}
