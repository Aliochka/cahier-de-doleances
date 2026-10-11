import type { ComponentProps } from "react";
import { cva, cx } from "../../../styled-system/css";

const styles = cva({
  base: {
    background: "skeleton",
    borderRadius: "control",
    animation: "skeleton-pulse 2s ease-in-out infinite",
    _motionReduce: { animation: "none" },
    width: "100%",
  },
  variants: {
    variant: { line: { height: "1rem" }, block: { height: "8rem" } },
  },
  defaultVariants: { variant: "line" },
});
export function Skeleton({
  variant,
  className,
  ...props
}: ComponentProps<"div"> & { variant?: "line" | "block" }) {
  return (
    <div
      {...props}
      aria-hidden="true"
      data-skeleton=""
      className={cx(styles({ variant }), className)}
    />
  );
}
