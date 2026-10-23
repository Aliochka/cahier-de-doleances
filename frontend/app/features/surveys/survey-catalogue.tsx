import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { Forms } from "../../lib/api";
import {
  type Consultation,
  consultations,
  groupQuestionnaires,
} from "./catalogue";
import { SurveyList } from "./survey-card";

export function SurveyCatalogue({
  forms,
  catalogue = consultations,
}: {
  forms: Forms;
  catalogue?: readonly Consultation[];
}) {
  if (!forms.length)
    return <EmptyState>Aucun formulaire disponible pour le moment.</EmptyState>;
  const sections = groupQuestionnaires(forms, catalogue);
  return (
    <div className={css({ display: "grid", gap: { base: "10", md: "12" } })}>
      {sections.map(({ consultation, forms }) => (
        <section
          key={consultation.id}
          aria-labelledby={`consultation-${consultation.id}`}
        >
          <header
            className={css({
              borderTopWidth: "thin",
              borderColor: "border",
              pt: "6",
              mb: "6",
            })}
          >
            {consultation.period && (
              <p className={css({ textStyle: "documentMetadata", mb: "2" })}>
                {consultation.period}
              </p>
            )}
            <h2 id={`consultation-${consultation.id}`}>{consultation.name}</h2>
            {consultation.description && (
              <p
                className={css({
                  textStyle: "editorialBody",
                  maxWidth: "reading",
                })}
              >
                {consultation.description}
              </p>
            )}
          </header>
          <SurveyList
            forms={forms}
            label={`Questionnaires — ${consultation.name}`}
            questionnaireMetadata={consultation.questionnaires}
          />
        </section>
      ))}
    </div>
  );
}
