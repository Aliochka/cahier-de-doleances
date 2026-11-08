// Never returns the SSR-only token to the browser.
export function localPreviewRequest(request: Request): boolean {
  return (
    process.env.DOCUMENTARY_LOCAL_PREVIEW === "1" &&
    request.headers.get("sec-fetch-site") !== "cross-site" &&
    ["127.0.0.1", "localhost", "[::1]"].includes(
      new URL(request.url).hostname,
    ) &&
    !["forwarded", "x-forwarded-host", "x-forwarded-for"].some((h) =>
      request.headers.has(h),
    )
  );
}
