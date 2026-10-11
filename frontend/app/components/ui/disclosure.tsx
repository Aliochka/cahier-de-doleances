import { Collapsible } from "@ark-ui/react/collapsible";
import type { ReactNode } from "react";
import { css } from "../../../styled-system/css";

// A single accessible primitive to verify Ark UI styling and hydration.
export function Disclosure({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Collapsible.Root
      defaultOpen
      className={css({
        mt: "8",
        border: "panel",
        borderRadius: "panel",
        bg: "surface",
        p: "4",
      })}
    >
      <Collapsible.Trigger
        className={css({
          color: "primary",
          fontWeight: "bold",
          cursor: "pointer",
          textAlign: "left",
        })}
      >
        {title}
        <Collapsible.Indicator aria-hidden="true"> +</Collapsible.Indicator>
      </Collapsible.Trigger>
      <Collapsible.Content className={css({ pt: "3" })}>
        {children}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
