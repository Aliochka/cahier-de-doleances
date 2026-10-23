import { Link, type LinkProps } from "react-router";
import { cx } from "../../../styled-system/css";
import { type ButtonVariants, buttonStyles } from "./button";
export function LinkButton({
  variant,
  size,
  className,
  ...props
}: LinkProps & ButtonVariants) {
  return (
    <Link
      {...props}
      className={cx(buttonStyles({ variant, size }), className)}
    />
  );
}
