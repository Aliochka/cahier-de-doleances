import { Link, NavLink, useMatch } from "react-router";
import { css } from "../../../styled-system/css";
import { PageContainer } from "./page-container";

export function Header() {
  const surveysMatch = useMatch("/enquetes");
  const formMatch = useMatch("/forms/:formId");
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
            <li>
              <span
                aria-disabled="true"
                className={css({
                  color: "muted",
                  display: "inline-flex",
                  flexDirection: "column",
                })}
              >
                Recherche
                <span className={css({ fontSize: "caption" })}>À venir</span>
              </span>
            </li>
            <li>
              <Link
                to="/enquetes"
                aria-current={
                  surveysMatch ? "page" : formMatch ? "location" : undefined
                }
                className={css({
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: "control",
                  "&[aria-current]": { fontWeight: "bold" },
                })}
              >
                Enquêtes
              </Link>
            </li>
          </ul>
        </nav>
      </PageContainer>
    </header>
  );
}
