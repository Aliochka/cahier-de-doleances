import type { ComponentProps } from "react";
import { cva, cx } from "../../../styled-system/css";

const styles = cva({
  base: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "2",
    px: "4",
    borderWidth: "thin",
    borderStyle: "solid",
    borderRadius: "control",
    fontWeight: "semibold",
    whiteSpace: "normal",
    overflowWrap: "anywhere",
    cursor: "pointer",
    _disabled: {
      color: "disabledText",
      background: "disabledSurface",
      borderColor: "border",
      cursor: "not-allowed",
    },
  },
  variants: {
    variant: {
      primary: {
        background: "primary",
        color: "onPrimary",
        borderColor: "primary",
        _hover: { textDecoration: "underline" },
      },
      secondary: {
        background: "surface",
        color: "primary",
        borderColor: "controlBorder",
        _hover: { textDecoration: "underline" },
      },
      quiet: {
        background: "transparent",
        color: "primary",
        borderColor: "transparent",
        _hover: { textDecoration: "underline" },
      },
      destructive: {
        background: "danger",
        color: "onPrimary",
        borderColor: "danger",
        _hover: { textDecoration: "underline" },
      },
    },
    size: {
      small: { minHeight: "controlSmall", fontSize: "secondary" },
      medium: { minHeight: "control" },
      large: { minHeight: "controlLarge", px: "6" },
    },
  },
  defaultVariants: { variant: "primary", size: "medium" },
});

type Props = ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "quiet" | "destructive";
  size?: "small" | "medium" | "large";
  loading?: boolean;
};

export function Button({
  variant,
  size,
  loading = false,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: Props) {
  return (
    <button
      {...props}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(styles({ variant, size }), className)}
    >
      {loading && <span aria-hidden="true">…</span>}
      {children}
    </button>
  );
}
