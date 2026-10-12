import { Link } from "react-router";
import type { components } from "../../../contracts/api.generated";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import { Card } from "../../components/ui/card";
import type { Forms } from "../../lib/api";

export function SurveyCard({
  form,
}: {
  form: components["schemas"]["FormSummary"];
}) {
  return (
    <Card>
      <h2 className={css({ mb: "3" })}>
        <Link to={`/forms/${form.id}`}>{form.name}</Link>
      </h2>
      <p className={css({ color: "muted" })}>
        {form.questions_count} question{form.questions_count !== 1 ? "s" : ""}
      </p>
    </Card>
  );
}

export function SurveyList({ forms }: { forms: Forms }) {
  if (!forms.length)
    return <EmptyState>Aucun formulaire disponible pour le moment.</EmptyState>;
  return (
    <ul
      aria-label="Formulaires du Grand Débat"
      className={css({
        display: "grid",
        gridTemplateColumns: { base: "1fr", md: "repeat(2, minmax(0, 1fr))" },
        gap: "6",
        listStyle: "none",
        p: "0",
      })}
    >
      {forms.map((form) => (
        <li key={form.id}>
          <SurveyCard form={form} />
        </li>
      ))}
    </ul>
  );
}
