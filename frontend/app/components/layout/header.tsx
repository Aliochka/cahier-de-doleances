import { Link, NavLink, useMatch } from "react-router";
import { css } from "../../../styled-system/css";
import { PageContainer } from "./page-container";

export function Header() {
  const surveysMatch = useMatch("/enquetes");
  const formMatch = useMatch("/forms/:formId/*");
  return (
    <header
      className={css({
        borderBottomWidth: "thin",
        borderColor: "border",
        background: "surfaceSecondary",
        "& > div": { py: { base: "3", md: "4" } },
      })}
    >
      <PageContainer
        className={css({
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: { base: "2", md: "6" },
        })}
      >
        <NavLink
          to="/"
          end
          aria-label="Accueil — Cahier de doléances"
          className={css({
            textStyle: "projectIdentity",
            color: "text",
            textDecoration: "none",
            minHeight: "control",
            display: "flex",
            alignItems: "center",
            overflowWrap: "anywhere",
            minWidth: 0,
            maxWidth: "100%",
            gap: "2",
          })}
        >
          <img
            src="/favicon.svg"
            alt=""
            width="512"
            height="512"
            className={css({
              width: "controlSmall",
              height: "auto",
              flexShrink: 0,
            })}
          />
          <span className={css({ minWidth: 0 })}>Cahier de doléances</span>
        </NavLink>
        <nav aria-label="Navigation principale">
          <ul
            className={css({
              display: "flex",
              flexWrap: "wrap",
              gap: { base: "4", md: "6" },
              textStyle: "documentNavigation",
            })}
          >
            <li>
              <Link
                to="/enquetes"
                aria-current={
                  surveysMatch ? "page" : formMatch ? "location" : undefined
                }
                className={css({
                  color: "text",
                  textUnderlineOffset: "0.3em",
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: "control",
                  "&[aria-current]": { textDecorationThickness: "3px" },
                })}
              >
                Enquêtes
              </Link>
            </li>
            <li>
              <NavLink
                to="/recherche"
                className={css({
                  color: "text",
                  textUnderlineOffset: "0.3em",
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: "control",
                  "&[aria-current]": { textDecorationThickness: "3px" },
                })}
              >
                Recherche
              </NavLink>
            </li>
          </ul>
        </nav>
      </PageContainer>
    </header>
  );
}
