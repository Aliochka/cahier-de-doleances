import { data, redirect } from "react-router";
import {
  type ApiFailure,
  type HybridSearchPage,
  httpFailure,
  isHistoricalResult,
} from "../../lib/api";
import { listCorpora, search } from "../../lib/api.server";
import { failureStatus } from "../../lib/api-errors";
import { localPreviewRequest } from "../../lib/local-preview.server";
import { type SearchState, searchUrl } from "./search-url";

const headers = {
  "Cache-Control": "private, no-store",
  "X-Robots-Tag": "noindex, follow",
};
export async function loadSearch(
  request: Request,
  url: URL,
  scope?: { path: string; questionId: string; enabled?: boolean },
) {
  const params = url.searchParams;
  const raw = params.get("q") ?? "";
  const size = params.get("page_size");
  const corpus = params.get("corpus");
  const preview = !scope && localPreviewRequest(request);
  const options = !scope
    ? await listCorpora({
        signal: request.signal,
        ...(preview ? { preview: true } : {}),
      })
    : null;
  const corpora = options?.ok
    ? options.data
    : [
        {
          id: "2019" as const,
          label: "Grand Débat national — 2019",
          available: true,
          published: true,
          preview: false,
        },
        {
          id: "1789" as const,
          label: "Cahiers de doléances — 1789",
          available: false,
          published: false,
          preview: false,
        },
      ];
  const state: SearchState = {
    ...(scope ? { path: scope.path } : {}),
    ...(corpus ? { corpus: corpus as "tous" | "2019" | "1789" } : {}),
    q: raw.normalize("NFC").trim(),
    cursor: params.get("cursor"),
    page_size: size === null ? 20 : Number(size),
  };
  const invalid =
    (scope !== undefined && params.get("tab") !== "search") ||
    (corpus !== null &&
      (!["tous", "2019", "1789"].includes(corpus) || scope !== undefined)) ||
    Array.from(raw).length > 512 ||
    [...params.keys()].some(
      (key) =>
        ![
          "q",
          "cursor",
          "page_size",
          ...(scope ? ["tab"] : ["corpus"]),
        ].includes(key) || params.getAll(key).length !== 1,
    ) ||
    (size !== null && !/^(?:[1-9]|1[0-9]|20)$/.test(size)) ||
    (state.cursor !== null &&
      (!state.q || !state.cursor || state.cursor.length > 1024));
  let failure: ApiFailure | null = invalid ? httpFailure(422) : null;
  let result: HybridSearchPage | null = null;
  if (!failure && state.q && scope?.enabled !== false) {
    const response = await search(
      {
        ...(scope ? { question_id: scope.questionId } : {}),
        q: state.q,
        ...(state.corpus ? { corpus: state.corpus } : {}),
        page_size: state.page_size,
        ...(state.cursor !== null ? { cursor: state.cursor } : {}),
      },
      { signal: request.signal, ...(preview ? { preview: true } : {}) },
    );
    if (response.ok) {
      if (
        response.data.mode !== (scope ? "lexical" : "hybrid") ||
        response.data.q !== state.q ||
        response.data.page_size !== state.page_size ||
        (scope !== undefined &&
          response.data.items.some(
            (item) =>
              isHistoricalResult(item) || item.question.id !== scope.questionId,
          ))
      )
        failure = { ok: false, kind: "invalid_response" };
      else {
        result = response.data;
        // Une seule redirection. Toutes les navigations suivantes portent déjà un curseur.
        if (state.cursor === null && result.first_cursor)
          throw redirect(searchUrl({ ...state, cursor: result.first_cursor }), {
            status: 303,
            headers,
          });
      }
    } else failure = response;
  }
  return data(
    {
      state,
      corpora,
      result,
      failure,
      fieldError:
        Array.from(raw).length > 512
          ? "La recherche est limitée à 512 caractères."
          : failure?.kind === "request"
            ? scope
              ? "Vérifiez vos mots-clés et les paramètres de recherche."
              : "Vérifiez votre question et les paramètres de recherche."
            : undefined,
    },
    { status: failure ? failureStatus(failure) : 200, headers },
  );
}
