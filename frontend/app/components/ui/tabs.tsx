import { Tabs as ArkTabs } from "@ark-ui/react/tabs";
import type { ComponentProps } from "react";
import { css, cx } from "../../../styled-system/css";

function Root({
  className,
  variant = "underline",
  ...props
}: ComponentProps<typeof ArkTabs.Root> & {
  variant?: "underline" | "enclosed";
}) {
  return (
    <ArkTabs.Root
      {...props}
      data-variant={variant}
      className={cx(
        css({
          minWidth: 0,
          '&[data-variant="enclosed"] [data-part="list"]': {
            background: "surfaceSecondary",
            border: "panel",
            borderRadius: "control",
            p: "1",
          },
        }),
        className,
      )}
    />
  );
}
function List({ className, ...props }: ComponentProps<typeof ArkTabs.List>) {
  return (
    <ArkTabs.List
      {...props}
      className={cx(
        css({
          display: "flex",
          flexWrap: "wrap",
          gap: "2",
          borderBottomWidth: "thin",
          borderColor: "border",
        }),
        className,
      )}
    />
  );
}
function Trigger({
  className,
  ...props
}: ComponentProps<typeof ArkTabs.Trigger>) {
  return (
    <ArkTabs.Trigger
      {...props}
      className={cx(
        css({
          flex: "1",
          minWidth: 0,
          minHeight: "control",
          px: "3",
          py: "2",
          whiteSpace: "normal",
          overflowWrap: "anywhere",
          cursor: "pointer",
          borderBottomWidth: "emphasis",
          borderColor: "transparent",
          color: "muted",
          _selected: {
            color: "primary",
            borderColor: "primary",
            fontWeight: "semibold",
          },
          _disabled: { color: "disabledText", cursor: "not-allowed" },
        }),
        className,
      )}
    />
  );
}
function Content({
  className,
  ...props
}: ComponentProps<typeof ArkTabs.Content>) {
  return (
    <ArkTabs.Content
      {...props}
      className={cx(
        css({ py: "6", minWidth: 0, overflowWrap: "anywhere" }),
        className,
      )}
    />
  );
}
export const Tabs = { Root, List, Trigger, Content };
