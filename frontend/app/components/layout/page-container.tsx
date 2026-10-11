import type { ReactNode } from "react";
import { css } from "../../../styled-system/css";

export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <main
      className={css({
        maxWidth: "48rem",
        mx: "auto",
        px: { base: "4", md: "8" },
        py: "10",
      })}
    >
      {children}
    </main>
  );
}
