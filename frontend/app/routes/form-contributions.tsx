import { data, redirect } from "react-router";
import { httpFailure } from "../lib/api";
import { getFormContribution } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";
import type { Route } from "./+types/form-contributions";
import { ContributionContent } from "./contribution";

export async function loader({ request, params }: Route.LoaderArgs) {
  const query = new URL(request.url).searchParams;
  const index = query.get("contrib") ?? "1";
  if (!/^[1-9]\d{0,18}$/.test(index) || BigInt(index) > 9223372036854775807n)
    throw new Response("Rang de contribution invalide", { status: 422 });
  const detail = requireApiData(
    await getFormContribution(params.formId, index, { signal: request.signal }),
  );
  if (detail.form.id !== params.formId || !detail.legacy_index)
    requireApiData(httpFailure(502));
  const rank = BigInt(detail.legacy_index ?? "1");
  const path = `/forms/${params.formId}/contributions`;
  if (String(rank) !== index) return redirect(`${path}?contrib=${rank}`);
  // The existing API clamps ranks to the final contribution. Probe only the next
  // rank to avoid presenting an endless "next" link at the end of the corpus.
  const next =
    rank < 9223372036854775807n
      ? requireApiData(
          await getFormContribution(params.formId, String(rank + 1n), {
            signal: request.signal,
          }),
        )
      : null;
  if (next && next.form.id !== params.formId) requireApiData(httpFailure(502));
  return data(
    {
      detail,
      navigation: {
        previous: rank > 1n ? `${path}?contrib=${rank - 1n}` : null,
        next:
          next && next.contribution.id !== detail.contribution.id
            ? `${path}?contrib=${rank + 1n}`
            : null,
      },
    },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
export default function FormContributions({
  loaderData,
}: Route.ComponentProps) {
  return (
    <ContributionContent
      detail={loaderData.detail}
      navigation={loaderData.navigation}
    />
  );
}
export { ErrorBoundary, headers } from "./contribution";
