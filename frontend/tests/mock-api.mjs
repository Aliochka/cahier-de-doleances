// Loopback-only synthetic API. No request is forwarded to Wallace.
import { createServer } from "node:http";

let retry = 0;
const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "private, no-store");
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
  const id = url.pathname.split("/").at(-1);
  if (["404", "500", "503", "504"].includes(id)) {
    response.statusCode = Number(id);
    response.end(
      JSON.stringify({ detail: "private SQL / credentials / host" }),
    );
    return;
  }
  if (id === "7" && retry++ === 0) {
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
