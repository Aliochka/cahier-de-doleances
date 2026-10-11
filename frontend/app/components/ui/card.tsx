import type { ComponentProps } from "react";
import { css, cx } from "../../../styled-system/css";

export function Card({ className, ...props }: ComponentProps<"article">) {
  return (
    <article
      {...props}
      className={cx(
        css({
          background: "surface",
          border: "panel",
          borderRadius: "panel",
          p: "6",
          minWidth: 0,
          overflowWrap: "anywhere",
        }),
        className,
      )}
    />
  );
}
