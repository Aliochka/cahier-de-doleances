import { NavLink } from "react-router";
import { css } from "../../../styled-system/css";
import { PageContainer } from "./page-container";

export function Header() {
  return (
    <header
      className={css({
        borderBottomWidth: "thin",
        borderColor: "border",
        background: "surfaceSecondary",
      })}
    >
      <PageContainer
        className={css({
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "6",
        })}
      >
        <NavLink
          to="/"
          end
          aria-label="Accueil — Cahier de doléances"
          className={css({
            fontFamily: "archive",
            fontWeight: "bold",
            fontSize: "section",
            textDecoration: "none",
            minHeight: "control",
            display: "flex",
            alignItems: "center",
            overflowWrap: "anywhere",
            minWidth: 0,
          })}
        >
          Cahier de doléances
        </NavLink>
        <nav aria-label="Navigation principale">
          <ul
            className={css({
              display: "flex",
              flexWrap: "wrap",
              gap: "6",
              fontSize: "navigation",
            })}
          >
            {["Recherche", "Enquêtes"].map((label) => (
              <li key={label}>
                <span
                  aria-disabled="true"
                  className={css({
                    color: "muted",
                    display: "inline-flex",
                    flexDirection: "column",
                  })}
                >
                  {label}
                  <span className={css({ fontSize: "caption" })}>À venir</span>
                </span>
              </li>
            ))}
          </ul>
        </nav>
      </PageContainer>
    </header>
  );
}
