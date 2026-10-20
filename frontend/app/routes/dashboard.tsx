import { redirect } from "react-router";
import type { Route } from "./+types/dashboard";

/** Legacy bookmarks redirect before any API call; browsers retain their fragment. */
export function loader({ params, url }: Route.LoaderArgs) {
  return redirect(
    `/forms/${encodeURIComponent(params.formId)}${url.search}`,
    308,
  );
}
