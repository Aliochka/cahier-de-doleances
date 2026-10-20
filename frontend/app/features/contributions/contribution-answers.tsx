import { Link } from "react-router";
import { css, cx } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { ContributionDetail } from "../../lib/api";
import styles from "../forms/results.module.css";

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
    <ol aria-label="Réponses de la contribution" className={styles.questions}>
      {answers.map((answer) => (
        <li key={answer.id}>
          <section
            id={`answer-${answer.id}`}
            data-targeted={targetId === `answer-${answer.id}` || undefined}
            tabIndex={-1}
            aria-labelledby={`answer-title-${answer.id}`}
            className={cx(
              styles.question,
              css({
                overflowWrap: "anywhere",
                "&:target, &[data-targeted]": {
                  borderTopColor: "primary",
                  outline: "2px solid",
                  outlineColor: "primary",
                  outlineOffset: "2",
                },
              }),
            )}
          >
            <h2
              id={`answer-title-${answer.id}`}
              className={styles.questionTitle}
            >
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
            {answer.text !== null &&
              answer.text !== "" &&
              !duplicatesStructuredContent(answer) && (
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

// Imports may store the same choice labels/other fields both in text and in
// structured fields. Hide only a complete duplicate; never subtract fragments
// from citizen text or merge different answer rows.
export function duplicatesStructuredContent(
  answer: ContributionDetail["answers"][number],
): boolean {
  if (answer.text === null) return false;
  const normalize = (text: string) => text.replace(/\r\n?/g, "\n").trim();
  const text = normalize(answer.text);
  if (!text) return false;
  if (["single_choice", "multi_choice"].includes(answer.question.type)) {
    const options = answer.selected_options.map((option) => option.label);
    const other = answer.other_text;
    return [options, other, [...options, ...other]].some(
      (parts) => parts.length > 0 && normalize(parts.join("\n")) === text,
    );
  }
  return (
    ["number", "scale", "date"].includes(answer.question.type) &&
    answer.value !== null &&
    normalize(answer.value) === text
  );
}
