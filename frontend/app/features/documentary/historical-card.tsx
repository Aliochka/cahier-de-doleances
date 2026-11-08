import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { Alert } from "../../components/ui/alert";
import type { HistoricalSearchResult } from "../../lib/api";
import {
  CitizenText,
  contributionStyles,
} from "../contributions/contribution-presentation";

export function HistoricalCard({ item }: { item: HistoricalSearchResult }) {
  return (
    <li data-progressive-id={`1789:${item.document_id}`} tabIndex={-1}>
      <article
        className={contributionStyles.entry}
        aria-labelledby={`cahier-${item.document_id}`}
      >
        <p className={contributionStyles.metadata}>
          Cahiers de doléances — 1789
        </p>
        <h3
          id={`cahier-${item.document_id}`}
          className={contributionStyles.question}
        >
          <Link to={item.url}>{item.title}</Link>
        </h3>
        {(item.place || item.orders.length > 0) && (
          <p className={contributionStyles.metadata}>
            {[item.place, ...item.orders].filter(Boolean).join(" · ")}
          </p>
        )}
        {item.match_origin === "metadata" && (
          <p
            className={css({ fontSize: "secondary", color: "muted", mt: "3" })}
          >
            Correspondance dans les métadonnées du cahier. Extrait d’ouverture.
          </p>
        )}
        <blockquote className={css({ mx: "0", my: "5" })}>
          <CitizenText>{item.excerpt}</CitizenText>
        </blockquote>
        {item.warnings.map((w) => (
          <Alert key={w.code} variant="warning">
            {w.message}
          </Alert>
        ))}
        <footer className={css({ display: "grid", gap: "3", mt: "5" })}>
          <p>
            <Link to={item.url}>Lire le cahier intégral à cet emplacement</Link>
          </p>
          {item.reference && (
            <details className={contributionStyles.metadata}>
              <summary>Référence historique</summary>
              <p className={css({ mt: "2" })}>{item.reference}</p>
            </details>
          )}
        </footer>
      </article>
    </li>
  );
}
