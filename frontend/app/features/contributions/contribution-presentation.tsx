import type { ComponentProps } from "react";
import { css, cx } from "../../../styled-system/css";

// Share the editorial treatment, while each view keeps its own semantic structure.
export const contributionStyles = {
  list: css({ listStyle: "none", p: "0", maxWidth: "reading", minWidth: 0 }),
  entry: css({
    borderTopWidth: "thin",
    borderColor: "border",
    py: { base: "6", md: "8" },
    minWidth: 0,
    overflowWrap: "anywhere",
    scrollMarginTop: "6",
  }),
  metadata: css({
    textStyle: "documentMetadata",
    overflowWrap: "anywhere",
    "& a": { textUnderlineOffset: "0.2em" },
  }),
  question: css({
    textStyle: "documentQuestion",
    mb: "5",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    "& a": {
      color: "inherit",
      textDecoration: "underline",
      textUnderlineOffset: "0.2em",
    },
  }),
  reading: css({
    textStyle: "citizenReading",
    maxWidth: "reading",
    minWidth: 0,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  }),
};

export function CitizenText({ className, ...props }: ComponentProps<"p">) {
  return <p {...props} className={cx(contributionStyles.reading, className)} />;
}
