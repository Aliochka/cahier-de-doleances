import type {
  AuthorFormsPage,
  ContributionDetail,
  PublicAuthor,
} from "../../lib/api";
export const publicAuthor: PublicAuthor = {
  id: "9007199254743993",
  name: "Auteur anonyme",
  is_anonymous: true,
  slug: "anonyme",
  url: "/authors/9007199254743993-anonyme",
};
export const contribution: ContributionDetail = {
  form: {
    id: "9007199254740995",
    name: "Participation citoyenne",
    url: "/forms/9007199254740995",
  },
  contribution: {
    id: "9007199254742993",
    submitted_at: null,
    api_url: "/api/v1/forms/9007199254740995/contributions/9007199254742993",
  },
  author: publicAuthor,
  legacy_index: null,
  answers: [
    {
      id: "9007199254741993",
      position: 1,
      question: {
        id: "9007199254741022",
        form_id: "9007199254740995",
        prompt: "Une question ouverte",
        type: "text",
        position: 1,
        slug: "ouverte",
        url: "/questions/9007199254741022-ouverte",
      },
      text:
        "Un paragraphe.\n\n<script>secret()</script>\n" +
        "Un texte complet. ".repeat(1500),
      selected_options: [],
      other_text: [],
      value: null,
    },
    {
      id: "9007199254741992",
      position: 2,
      question: {
        id: "9007199254741022",
        form_id: "9007199254740995",
        prompt: "Une question ouverte",
        type: "text",
        position: 1,
        slug: "ouverte",
        url: "/questions/9007199254741022-ouverte",
      },
      text: "Deuxième réponse à la même question",
      selected_options: [],
      other_text: [],
      value: null,
    },
    {
      id: "9007199254741994",
      position: 1,
      question: {
        id: "9007199254741021",
        form_id: "9007199254740995",
        prompt: "Vos choix",
        type: "multi_choice",
        position: 2,
        slug: "choix",
        url: "/questions/9007199254741021-choix",
      },
      text: null,
      selected_options: [
        { id: "9007199254744993", label: "Choix B", position: 1 },
        { id: "9007199254744994", label: "Choix A", position: 2 },
      ],
      other_text: ["Autre réponse"],
      value: null,
    },
    {
      id: "9007199254741995",
      position: 1,
      question: {
        id: "9007199254741023",
        form_id: "9007199254740995",
        prompt: "Combien ?",
        type: "number",
        position: null,
        slug: "combien",
        url: "/questions/9007199254741023-combien",
      },
      text: null,
      selected_options: [],
      other_text: [],
      value: "42",
    },
  ],
};
export const authorPage: AuthorFormsPage = {
  author_id: publicAuthor.id,
  page_size: 20,
  has_next: true,
  next_after_id: "9007199254742994",
  forms: [
    {
      ...contribution.form,
      contributions: [
        contribution.contribution,
        { ...contribution.contribution, id: "9007199254742994" },
      ],
    },
    {
      id: "9007199254740993",
      name: "Autre formulaire",
      url: "/forms/9007199254740993",
      contributions: [{ ...contribution.contribution, id: "9007199254742995" }],
    },
  ],
};
