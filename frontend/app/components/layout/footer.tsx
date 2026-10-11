import { css } from "../../../styled-system/css";
import { PageContainer } from "./page-container";

export function Footer() {
  return (
    <footer
      className={css({
        borderTopWidth: "thin",
        borderColor: "border",
        color: "muted",
        fontSize: "secondary",
      })}
    >
      <PageContainer>© Cahier de doléances</PageContainer>
    </footer>
  );
}
