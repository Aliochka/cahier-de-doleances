import { Link } from "react-router";
import { css, cx } from "../../../styled-system/css";

const linkStyle = css({
  textStyle: "documentLink",
  color: "text",
  background: "transparent",
  minHeight: "control",
  display: "inline-flex",
  alignItems: "center",
  py: "2",
  borderBottomWidth: "thin",
  borderColor: "border",
  textDecoration: "none",
  overflowWrap: "anywhere",
  _hover: {
    color: "primary",
    borderColor: "primary",
    textDecoration: "underline",
  },
  _focusVisible: {
    color: "primary",
    borderColor: "primary",
    textDecoration: "underline",
  },
});

export function DocumentNavigation({
  label,
  previous,
  next,
  previousLabel,
  nextLabel,
}: {
  label: string;
  previous: string | null;
  next: string | null;
  previousLabel: string;
  nextLabel: string;
}) {
  if (!previous && !next) return null;
  return (
    <nav
      aria-label={label}
      className={css({
        display: "flex",
        flexDirection: { base: "column", sm: "row" },
        justifyContent: "space-between",
        gap: "4",
        my: "6",
        maxWidth: "reading",
        minWidth: 0,
      })}
    >
      {previous && (
        <Link className={linkStyle} to={previous}>
          {previousLabel}
        </Link>
      )}
      {next && (
        <Link
          className={cx(
            linkStyle,
            css({ marginInlineStart: { base: "0", sm: "auto" } }),
          )}
          to={next}
        >
          {nextLabel}
        </Link>
      )}
    </nav>
  );
}
