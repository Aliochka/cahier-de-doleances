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
let retry = 0;
let formRetry = 0;
const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "private, no-store");
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
              text: cursor
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
    response.end(
      JSON.stringify({
        question_id: qid,
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
      }),
    );
    return;
  }
  if (url.pathname === "/api/v1/forms") {
    response.end(JSON.stringify(forms));
    return;
  }
  if (url.pathname === `/api/v1/forms/${forms[0].id}`) {
    response.end(JSON.stringify({ ...forms[0], questions }));
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
      }),
    );
  if (id === "8") {
    const timer = setTimeout(send, 8500);
    response.on("close", () => clearTimeout(timer));
  } else send();
});
server.listen(4176, "127.0.0.1");
