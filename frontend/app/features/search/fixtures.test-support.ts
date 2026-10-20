import type { HybridSearchPage } from "../../lib/api";
export const form = {
  id: "9007199254740995",
  name: "Participation citoyenne",
  url: "/forms/9007199254740995",
};
export const question = {
  id: "9007199254741022",
  prompt: "Comment améliorer la participation citoyenne ?",
  url: "/questions/9007199254741022-participation",
};
export const page: HybridSearchPage = {
  q: "école & lecture",
  state: "results",
  mode: "hybrid",
  recipe_version: "h1-public-v1",
  page_size: 20,
  has_next: true,
  next_cursor: "next+2/=opaque",
  previous_cursor: null,
  first_cursor: "first+1/=opaque",
  expires_at: "2026-10-20T16:10:00Z",
  window: {
    document_limit: 50,
    retrieval_depth: 50,
    answer_count: 21,
    exhaustive: false,
  },
  warnings: [],
  items: Array.from({ length: 20 }, (_, index) => {
    const id =
      ["9007199254741993", "9007199254741992", "9007199254741994"][index] ??
      String(9007199254742000n + BigInt(index));
    return {
      answer_id: id,
      contribution_id: "9007199254742993",
      rank: index + 1,
      texts:
        index === 2
          ? [
              {
                unit_type: "other_text" as const,
                unit_index: 0,
                text: "Autre A",
              },
              {
                unit_type: "other_text" as const,
                unit_index: 2,
                text: "Autre B",
              },
            ]
          : [
              {
                unit_type: "open_answer" as const,
                unit_index: 0,
                text:
                  index === 0
                    ? "Première réponse.\n\n<script>alert('non fiable')</script>\n" +
                      "Un texte très long. ".repeat(30)
                    : index === 1
                      ? "Non"
                      : `Réponse citoyenne ${index + 1}.`,
              },
            ],
      is_truncated: index === 0,
      question,
      form,
      url: `/forms/${form.id}/contributions/9007199254742993#answer-${id}`,
    };
  }),
};
