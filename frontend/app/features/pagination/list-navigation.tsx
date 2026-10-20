import type { MouseEvent } from "react";
import { Link } from "react-router";
import styles from "./pagination.module.css";

export type MoreAction = (
  href: string,
  event: MouseEvent<HTMLAnchorElement>,
) => void;
export function ListNavigation({
  label,
  first,
  previous,
  next,
  firstLabel = "Revenir au début",
  previousLabel = "← Précédent",
  nextLabel = "Afficher davantage de réponses",
  pending = false,
  onMore,
}: {
  label: string;
  first?: string | null;
  previous?: string | null;
  next?: string | null;
  firstLabel?: string;
  previousLabel?: string;
  nextLabel?: string;
  pending?: boolean;
  onMore?: MoreAction;
}) {
  if (!first && !previous && !next) return null;
  return (
    <nav aria-label={label} className={styles.navigation}>
      {previous && (
        <Link className={styles.secondary} to={previous}>
          {previousLabel}
        </Link>
      )}
      {first && (
        <Link className={styles.secondary} to={first}>
          {firstLabel}
        </Link>
      )}
      {next && (
        <Link
          className={styles.more}
          to={next}
          aria-disabled={pending || undefined}
          aria-busy={pending || undefined}
          onClick={(event) => {
            if (pending) event.preventDefault();
            else onMore?.(next, event);
          }}
        >
          {nextLabel}
        </Link>
      )}
      {pending && <p role="status">Chargement en cours…</p>}
    </nav>
  );
}
