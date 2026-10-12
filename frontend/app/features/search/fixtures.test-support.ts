import type { AnswerSearchPage, CatalogSearchPage } from "../../lib/api";
export const form = {
  id: "9007199254740995",
  name: "Participation citoyenne",
  url: "/forms/9007199254740995",
};
export const question = {
  id: "9007199254741022",
  form_id: form.id,
  prompt: "Comment améliorer la participation citoyenne ?",
  type: "text",
  position: 1,
  slug: "participation",
  url: "/questions/9007199254741022-participation",
};
export const answers: AnswerSearchPage = {
  q: "école & lecture",
  page_size: 20,
  has_next: true,
  next_cursor: "answer+2/=opaque",
  items: [
    {
      id: "9007199254741993",
      contribution_id: "9007199254742993",
      text:
        "Première réponse.\n\n<script>alert('non fiable')</script>\n" +
        "Un texte très long. ".repeat(20),
      is_truncated: true,
      submitted_at: null,
      author: {
        id: "9007199254743994",
        name: "Pseudonyme public",
        is_anonymous: false,
        slug: "pseudonyme-public",
        url: "/authors/9007199254743994",
      },
      question,
      form,
      url: `/forms/${form.id}/contributions/9007199254742993#answer-9007199254741993`,
    },
    {
      id: "9007199254741992",
      contribution_id: "9007199254742993",
      text: "Seconde réponse.",
      is_truncated: false,
      submitted_at: "2019-01-15T00:00:00",
      author: {
        id: "9007199254743993",
        name: "Auteur anonyme",
        is_anonymous: true,
        slug: "anonyme",
        url: "/authors/9007199254743993",
      },
      question,
      form,
      url: `/forms/${form.id}/contributions/9007199254742993#answer-9007199254741992`,
    },
  ],
};
export const catalog: CatalogSearchPage = {
  q: answers.q,
  page_size: 20,
  has_next_forms: true,
  has_next_questions: true,
  next_cursor_forms: "forms+2/=opaque",
  next_cursor_questions: "questions+2/=opaque",
  forms: [
    { ...form, questions_count: 3, kind: "form" },
    {
      id: "9007199254740993",
      name: "Autre enquête",
      url: "/forms/9007199254740993",
      questions_count: 0,
      kind: "form",
    },
  ],
  questions: [
    { ...question, kind: "question", form, answers_count: 100 },
    {
      ...question,
      id: "9007199254741021",
      prompt: "Une autre question au libellé très long. ".repeat(20),
      url: "/questions/9007199254741021-sujets",
      kind: "question",
      form,
      answers_count: 0,
    },
  ],
};
