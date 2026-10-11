import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Disclosure } from "../components/ui/disclosure";

export default function Home() {
  return (
    <PageContainer>
      <title>Cahier de doléances — Les voix du Grand Débat</title>
      <meta
        name="description"
        content="Explorez les contributions citoyennes du Grand Débat National avec Cahier de doléances."
      />
      <h1
        className={css({
          fontFamily: "archive",
          fontSize: "title",
          lineHeight: "title",
          color: "primary",
          mb: "6",
        })}
      >
        Cahier de doléances
      </h1>
      <p>
        Une application open source pour explorer les contributions citoyennes
        du Grand Débat National et mieux comprendre les préoccupations exprimées
        par les Français.
      </p>
      <Disclosure title="À propos du projet">
        <p>
          Faire vivre les paroles citoyennes et rendre ces archives accessibles
          à toutes et à tous.
        </p>
      </Disclosure>
    </PageContainer>
  );
}
