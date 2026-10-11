import { data } from "react-router";
import type { ApiErrorKind, ApiFailure, ApiResult } from "./api";

export const errorMessages: Record<ApiErrorKind, string> = {
  request: "La demande est invalide. Vérifiez les informations saisies.",
  denied: "Vous n’avez pas accès à cette ressource.",
  missing: "Cette ressource n’existe pas.",
  application: "Une erreur est survenue. Veuillez réessayer.",
  unavailable: "Le service est momentanément indisponible.",
  server_timeout:
    "Le service a dépassé son délai de réponse. Réessayez dans quelques instants.",
  timeout: "La réponse prend trop de temps. Vous pouvez réessayer.",
  network: "Le service est inaccessible pour le moment.",
  cancelled: "La requête a été annulée.",
  invalid_response:
    "Le service a envoyé une réponse inutilisable. Veuillez réessayer.",
  configuration: "Le service est momentanément indisponible.",
};
export function failureStatus(error: ApiFailure): number {
  if (["network", "configuration", "unavailable"].includes(error.kind))
    return 503;
  if (["timeout", "server_timeout"].includes(error.kind)) return 504;
  if (error.kind === "invalid_response") return 502;
  if (error.kind === "cancelled") return 499;
  return error.status ?? (error.kind === "request" ? 422 : 500);
}
export const ERROR_HEADERS = {
  "Cache-Control": "private, no-store",
  "X-Robots-Tag": "noindex, nofollow",
};
/** Await this in the loader. Never defer essential data into the HTML stream. */
export function requireApiData<T>(result: ApiResult<T>): T {
  if (result.ok) return result.data;
  throw data(
    { kind: result.kind },
    { status: failureStatus(result), headers: ERROR_HEADERS },
  );
}
