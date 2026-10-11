import type { ComponentProps } from "react";
import { css, cx } from "../../../styled-system/css";

export function PageContainer({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      {...props}
      className={cx(
        css({
          width: "100%",
          maxWidth: "page",
          mx: "auto",
          px: { base: "4", md: "8" },
          py: "6",
        }),
        className,
      )}
    />
  );
}
