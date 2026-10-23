import type { Forms } from "../../lib/api";

export type Consultation = {
  id: string;
  name: string;
  period?: string;
  description?: string;
  questionnaires: Readonly<Record<string, { title: string; type?: string }>>;
};

// Editorial catalogue, not API data. IDs and types are documented in
// docs/audit-corpus-rag.md §3; source provenance: docs/ingestion.md.
// Import/export dates are not consultation periods. Unlisted IDs stay unassigned.
export const consultations: readonly Consultation[] = [
  {
    id: "grand-debat-national",
    name: "Grand Débat national",
    period: "2019",
    description:
      "Les formulaires du Grand Débat National invitent à découvrir les thèmes et les questions proposés aux citoyens. Retrouvez ici ces questionnaires historiques.",
    questionnaires: {
      "2": {
        title: "Organisation de l'État & services publics",
        type: "Questionnaire rapide",
      },
      "4": {
        title: "Organisation de l'État & services publics",
        type: "Questionnaire détaillé",
      },
      "5": {
        title: "Démocratie & citoyenneté",
        type: "Questionnaire détaillé",
      },
      "7": {
        title: "Fiscalité & dépenses publiques",
        type: "Questionnaire détaillé",
      },
      "10": { title: "Transition écologique", type: "Questionnaire détaillé" },
      "11": { title: "Démocratie & citoyenneté", type: "Questionnaire rapide" },
      "12": { title: "Transition écologique", type: "Questionnaire rapide" },
    },
  },
];

export type CatalogueSection = {
  consultation: Consultation;
  forms: Forms;
};

export function groupQuestionnaires(
  forms: Forms,
  catalogue: readonly Consultation[] = consultations,
): CatalogueSection[] {
  const byId = new Map<string, Consultation>();
  for (const consultation of catalogue) {
    for (const id of Object.keys(consultation.questionnaires)) {
      if (byId.has(id)) throw new Error(`Questionnaire assigned twice: ${id}`);
      byId.set(id, consultation);
    }
  }
  const groups = new Map<string, Forms>();
  const unassigned: Forms = [];
  for (const form of forms) {
    const consultation = byId.get(form.id);
    if (!consultation) unassigned.push(form);
    else {
      const group = groups.get(consultation.id) ?? [];
      group.push(form);
      groups.set(consultation.id, group);
    }
  }
  const sections: CatalogueSection[] = catalogue.flatMap((consultation) => {
    const forms = groups.get(consultation.id);
    return forms?.length ? [{ consultation, forms }] : [];
  });
  if (unassigned.length)
    sections.push({
      consultation: {
        id: "unassigned",
        name: "Consultation non renseignée",
        questionnaires: {},
      },
      forms: unassigned,
    });
  return sections;
}
