import { Form, Link } from "react-router";
import { css } from "../../../styled-system/css";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { type SearchState, searchUrl } from "./search-url";

export function SearchControls({
  state,
  draft,
  onDraftChange,
  error,
}: {
  state: SearchState;
  draft: string;
  onDraftChange: (value: string) => void;
  error?: string;
}) {
  return (
    <>
      <Form
        method="get"
        action="/recherche"
        role="search"
        className={css({ display: "grid", gap: "4", mb: "6" })}
      >
        <Input
          name="q"
          type="search"
          label="Mots-clés"
          description="Saisissez un mot ou une expression, puis lancez la recherche."
          maxLength={512}
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          error={error}
        />
        <input type="hidden" name="tab" value={state.tab} />
        <div>
          <Button type="submit">Rechercher</Button>
        </div>
      </Form>
      <nav aria-label="Ensembles de recherche" className={css({ mb: "8" })}>
        <ul
          className={css({
            display: "flex",
            flexWrap: "wrap",
            gap: "3",
            listStyle: "none",
            p: 0,
          })}
        >
          {(
            [
              ["answers", "Réponses"],
              ["catalog", "Questions et enquêtes"],
            ] as const
          ).map(([tab, label]) => (
            <li key={tab}>
              <Link
                to={searchUrl({ q: state.q, tab })}
                aria-current={state.tab === tab ? "page" : undefined}
                className={css({
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: "control",
                  px: "4",
                  py: "2",
                  border: "panel",
                  borderRadius: "control",
                  "&[aria-current]": {
                    background: "primary",
                    color: "onPrimary",
                    fontWeight: "bold",
                  },
                })}
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}
