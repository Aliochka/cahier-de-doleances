import { Link } from "react-router";
import { EmptyState } from "../../components/layout/data-states";
import type { FormDetail } from "../../lib/api";
import { ResultChart, StatisticalDetails } from "./result-charts";
import styles from "./results.module.css";

const types: Record<string, string> = {
  text: "Réponse libre",
  free_text: "Réponse libre",
  single_choice: "Choix unique",
  multi_choice: "Choix multiples",
  number: "Réponse numérique",
  scale: "Échelle",
  date: "Date",
};
const number = new Intl.NumberFormat("fr-FR");

export function FormQuestions({ form }: { form: FormDetail }) {
  if (!form.questions.length)
    return <EmptyState>Ce formulaire ne contient aucune question.</EmptyState>;
  const available = form.statistics_availability.status === "available";
  return (
    <div className={styles.results}>
      <ol className={styles.questions} aria-label="Questions du formulaire">
        {form.questions.map((q, index) => {
          const ordinal = q.position ?? index + 1;
          const choice = ["single_choice", "multi_choice"].includes(q.type);
          const stats = available ? q.statistics : null;
          const count = available ? q.answers_count : null;
          return (
            <li key={q.id}>
              <section
                id={`question-${q.id}`}
                tabIndex={-1}
                aria-labelledby={`question-title-${q.id}`}
                className={styles.question}
              >
                <p className={styles.eyebrow}>
                  Question {ordinal}
                  {Object.hasOwn(types, q.type) ? ` · ${types[q.type]}` : ""}
                </p>
                <h2
                  id={`question-title-${q.id}`}
                  className={styles.questionTitle}
                >
                  <Link to={q.url}>{q.prompt}</Link>
                </h2>
                <p className={styles.count}>
                  {typeof count === "number"
                    ? `${number.format(count)} réponse${count === 1 ? "" : "s"} enregistrée${count === 1 ? "" : "s"}`
                    : "Nombre de réponses indisponible."}
                </p>
                {choice &&
                  (stats ? (
                    <>
                      <ResultChart stats={stats} />
                      <StatisticalDetails
                        stats={stats}
                        publication={form.statistics_availability}
                        questionNumber={ordinal}
                      />
                    </>
                  ) : (
                    <p className={styles.unavailable}>
                      Les statistiques de cette question sont momentanément
                      indisponibles.
                    </p>
                  ))}
              </section>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
