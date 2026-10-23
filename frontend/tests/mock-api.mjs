// Loopback-only synthetic API. No request is forwarded to Wallace.
import { createServer } from "node:http";

const forms = [
  {
    id: "9007199254740995",
    name: "Participation citoyenne",
    questions_count: 3,
    url: "/forms/9007199254740995",
  },
  {
    id: "9007199254740993",
    name: "Formulaire synthétique",
    questions_count: 0,
    url: "/forms/9007199254740993",
  },
];
const questions = [
  {
    id: "9007199254741022",
    form_id: forms[0].id,
    prompt:
      "Comment améliorer la participation citoyenne et permettre à chacun de contribuer aux décisions publiques, y compris dans les territoires les plus éloignés ?",
    type: "text",
    position: 1,
    slug: "participation",
    url: "/questions/9007199254741022-participation",
  },
  {
    id: "9007199254741020",
    form_id: forms[0].id,
    prompt: "Quel mode de consultation privilégier ?",
    type: "single_choice",
    position: 2,
    slug: "consultation",
    url: "/questions/9007199254741020-consultation",
  },
  {
    id: "9007199254741021",
    form_id: forms[0].id,
    prompt: "Quels sujets souhaitez-vous aborder ?",
    type: "multi_choice",
    position: null,
    slug: "sujets",
    url: "/questions/9007199254741021-sujets",
  },
];
const author = {
  id: "9007199254743993",
  name: "Auteur anonyme",
  is_anonymous: true,
  slug: "anonyme",
  url: "/authors/9007199254743993-anonyme",
};
const contributionIds = [
  "9007199254742993",
  "9007199254742994",
  "9007199254742995",
];
const reference = (id) => ({
  id,
  submitted_at: "2019-01-15T00:00:00",
  api_url: `/api/v1/forms/${forms[0].id}/contributions/${id}`,
});
const fullContribution = (id) => ({
  form: { id: forms[0].id, name: forms[0].name, url: forms[0].url },
  contribution: reference(id),
  author: id === "9007199254742995" ? null : author,
  legacy_index: null,
  previous_id:
    contributionIds.indexOf(id) > 0
      ? contributionIds[contributionIds.indexOf(id) - 1]
      : null,
  next_id:
    contributionIds.indexOf(id) >= 0
      ? (contributionIds[contributionIds.indexOf(id) + 1] ?? null)
      : null,
  answers:
    id === "9007199254742995"
      ? []
      : [
          {
            id: "9007199254741993",
            position: 1,
            question: questions[0],
            text:
              "Une réponse citoyenne.\n\nUn second paragraphe. <script>alert('non fiable')</script>\n" +
              "Texte complet très long. ".repeat(1500),
            selected_options: [],
            other_text: [],
            value: null,
          },
          {
            id: "9007199254741992",
            position: 2,
            question: questions[0],
            text: "Réponse du lot suivant.",
            selected_options: [],
            other_text: [],
            value: null,
          },
          {
            id: "9007199254741994",
            position: 1,
            question: questions[2],
            text: "Consultations citoyennes\nRéunions locales\nAutre proposition",
            selected_options: [
              {
                id: "9007199254744993",
                label: "Consultations citoyennes",
                position: 1,
              },
              {
                id: "9007199254744994",
                label: "Réunions locales",
                position: 2,
              },
            ],
            other_text: ["Autre proposition"],
            value: null,
          },
          {
            id: "9007199254741995",
            position: 1,
            question: questions[1],
            text: null,
            selected_options: [],
            other_text: [],
            value: "42",
          },
        ],
});
const questionStatistics = (source) => ({
  question_id: source.id,
  type: source.type,
  total_answers: 10,
  answered_contributions_count: 8,
  total_option_selections: 13,
  other_text_answers_count: 1,
  total_selections: 14,
  percentage_denominator: "total_answers",
  percentage_decimal_places: 2,
  categories: [
    {
      option_id: "9007199254744993",
      kind: "option",
      label:
        "Renforcer les consultations citoyennes, y compris dans les territoires les plus éloignés et pour toutes les générations",
      position: 1,
      count: 8,
      percentage: 80,
    },
    {
      option_id: "9007199254744994",
      kind: "option",
      label: "Organiser des réunions locales",
      position: 2,
      count: 5,
      percentage: 50,
    },
    {
      option_id: "9007199254744995",
      kind: "option",
      label: "Option sans sélection",
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
});
const publication = {
  status: "available",
  generation_id: "synthetic-generation",
  calculated_at: "2026-10-20T17:00:00Z",
  method_version: "historical-answers-v1",
};
function enrichedForm(id) {
  const source =
    id === forms[0].id
      ? forms[0]
      : {
          ...forms[0],
          id,
          url: `/forms/${id}`,
          name: "Questionnaire de contrôle (questions rapides)",
        };
  let entries = questions.map((q) => ({
    ...q,
    form_id: id,
    answers_count: 10,
    statistics: q.type === "text" ? null : questionStatistics(q),
  }));
  if (["101", "103", "104"].includes(id)) {
    const q = entries[1];
    const yes = id === "103" ? 0 : id === "104" ? 4 : 7;
    const no = id === "103" ? 0 : 3;
    const total = id === "103" ? 0 : 10;
    entries[1] = {
      ...q,
      answers_count: total,
      statistics: {
        ...q.statistics,
        total_answers: total,
        answered_contributions_count: total,
        total_option_selections: yes + no,
        total_selections: yes + no,
        other_text_answers_count: 0,
        categories: [
          {
            option_id: "9007199254744900",
            kind: "option",
            label: "Oui",
            position: 1,
            count: yes,
            percentage: yes * 10,
          },
          {
            option_id: "9007199254744901",
            kind: "option",
            label: "Non",
            position: 2,
            count: no,
            percentage: no * 10,
          },
        ],
      },
    };
  }
  if (id === "105")
    entries = Array.from({ length: 37 }, (_, i) => ({
      ...entries[0],
      id: String(9007199254741100n + BigInt(i)),
      prompt:
        `Question ${i + 1} : ` +
        "Un intitulé complet sur la participation citoyenne. ".repeat(3),
      url: `/questions/${9007199254741100n + BigInt(i)}-exemple`,
      position: i + 1,
    }));
  const available = id !== "102";
  return {
    ...source,
    questions_count: entries.length,
    statistics_availability: available
      ? publication
      : { status: "unavailable", reason: "incompatible" },
    questions: available
      ? entries
      : entries.map((q) => ({ ...q, answers_count: null, statistics: null })),
  };
}
const formCalls = [];
let searchRetry = 0;
const searchCalls = [];
const snapshots = new Map();
let snapshotId = 0;
let retry = 0;
let formRetry = 0;
const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "private, no-store");
  if (url.pathname === "/forms-reset") {
    formCalls.length = 0;
    response.end("{}");
    return;
  }
  if (url.pathname === "/forms-calls") {
    response.end(JSON.stringify(formCalls));
    return;
  }
  if (url.pathname.startsWith("/api/v1/forms")) formCalls.push(url.pathname);
  if (url.pathname === "/search-reset") {
    searchCalls.length = 0;
    searchRetry = 0;
    snapshots.clear();
    response.end("{}");
    return;
  }
  if (url.pathname === "/search-calls") {
    response.end(JSON.stringify(searchCalls));
    return;
  }
  if (url.pathname === "/search-expire") {
    snapshots.clear();
    response.end("{}");
    return;
  }
  if (url.pathname === "/api/v1/search") {
    const q = url.searchParams.get("q") ?? "";
    const cursor = url.searchParams.get("cursor");
    const pageSize = Number(url.searchParams.get("page_size") ?? 20);
    searchCalls.push({
      path: url.pathname,
      query: url.search,
      calculated: !cursor,
    });
    const fail = (status, code) => {
      response.statusCode = status;
      response.end(
        JSON.stringify({
          error: {
            code,
            message: "private SQL SECRET http://private-host",
            retryable: true,
          },
          request_id: "private",
        }),
      );
    };
    if (request.headers.cookie) {
      fail(403, "internal_error");
      return;
    }
    if (
      ["410", "422", "500", "503", "504"].includes(q) ||
      (q === "retry" && searchRetry++ === 0)
    ) {
      const status = q === "retry" ? 503 : Number(q);
      fail(
        status,
        {
          410: "search_expired",
          422: "invalid_query",
          500: "internal_error",
          503: "search_unavailable",
          504: "search_timeout",
        }[status],
      );
      return;
    }
    if (q === "invalid-json") {
      response.end("{invalid");
      return;
    }
    let snapshot = cursor ? snapshots.get(cursor) : null;
    if (
      cursor &&
      (!snapshot || snapshot.q !== q || snapshot.pageSize !== pageSize)
    ) {
      fail(410, "search_expired");
      return;
    }
    if (!cursor) {
      const id = ++snapshotId;
      snapshot = {
        q,
        pageSize,
        first: `first+${id}/=opaque`,
        next: `next+${id}/=opaque`,
      };
      snapshots.set(snapshot.first, snapshot);
      snapshots.set(snapshot.next, snapshot);
    }
    const next = cursor === snapshot.next;
    if (next && q === "pagination-error") {
      fail(503, "search_unavailable");
      return;
    }
    const empty = q === "absent" || q === "withdrawn";
    const items = empty
      ? []
      : Array.from({ length: next ? 1 : pageSize }, (_, index) => {
          const id = next
            ? "9007199254741995"
            : index === 0
              ? "9007199254741993"
              : index === 1
                ? "9007199254741992"
                : index === 2
                  ? "9007199254741994"
                  : String(9007199254742000n + BigInt(index));
          return {
            answer_id: id,
            contribution_id: contributionIds[0],
            rank: next ? pageSize + 1 : index + 1,
            texts:
              index === 2 && !next
                ? [
                    {
                      unit_type: "other_text",
                      unit_index: 0,
                      text: "Autre proposition A",
                    },
                    {
                      unit_type: "other_text",
                      unit_index: 2,
                      text: "Autre proposition B",
                    },
                  ]
                : [
                    {
                      unit_type: "open_answer",
                      unit_index: 0,
                      text: next
                        ? "Réponse du lot suivant."
                        : index === 0
                          ? `Une réponse pour ${q}.\n\n<script>alert('non fiable')</script>\n` +
                            "Texte long. ".repeat(60)
                          : index === 1
                            ? "Non"
                            : "Une parole citoyenne.",
                    },
                  ],
            is_truncated: !next && index === 0,
            question: {
              id: questions[0].id,
              prompt: questions[0].prompt,
              url: questions[0].url,
            },
            form: { id: forms[0].id, name: forms[0].name, url: forms[0].url },
            url: `/forms/${forms[0].id}/contributions/${contributionIds[0]}#answer-${id}`,
          };
        });
    const send = () =>
      response.end(
        JSON.stringify({
          q,
          state:
            q === "withdrawn"
              ? "sources_unavailable"
              : empty
                ? "empty"
                : "results",
          mode: "hybrid",
          recipe_version: "h1-test-v1",
          items,
          page_size: pageSize,
          has_next: !next && !empty,
          next_cursor: next || empty ? null : snapshot.next,
          previous_cursor: next ? snapshot.first : null,
          first_cursor: empty ? null : snapshot.first,
          expires_at: empty
            ? null
            : new Date(Date.now() + 600000).toISOString(),
          window: {
            document_limit: 50,
            retrieval_depth: 50,
            answer_count: empty ? 0 : pageSize + 1,
            exhaustive: false,
          },
          warnings: ["withdrawn", "warning"].includes(q)
            ? [
                {
                  code: "source_unavailable",
                  count: 1,
                  message: "Une source est indisponible.",
                },
              ]
            : [],
        }),
      );
    if (q === "slow") {
      const timer = setTimeout(send, 8500);
      response.on("close", () => clearTimeout(timer));
    } else send();
    return;
  }
  if (url.pathname === "/reset-form") {
    formRetry = 0;
    response.end("{}");
    return;
  }
  if (url.pathname === "/reset") {
    retry = 0;
    response.end("{}");
    return;
  }
  if (request.headers.cookie) {
    response.statusCode = 403;
    response.end("{}");
    return;
  }
  const dashboardMatch = /^\/api\/v1\/forms\/(\d+)\/stats$/.exec(url.pathname);
  if (dashboardMatch) {
    const id = dashboardMatch[1];
    if (["404", "500", "503", "504"].includes(id)) {
      response.statusCode = Number(id);
      response.end(
        JSON.stringify({ detail: "private SQL SECRET http://private-host" }),
      );
      return;
    }
    response.end(
      JSON.stringify({
        form: { id, name: forms[0].name, url: `/forms/${id}` },
        questions:
          id !== forms[0].id
            ? []
            : questions
                .filter((q) => q.type !== "text")
                .map((q) => ({ question: q, stats: questionStatistics(q) })),
      }),
    );
    return;
  }
  const browseMatch = /^\/api\/v1\/forms\/(\d+)\/contributions$/.exec(
    url.pathname,
  );
  if (browseMatch) {
    response.setHeader("Content-Type", "application/json");
    if (browseMatch[1] !== forms[0].id) {
      response.statusCode = 404;
      response.end(JSON.stringify({ detail: "Introuvable" }));
      return;
    }
    const rank = Math.min(
      3,
      Math.max(1, Number(url.searchParams.get("contrib") ?? "1")),
    );
    response.end(
      JSON.stringify({
        ...fullContribution(contributionIds[rank - 1]),
        legacy_index: String(rank),
      }),
    );
    return;
  }
  const authorMatch = /^\/api\/v1\/authors\/(\d+)(\/forms)?$/.exec(
    url.pathname,
  );
  const contributionMatch =
    /^\/api\/v1\/forms\/(\d+)\/contributions\/(\d+)$/.exec(url.pathname);
  if (authorMatch || contributionMatch) {
    const id = authorMatch?.[1] ?? contributionMatch[2];
    const status = ["404", "500", "503", "504"].includes(id)
      ? Number(id)
      : contributionMatch &&
          contributionMatch[1] !==
            (id === "9007199254742996" ? forms[1].id : forms[0].id)
        ? 404
        : 200;
    response.statusCode = status;
    if (status !== 200) {
      response.end(
        JSON.stringify({ detail: "private SQL / credentials / host" }),
      );
      return;
    }
    if (contributionMatch) {
      response.end(
        JSON.stringify(
          id === "9007199254742996"
            ? {
                ...fullContribution("9007199254742995"),
                contribution: {
                  ...reference(id),
                  api_url: `/api/v1/forms/${forms[1].id}/contributions/${id}`,
                },
                form: {
                  id: forms[1].id,
                  name: forms[1].name,
                  url: forms[1].url,
                },
              }
            : fullContribution(id),
        ),
      );
      return;
    }
    const publicAuthor =
      id === "9007199254743993"
        ? author
        : { ...author, id, name: "Pseudonyme public", is_anonymous: false };
    if (!authorMatch[2]) {
      response.end(JSON.stringify(publicAuthor));
      return;
    }
    const after = url.searchParams.get("after_id");
    if (id === "102") {
      response.statusCode = 503;
      response.end("{}");
      return;
    }
    const empty = id === "100";
    response.end(
      JSON.stringify({
        author_id: id,
        forms: empty
          ? []
          : after
            ? [
                {
                  id: forms[0].id,
                  name: forms[0].name,
                  url: forms[0].url,
                  contributions: [reference(contributionIds[2])],
                },
                {
                  id: forms[1].id,
                  name: forms[1].name,
                  url: forms[1].url,
                  contributions: [
                    {
                      ...reference("9007199254742996"),
                      api_url: `/api/v1/forms/${forms[1].id}/contributions/9007199254742996`,
                    },
                  ],
                },
              ]
            : [
                {
                  id: forms[0].id,
                  name: forms[0].name,
                  url: forms[0].url,
                  contributions: contributionIds.slice(0, 2).map(reference),
                },
              ],
        page_size: 20,
        has_next: !after && !empty,
        next_after_id: !after && !empty ? contributionIds[1] : null,
      }),
    );
    return;
  }
  const questionMatch =
    /^\/api\/v1\/questions\/(\d+)(?:\/(answers|stats))?$/.exec(url.pathname);
  if (questionMatch) {
    const [, qid, operation] = questionMatch;
    if (["404", "500", "503", "504"].includes(qid)) {
      response.statusCode = Number(qid);
      response.end(
        JSON.stringify({ detail: "private SQL / credentials / host" }),
      );
      return;
    }
    const source = questions.find((q) => q.id === qid) ?? {
      ...questions[0],
      id: qid,
      slug: "exemple",
    };
    const choice = source.type !== "text";
    if (
      (qid === "102" && operation === "stats") ||
      url.searchParams.get("cursor") === "fail"
    ) {
      response.statusCode = 503;
      response.end(
        JSON.stringify({ detail: "private SQL / credentials / host" }),
      );
      return;
    }
    if (!operation) {
      response.end(
        JSON.stringify({
          ...source,
          display_mode: choice || qid === "102" ? "choice" : "text",
          url: `/questions/${qid}-${source.slug}`,
          form: { id: forms[0].id, name: forms[0].name, url: forms[0].url },
        }),
      );
      return;
    }
    if (operation === "answers") {
      const cursor = url.searchParams.get("cursor");
      const empty = qid === "100";
      const items = empty
        ? []
        : [
            {
              id: cursor ? "9007199254741992" : "9007199254741993",
              question_id: qid,
              contribution_id: "9007199254742993",
              text:
                url.searchParams.get("other_only") === "true"
                  ? cursor
                    ? "Autre proposition suivante."
                    : "Une autre proposition citoyenne."
                  : cursor
                    ? "Réponse du lot suivant."
                    : "Une réponse citoyenne.\n\nUn second paragraphe. <script>alert('non fiable')</script>",
              submitted_at: cursor ? "2019-01-15T00:15:00" : null,
              is_truncated: !cursor,
              author: {
                id: "9007199254743993",
                name: "Auteur anonyme",
                is_anonymous: true,
                slug: "anonyme",
                url: "/authors/9007199254743993-anonyme",
              },
              url: "/answers/9007199254741993",
            },
          ];
      response.end(
        JSON.stringify({
          question_id: qid,
          items,
          page_size: 20,
          has_next: !cursor && !empty,
          next_cursor:
            cursor || empty ? null : qid === "101" ? "fail" : "page+2/=opaque",
        }),
      );
      return;
    }
    response.end(JSON.stringify(questionStatistics(source)));
    return;
  }
  if (url.pathname === "/api/v1/forms") {
    response.end(JSON.stringify(forms));
    return;
  }
  const enrichedMatch =
    /^\/api\/v1\/forms\/(9007199254740995|101|102|103|104|105)$/.exec(
      url.pathname,
    );
  if (enrichedMatch) {
    response.end(JSON.stringify(enrichedForm(enrichedMatch[1])));
    return;
  }
  const id = url.pathname.split("/").at(-1);
  if (["404", "500", "503", "504"].includes(id)) {
    response.statusCode = Number(id);
    response.end(
      JSON.stringify({ detail: "private SQL / credentials / host" }),
    );
    return;
  }
  if ((id === "7" && retry++ === 0) || (id === "9" && formRetry++ === 0)) {
    response.statusCode = 503;
    response.end("{}");
    return;
  }
  const send = () =>
    response.end(
      JSON.stringify({
        id,
        name: "Formulaire synthétique",
        questions_count: 0,
        url: `/forms/${id}`,
        questions: [],
        statistics_availability: { status: "unavailable", reason: "absent" },
      }),
    );
  if (id === "8") {
    const timer = setTimeout(send, 8500);
    response.on("close", () => clearTimeout(timer));
  } else send();
});
server.listen(4176, "127.0.0.1");
