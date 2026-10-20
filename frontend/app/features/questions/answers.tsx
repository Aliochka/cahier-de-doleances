import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { AnswerPage } from "../../lib/api";
import { ListNavigation, type MoreAction } from "../pagination/list-navigation";

export function Answers({
  page,
  path,
  cursor,
  formId,
  otherOnly = false,
  onMore,
  pending,
}: {
  page: AnswerPage;
  path: string;
  cursor: string | null;
  formId: string;
  otherOnly?: boolean;
  onMore?: MoreAction;
  pending?: boolean;
}) {
  return (
    <section aria-labelledby="answers-title">
      <h2 id="answers-title">
        {otherOnly
          ? "Réponses « Autre » à la question"
          : "Réponses à la question"}
      </h2>
      <p role="status" className={css({ color: "muted", mb: "6" })}>
        {page.items.length} réponses affichées.
      </p>
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
              data-progressive-id={answer.id}
              tabIndex={-1}
              className={css({
                borderTopWidth: "thin",
                borderColor: "border",
                pt: "6",
                minWidth: 0,
              })}
            >
              <p className={css({ color: "muted", mb: "3" })}>
                {answer.author ? (
                  <Link to={`/authors/${answer.author.id}`}>
                    {answer.author.name}
                  </Link>
                ) : (
                  "Auteur non renseigné"
                )}
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
                  Texte abrégé dans cette liste. Le texte intégral est
                  disponible dans la contribution.
                </p>
              )}
              <p className={css({ mt: "4" })}>
                <Link
                  to={`/forms/${formId}/contributions/${answer.contribution_id}#answer-${answer.id}`}
                >
                  Voir la contribution complète
                </Link>
              </p>
            </li>
          ))}
        </ol>
      )}
      <ListNavigation
        label="Lots de réponses"
        first={cursor !== null ? path : null}
        next={
          page.has_next && page.next_cursor
            ? `${path}?${new URLSearchParams({ cursor: page.next_cursor })}`
            : null
        }
        pending={pending}
        onMore={onMore}
      />
    </section>
  );
}
