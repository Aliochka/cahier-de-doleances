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
    url: "/forms/9007199254740993",
    questions: [],
  };
  expectTypeOf(example.id).toEqualTypeOf<string>();
});
