import { Dialog as ArkDialog } from "@ark-ui/react/dialog";
import { Portal } from "@ark-ui/react/portal";
import type { ComponentProps } from "react";
import { css, cx } from "../../../styled-system/css";
import { Button } from "./button";

function Content({
  title,
  description,
  children,
  className,
  ...props
}: Omit<ComponentProps<typeof ArkDialog.Content>, "title"> & {
  title: string;
  description?: string;
}) {
  return (
    <Portal>
      <ArkDialog.Backdrop
        className={css({
          position: "fixed",
          inset: 0,
          background: "overlay",
          zIndex: "overlay",
        })}
      />
      <ArkDialog.Positioner
        className={css({
          position: "fixed",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          p: "4",
          zIndex: "modal",
        })}
      >
        <ArkDialog.Content
          {...props}
          className={cx(
            css({
              width: "100%",
              maxWidth: "dialog",
              maxHeight: "calc(100dvh - 2rem)",
              overflowY: "auto",
              background: "surface",
              border: "panel",
              borderRadius: "panel",
              p: { base: "4", md: "6" },
              minWidth: 0,
            }),
            className,
          )}
        >
          <div
            className={css({
              display: "flex",
              alignItems: "start",
              gap: "4",
              justifyContent: "space-between",
            })}
          >
            <ArkDialog.Title asChild>
              <h2>{title}</h2>
            </ArkDialog.Title>
            <ArkDialog.CloseTrigger asChild>
              <Button variant="quiet" aria-label="Fermer la fenêtre">
                ×
              </Button>
            </ArkDialog.CloseTrigger>
          </div>
          {description && (
            <ArkDialog.Description className={css({ color: "muted", mb: "6" })}>
              {description}
            </ArkDialog.Description>
          )}
          {children}
        </ArkDialog.Content>
      </ArkDialog.Positioner>
    </Portal>
  );
}
export const Dialog = {
  Root: ArkDialog.Root,
  Trigger: ArkDialog.Trigger,
  CloseTrigger: ArkDialog.CloseTrigger,
  Content,
};
