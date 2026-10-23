import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { EmptyState } from "../../components/layout/data-states";
import type { AuthorFormsPage } from "../../lib/api";
import { ListNavigation, type MoreAction } from "../pagination/list-navigation";

export function AuthorForms({
  page,
  path,
  after,
  onMore,
  pending,
}: {
  page: AuthorFormsPage;
  path: string;
  after: string | null;
  onMore?: MoreAction;
  pending?: boolean;
}) {
  return (
    <section
      aria-labelledby="author-forms-title"
      className={css({ minWidth: 0, overflowWrap: "anywhere" })}
    >
      <h2 id="author-forms-title">Formulaires et contributions</h2>
      <p role="status" className={css({ color: "muted", mb: "6" })}>
        {page.forms.reduce((sum, form) => sum + form.contributions.length, 0)}{" "}
        contributions affichées.
      </p>
      {page.forms.length === 0 ? (
        <EmptyState>Aucune contribution consultable dans ce lot.</EmptyState>
      ) : (
        <ul
          className={css({
            listStyle: "none",
            p: 0,
            display: "grid",
            gap: "8",
          })}
        >
          {page.forms.map((form) => (
            <li
              key={form.id}
              className={css({
                borderTopWidth: "thin",
                borderColor: "border",
                pt: "6",
              })}
            >
              <h3>
                <Link to={`/forms/${form.id}`}>{form.name}</Link>
              </h3>
              <ul
                className={css({ display: "grid", gap: "4", mt: "4", pl: "6" })}
              >
                {form.contributions.map((contribution) => (
                  <li
                    key={contribution.id}
                    data-progressive-id={contribution.id}
                    tabIndex={-1}
                    className={css({ textStyle: "documentMetadata" })}
                  >
                    <Link
                      to={`/forms/${form.id}/contributions/${contribution.id}`}
                    >
                      Consulter la contribution {contribution.id}
                    </Link>
                    {contribution.submitted_at && (
                      <>
                        {" "}
                        ·{" "}
                        <time dateTime={contribution.submitted_at}>
                          {contribution.submitted_at.slice(0, 10)}
                        </time>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
      <ListNavigation
        label="Lots de contributions"
        first={after !== null ? path : null}
        next={
          page.has_next && page.next_after_id
            ? `${path}?${new URLSearchParams({ after_id: page.next_after_id })}`
            : null
        }
        nextLabel="Afficher davantage de contributions"
        pending={pending}
        onMore={onMore}
      />
    </section>
  );
}
