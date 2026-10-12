import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { ContributionDetail } from "../../lib/api";

export function ContributionAnswers({
  answers,
  targetId,
}: {
  answers: ContributionDetail["answers"];
  targetId?: string;
}) {
  if (answers.length === 0)
    return (
      <EmptyState>
        Cette contribution ne contient aucune réponse consultable.
      </EmptyState>
    );
  return (
    <ol
      aria-label="Réponses de la contribution"
      className={css({ listStyle: "none", p: 0, display: "grid", gap: "8" })}
    >
      {answers.map((answer) => (
        <li key={answer.id}>
          <section
            id={`answer-${answer.id}`}
            data-targeted={targetId === `answer-${answer.id}` || undefined}
            tabIndex={-1}
            aria-labelledby={`answer-title-${answer.id}`}
            className={css({
              p: { base: "4", md: "6" },
              borderWidth: "thin",
              borderColor: "border",
              bg: "surface",
              minWidth: 0,
              overflowWrap: "anywhere",
              scrollMarginTop: "8",
              "&:target, &[data-targeted]": {
                borderColor: "primary",
                outline: "2px solid",
                outlineColor: "primary",
                bg: "surfaceSecondary",
              },
            })}
          >
            <h2 id={`answer-title-${answer.id}`}>
              <Link
                to={`/questions/${answer.question.id}-${answer.question.slug}`}
              >
                {answer.question.prompt}
              </Link>
            </h2>
            {answer.selected_options.length > 0 && (
              <ul
                aria-label="Choix sélectionnés"
                className={css({ pl: "6", mt: "4" })}
              >
                {answer.selected_options.map((option) => (
                  <li key={option.id}>{option.label}</li>
                ))}
              </ul>
            )}
            {answer.other_text.length > 0 && (
              <p className={css({ whiteSpace: "pre-wrap", mt: "4" })}>
                Autre : {answer.other_text.join("\n\n")}
              </p>
            )}
            {answer.value !== null && (
              <p className={css({ mt: "4" })}>{answer.value}</p>
            )}
            {answer.text !== null && answer.text !== "" && (
              <p className={css({ whiteSpace: "pre-wrap", mt: "4" })}>
                {answer.text}
              </p>
            )}
            {!answer.text &&
              answer.value === null &&
              answer.selected_options.length === 0 &&
              answer.other_text.length === 0 && (
                <p>Aucun contenu renseigné pour cette réponse.</p>
              )}
          </section>
        </li>
      ))}
    </ol>
  );
}
