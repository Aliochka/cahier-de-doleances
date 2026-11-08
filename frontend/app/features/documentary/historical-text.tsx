import { css } from "../../../styled-system/css";
import type { DocumentaryReading } from "../../lib/api";

// Canonical fragments are already sliced in Unicode codepoints by the backend.
// Collapse layout whitespace only, without trimming fragment boundaries or
// repairing hyphenation/OCR. CSS collapses adjacent spaces across inline marks.
export function HistoricalText({
  paragraphs,
}: Pick<DocumentaryReading, "paragraphs">) {
  return (
    <section
      aria-label="Texte intégral du cahier"
      className={css({
        textStyle: "citizenReading",
        maxWidth: "reading",
        minWidth: 0,
        whiteSpace: "normal",
        textAlign: "start",
        overflowWrap: "anywhere",
        "& p": { mb: "5" },
        "& h2": { textStyle: "documentSection", mt: "8", mb: "5" },
      })}
    >
      {paragraphs.map((p) => {
        const Element = p.kind === "heading" ? "h2" : "p";
        return (
          <Element key={p.start_offset}>
            {p.fragments.map((f) => {
              const value = f.text.replace(/\s+/gu, " ");
              return f.selected ? (
                <mark
                  key="selected"
                  id={f.anchor ?? undefined}
                  className={css({
                    background: "warningSurface",
                    color: "text",
                    scrollMarginTop: "12",
                  })}
                >
                  {value}
                </mark>
              ) : (
                <span key={f === p.fragments[0] ? "before" : "after"}>
                  {value}
                </span>
              );
            })}
          </Element>
        );
      })}
    </section>
  );
}
