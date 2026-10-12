import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { FormDetail } from "../../lib/api";

const questionTypes: Record<string, string> = {
  text: "Réponse libre",
  free_text: "Réponse libre",
  single_choice: "Choix unique",
  multi_choice: "Choix multiples",
  scale: "Échelle",
  number: "Réponse numérique",
  date: "Date",
};

export function QuestionList({
  questions,
}: {
  questions: FormDetail["questions"];
}) {
  if (!questions.length)
    return <EmptyState>Ce formulaire ne contient aucune question.</EmptyState>;
  return (
    <ol
      aria-label="Questions du formulaire"
      className={css({ display: "grid", gap: "6", listStyle: "none", p: "0" })}
    >
      {questions.map((question, index) => (
        <li
          key={question.id}
          className={css({
            borderTopWidth: "thin",
            borderColor: "border",
            pt: "6",
            minWidth: 0,
          })}
        >
          <p
            className={css({ color: "muted", fontSize: "secondary", mb: "3" })}
          >
            Question {index + 1}
            {Object.hasOwn(questionTypes, question.type)
              ? ` · ${questionTypes[question.type]}`
              : ""}
          </p>
          <h2
            className={css({
              fontSize: "section",
              lineHeight: "1.6",
              fontFamily: "body",
              color: "text",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
            })}
          >
            <Link to={`/questions/${question.id}-${question.slug}`}>
              {question.prompt}
            </Link>
          </h2>
        </li>
      ))}
    </ol>
  );
}
