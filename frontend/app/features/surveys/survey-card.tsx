import { Link } from "react-router";
import type { components } from "../../../contracts/api.generated";
import { css, cx } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Card } from "../../components/ui/card";
import type { Forms } from "../../lib/api";
import type { Consultation } from "./catalogue";
import styles from "./survey-card.module.css";

export function SurveyCard({
  form,
  metadata,
}: {
  form: components["schemas"]["FormSummary"];
  metadata?: Consultation["questionnaires"][string];
}) {
  return (
    <Card className={styles.card}>
      <h3 className={styles.title}>
        <Link
          to={`/forms/${form.id}`}
          aria-label={
            metadata
              ? `${metadata.title} — ${metadata.type ?? "Questionnaire"}`
              : undefined
          }
        >
          {metadata?.title ?? form.name}
        </Link>
      </h3>
      <div
        className={cx(styles.metadata, css({ textStyle: "documentMetadata" }))}
      >
        {metadata?.type && <p>{metadata.type}</p>}
        <p>
          {form.questions_count} question{form.questions_count !== 1 ? "s" : ""}
        </p>
      </div>
    </Card>
  );
}

export function SurveyList({
  forms,
  label = "Questionnaires",
  questionnaireMetadata,
}: {
  forms: Forms;
  label?: string;
  questionnaireMetadata?: Consultation["questionnaires"];
}) {
  if (!forms.length)
    return <EmptyState>Aucun formulaire disponible pour le moment.</EmptyState>;
  return (
    <ul
      aria-label={label}
      className={css({
        display: "grid",
        gridTemplateColumns: { base: "1fr", md: "repeat(2, minmax(0, 1fr))" },
        gap: "6",
        listStyle: "none",
        p: "0",
      })}
    >
      {forms.map((form) => (
        <li key={form.id} className={css({ minWidth: 0 })}>
          <SurveyCard form={form} metadata={questionnaireMetadata?.[form.id]} />
        </li>
      ))}
    </ul>
  );
}
