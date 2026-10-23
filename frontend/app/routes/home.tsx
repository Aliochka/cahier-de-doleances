import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { LinkButton } from "../components/ui/link-button";
export default function Home() {
  return (
    <PageContainer className={css({ py: { base: "6", md: "16" } })}>
      <title>Cahier de doléances — Les paroles citoyennes</title>
      <meta
        name="description"
        content="Explorez les enquêtes et recherchez dans les contributions citoyennes avec Cahier de doléances."
      />
      <div
        className={css({
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: "4",
          borderBottomWidth: "thin",
          borderColor: "border",
          pb: "4",
          mb: { base: "6", md: "12" },
          textStyle: "annotation",
          color: "muted",
        })}
      >
        <span>Archives citoyennes</span>
        <span className={css({ display: { base: "none", md: "inline" } })}>
          Consultations publiques
        </span>
      </div>
      <section
        aria-labelledby="home-title"
        className={css({
          display: "grid",
          gridTemplateColumns: {
            base: "minmax(0, 1fr)",
            md: "minmax(0, 1.2fr) minmax(0, 1fr)",
          },
          columnGap: { base: "2", md: "12" },
          rowGap: { base: "4", md: "6" },
          alignItems: "center",
        })}
      >
        <h1
          id="home-title"
          className={css({
            gridColumn: "1",
            textStyle: "projectHero",
            color: "text",
            mb: "0",
          })}
        >
          Cahier de doléances
        </h1>
        <img
          src="/favicon.svg"
          alt=""
          width="512"
          height="512"
          decoding="async"
          className={css({
            gridColumn: { base: "1", md: "2" },
            gridRow: { base: "2", md: "1 / 4" },
            width: { base: "logoCompact", md: "100%" },
            maxWidth: { base: "100%", md: "logo" },
            height: "auto",
            justifySelf: { base: "center", md: "end" },
          })}
        />
        <p
          className={css({
            display: { base: "none", md: "block" },
            gridColumn: "1",
            gridRow: "2",
            textStyle: "annotation",
            color: "accent",
          })}
        >
          Lire. Explorer. Comprendre.
        </p>
        <p
          className={css({
            gridColumn: "1",
            gridRow: "3",
            textStyle: "editorial",
            maxWidth: "reading",
          })}
        >
          Des paroles citoyennes à découvrir. Explorez les consultations
          publiques et les idées qui s’y expriment.
        </p>
        <div
          className={css({
            gridColumn: "1 / -1",
            display: "flex",
            flexDirection: { base: "column", sm: "row" },
            alignItems: { base: "stretch", sm: "flex-start" },
            gap: "4",
            mt: { base: "2", md: "4" },
          })}
        >
          <LinkButton to="/enquetes" size="large">
            Explorer les enquêtes
          </LinkButton>
          <LinkButton to="/recherche" variant="secondary" size="large">
            Rechercher dans les contributions
          </LinkButton>
        </div>
      </section>
      <p
        className={css({
          borderTopWidth: "thin",
          borderColor: "border",
          mt: { base: "8", md: "16" },
          pt: "4",
          textStyle: "editorialBody",
          fontSize: "secondary",
          color: "muted",
          maxWidth: "reading",
        })}
      >
        Un projet ouvert pour rendre les contributions citoyennes accessibles à
        toutes et à tous.
      </p>
    </PageContainer>
  );
}
