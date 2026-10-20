import { useId } from "react";
import type { QuestionStatistics } from "../../lib/api";
import { ResultChart, StatisticalDetails } from "../forms/result-charts";
import styles from "../forms/results.module.css";

export function Statistics({ stats }: { stats: QuestionStatistics }) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className={styles.questions}>
      <h2 id={titleId} className={styles.questionTitle}>
        Résultats de la question
      </h2>
      <p className={styles.count}>
        {new Intl.NumberFormat("fr-FR").format(stats.total_answers)} réponses
        enregistrées
      </p>
      <ResultChart stats={stats} />
      <StatisticalDetails stats={stats} />
    </section>
  );
}
