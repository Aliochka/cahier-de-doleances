import { type ComponentProps, useId } from "react";
import { css, cx } from "../../../styled-system/css";

type Props = ComponentProps<"input"> & {
  label: string;
  description?: string;
  error?: string;
};
export function Input({
  label,
  description,
  error,
  id,
  className,
  "aria-describedby": describedBy,
  "aria-invalid": invalid,
  ...props
}: Props) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const descriptionId = `${inputId}-description`;
  const errorId = `${inputId}-error`;
  const references = [
    describedBy,
    description && descriptionId,
    error && errorId,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={css({ display: "grid", gap: "2", minWidth: 0 })}>
      <label htmlFor={inputId} className={css({ fontWeight: "semibold" })}>
        {label}
      </label>
      {description && (
        <p
          id={descriptionId}
          className={css({ fontSize: "secondary", color: "muted" })}
        >
          {description}
        </p>
      )}
      <input
        {...props}
        id={inputId}
        aria-describedby={references || undefined}
        aria-invalid={error ? true : invalid}
        className={cx(
          css({
            width: "100%",
            minWidth: 0,
            minHeight: "control",
            px: "3",
            background: "surface",
            borderWidth: "thin",
            borderStyle: "solid",
            borderColor: "controlBorder",
            borderRadius: "control",
            _invalid: { borderColor: "danger" },
            _disabled: { background: "disabledSurface", color: "disabledText" },
          }),
          className,
        )}
      />
      {error && (
        <p
          id={errorId}
          className={css({ color: "danger", fontSize: "secondary" })}
        >
          {error}
        </p>
      )}
    </div>
  );
}
