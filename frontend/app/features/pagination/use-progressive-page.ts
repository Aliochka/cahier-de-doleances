import { type MouseEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useNavigation } from "react-router";

type Snapshot = {
  identity: string;
  pages: unknown[];
  y: number;
  expires: number;
  bytes: number;
  source?: unknown;
};
// Public content only, in this tab's memory. No storage, cookies or SSR cache.
const snapshots = new Map<string, Snapshot>();
const ttl = 10 * 60 * 1000;
const maxBytes = 4 * 1024 * 1024;
function save(key: string, snapshot: Snapshot) {
  snapshots.delete(key);
  if (snapshot.bytes > maxBytes) return;
  snapshots.set(key, snapshot);
  let bytes = [...snapshots.values()].reduce(
    (sum, value) => sum + value.bytes,
    0,
  );
  for (const [id, value] of snapshots) {
    if (
      value.expires <= Date.now() ||
      snapshots.size > 16 ||
      bytes > maxBytes
    ) {
      snapshots.delete(id);
      bytes -= value.bytes;
    }
  }
}
function read<T>(
  key: string | undefined,
  identity: string,
): (Omit<Snapshot, "pages"> & { pages: T[] }) | null {
  const value = key ? snapshots.get(key) : undefined;
  return value && value.identity === identity && value.expires > Date.now()
    ? (value as Omit<Snapshot, "pages"> & { pages: T[] })
    : null;
}

export function useProgressivePage<T extends object>({
  page,
  identity,
  merge,
  ids,
}: {
  page: T | null;
  identity: string;
  merge: (pages: T[]) => T;
  ids: (page: T) => string[];
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const navigation = useNavigation();
  const [record, setRecord] = useState({
    key: location.key,
    identity,
    pages: page ? [page] : [],
  });
  const active = useRef<Snapshot | null>(null);
  const recordRef = useRef(record);
  recordRef.current = record;
  const merged =
    record.key === location.key &&
    record.identity === identity &&
    record.pages.length
      ? merge(record.pages)
      : page;
  const pending =
    navigation.state !== "idle" &&
    navigation.location?.pathname === location.pathname &&
    typeof navigation.location.state?.progressiveFrom === "string";

  useEffect(() => {
    const own = read<T>(location.key, identity);
    const fromKey =
      typeof location.state?.progressiveFrom === "string"
        ? location.state.progressiveFrom
        : undefined;
    const previousRecord = recordRef.current;
    const inherited =
      read<T>(fromKey, identity) ??
      (fromKey === previousRecord.key && previousRecord.identity === identity
        ? {
            identity,
            pages: previousRecord.pages,
            y: window.scrollY,
            expires: Date.now() + ttl,
            bytes: 0,
          }
        : null);
    const current = page;
    const pages =
      (own
        ? current && own.source !== current
          ? [...(own.source ? own.pages.slice(0, -1) : own.pages), current]
          : own.pages
        : null) ??
      (inherited
        ? [...inherited.pages, ...(current ? [current] : [])]
        : current
          ? [current]
          : []);
    const snapshot: Snapshot = {
      identity,
      pages,
      source: current,
      y: own?.y ?? inherited?.y ?? window.scrollY,
      expires: own?.expires ?? inherited?.expires ?? Date.now() + ttl,
      bytes: new TextEncoder().encode(JSON.stringify(pages)).length,
    };
    active.current = snapshot;
    save(location.key, snapshot);
    setRecord({ key: location.key, identity, pages });
    const restoredY = snapshot.y;
    let restoring = !!(own || inherited);
    let frame = 0;
    let secondFrame = 0;
    frame = requestAnimationFrame(() => {
      secondFrame = requestAnimationFrame(() => {
        if (own || inherited)
          window.scrollTo({ top: restoredY, behavior: "instant" });
        restoring = false;
        if (!own && inherited && current) {
          const oldIds = new Set(inherited.pages.flatMap(ids));
          const id = ids(current).find((value) => !oldIds.has(value));
          if (id)
            document
              .querySelector<HTMLElement>(
                `[data-progressive-id="${CSS.escape(id)}"]`,
              )
              ?.focus({ preventScroll: true });
        }
      });
    });
    const scroll = () => {
      if (!restoring && active.current === snapshot)
        snapshot.y = window.scrollY;
    };
    const freeze = () => {
      if (active.current === snapshot) {
        snapshot.y = window.scrollY;
        active.current = null;
      }
    };
    window.addEventListener("scroll", scroll, { passive: true });
    // Capture position before navigation changes the document/scroll height.
    const leaving = (event: globalThis.MouseEvent) => {
      if (
        event.button === 0 &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        !event.altKey &&
        event.target instanceof Element &&
        event.target.closest("a[href]")
      )
        freeze();
    };
    document.addEventListener("click", leaving, true);
    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(secondFrame);
      window.removeEventListener("scroll", scroll);
      document.removeEventListener("click", leaving, true);
    };
  }, [location.key, identity, location.state, ids, page]);

  function loadMore(href: string, event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    event.preventDefault();
    if (navigation.state !== "idle") return;
    const snapshot = snapshots.get(location.key);
    if (snapshot) snapshot.y = window.scrollY;
    navigate(href, {
      preventScrollReset: true,
      state: { progressiveFrom: location.key },
    });
  }
  return { page: merged, pending, loadMore };
}
