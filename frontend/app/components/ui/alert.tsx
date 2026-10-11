import type { ComponentProps } from "react";
import { cva, cx } from "../../../styled-system/css";

const styles = cva({
  base: {
    p: "4",
    borderLeftWidth: "emphasis",
    borderStyle: "solid",
    borderRadius: "control",
    overflowWrap: "anywhere",
  },
  variants: {
    variant: {
      info: {
        color: "primary",
        background: "infoSurface",
        borderColor: "primary",
      },
      success: {
        color: "success",
        background: "successSurface",
        borderColor: "success",
      },
      warning: {
        color: "warning",
        background: "warningSurface",
        borderColor: "warning",
      },
      error: {
        color: "danger",
        background: "dangerSurface",
        borderColor: "danger",
      },
    },
  },
  defaultVariants: { variant: "info" },
});
export function Alert({
  variant,
  announcement = "off",
  heading,
  className,
  children,
  role,
  ...props
}: ComponentProps<"div"> & {
  variant?: "info" | "success" | "warning" | "error";
  announcement?: "off" | "polite" | "assertive";
  heading?: string;
}) {
  return (
    <div
      {...props}
      role={
        role ??
        (announcement === "assertive"
          ? "alert"
          : announcement === "polite"
            ? "status"
            : undefined)
      }
      className={cx(styles({ variant }), className)}
    >
      {heading && <p className={cssHeading}>{heading}</p>}
      {children}
    </div>
  );
}
const cssHeading = cva({ base: { fontWeight: "semibold", mb: "2" } })();
