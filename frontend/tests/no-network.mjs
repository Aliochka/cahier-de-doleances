// Used only by the offline build and SSR tests; never included in the application.
import { Socket } from "node:net";

const connect = Socket.prototype.connect;
Socket.prototype.connect = function (...args) {
  const options = Array.isArray(args[0]) ? args[0][0] : args[0];
  // Local IPC may be needed by build tools; external TCP remains forbidden.
  if (
    (typeof options === "object" && options?.path) ||
    (typeof options === "string" && options.startsWith("/"))
  ) {
    return connect.apply(this, args);
  }
  const host = typeof options === "object" ? options.host : args[1];
  // React Router 8 prerenders by calling its own temporary loopback server.
  if (host === undefined || ["localhost", "127.0.0.1", "::1"].includes(host)) {
    return connect.apply(this, args);
  }
  throw new Error(
    "Network access is forbidden during the frontend offline build",
  );
};
const fetch = globalThis.fetch;
globalThis.fetch = (input, init) => {
  const url = new URL(input instanceof Request ? input.url : input);
  if (!["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    throw new Error(
      "External fetch is forbidden during the frontend offline build",
    );
  }
  return fetch(input, init);
};
