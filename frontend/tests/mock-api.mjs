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
