import { expectTypeOf, it } from "vitest";
import type { components, operations, paths } from "../contracts/api.generated";

it("préserve les identifiants chaînes, les valeurs nulles et les réponses imbriquées", () => {
  type Detail =
    paths["/api/v1/forms/{form_id}"]["get"]["responses"][200]["content"]["application/json"];
  expectTypeOf<Detail>().toEqualTypeOf<components["schemas"]["FormDetail"]>();
  expectTypeOf<Detail["id"]>().toEqualTypeOf<string>();
  expectTypeOf<
    Detail["questions"][number]["form_id"]
  >().toEqualTypeOf<string>();
  expectTypeOf<Detail["questions"][number]["position"]>().toEqualTypeOf<
    number | null
  >();
  expectTypeOf<
    operations["get_public_form"]["responses"][404]["content"]["application/json"]
  >().toEqualTypeOf<components["schemas"]["ApiError"]>();
  const example: Detail = {
    id: "9007199254740993",
    name: "Exemple",
    questions_count: 0,
    statistics_availability: {
      status: "unavailable" as const,
      reason: "absent" as const,
    },
    url: "/forms/9007199254740993",
    questions: [],
  };
  expectTypeOf(example.id).toEqualTypeOf<string>();
});

it("type les questions, réponses, statistiques et paramètres BIGINT comme des chaînes", () => {
  type QuestionPath = operations["get_public_question"]["parameters"]["path"];
  type AnswerPath = operations["get_public_answer"]["parameters"]["path"];
  type Page =
    operations["list_public_question_answers"]["responses"][200]["content"]["application/json"];
  type Stats =
    operations["get_public_question_statistics"]["responses"][200]["content"]["application/json"];
  expectTypeOf<QuestionPath["question_id"]>().toEqualTypeOf<string>();
  expectTypeOf<AnswerPath["answer_id"]>().toEqualTypeOf<string>();
  expectTypeOf<Page>().toEqualTypeOf<components["schemas"]["AnswerPage"]>();
  expectTypeOf<
    Page["items"][number]["contribution_id"]
  >().toEqualTypeOf<string>();
  expectTypeOf<Page["items"][number]["submitted_at"]>().toEqualTypeOf<
    string | null
  >();
  expectTypeOf<Page["next_cursor"]>().toEqualTypeOf<string | null>();
  expectTypeOf<Stats["categories"][number]["option_id"]>().toEqualTypeOf<
    string | null
  >();
  const path: QuestionPath = { question_id: "9007199254740993" };
  const page: Page = {
    question_id: path.question_id,
    items: [],
    page_size: 20,
    has_next: false,
    next_cursor: null,
  };
  expectTypeOf(page.question_id).toEqualTypeOf<string>();
});
