import type {
  AnswerPage,
  QuestionDetail,
  QuestionStatistics,
} from "../../lib/api";

export const question: QuestionDetail = {
  id: "9007199254741022",
  form_id: "9007199254740995",
  prompt: "Comment participer ?",
  type: "text",
  position: 1,
  slug: "comment-participer",
  url: "/questions/9007199254741022-comment-participer",
  display_mode: "text",
  form: {
    id: "9007199254740995",
    name: "Citoyenneté",
    url: "/forms/9007199254740995",
  },
};
export const answers: AnswerPage = {
  question_id: question.id,
  page_size: 20,
  has_next: true,
  next_cursor: "opaque+/=",
  items: [
    {
      id: "9007199254741993",
      question_id: question.id,
      contribution_id: "9007199254742993",
      text: "Premier paragraphe.\n\n<script>pas du HTML</script>",
      author: {
        id: "9007199254743993",
        name: "Auteur anonyme",
        is_anonymous: true,
        slug: "anonyme",
        url: "/authors/9007199254743993-anonyme",
      },
      submitted_at: null,
      is_truncated: true,
      url: "/answers/9007199254741993",
    },
  ],
};
export const stats: QuestionStatistics = {
  question_id: question.id,
  type: "multi_choice",
  total_answers: 10,
  answered_contributions_count: 8,
  total_selections: 14,
  total_option_selections: 13,
  other_text_answers_count: 1,
  percentage_denominator: "total_answers",
  percentage_decimal_places: 2,
  categories: [
    {
      option_id: "9007199254744993",
      kind: "option",
      label: "Une option longue ".repeat(12),
      position: 1,
      count: 8,
      percentage: 80,
    },
    {
      option_id: "9007199254744994",
      kind: "option",
      label: "Deuxième option",
      position: 2,
      count: 5,
      percentage: 50,
    },
    {
      option_id: "9007199254744995",
      kind: "option",
      label: "Zéro",
      position: null,
      count: 0,
      percentage: 0,
    },
    {
      option_id: null,
      kind: "other_text",
      label: "Autre texte",
      position: null,
      count: 1,
      percentage: 10,
    },
  ],
};
