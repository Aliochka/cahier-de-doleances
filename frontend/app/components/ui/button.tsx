import type { ComponentProps } from "react";
import { cva, cx } from "../../../styled-system/css";

export const buttonStyles = cva({
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
    textDecoration: "none",
    textAlign: "center",
    py: "2",
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
        _hover: { textDecoration: "underline", background: "primaryHover" },
        _active: { background: "primaryActive" },
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

export type ButtonVariants = {
  variant?: "primary" | "secondary" | "quiet" | "destructive";
  size?: "small" | "medium" | "large";
};

type Props = ComponentProps<"button"> & ButtonVariants & { loading?: boolean };

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
      className={cx(buttonStyles({ variant, size }), className)}
    >
      {loading && <span aria-hidden="true">…</span>}
      {children}
    </button>
  );
}
