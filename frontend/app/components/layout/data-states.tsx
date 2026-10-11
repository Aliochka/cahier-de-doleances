import { useEffect, useState } from "react";
import { css } from "../../../styled-system/css";
import { type ApiErrorKind, LONG_WAIT_MS } from "../../lib/api";
import { errorMessages } from "../../lib/api-errors";
import { Alert } from "../ui/alert";
import { Button } from "../ui/button";
import { Skeleton } from "../ui/skeleton";

export function LoadingState({ active }: { active: boolean }) {
  const [prolonged, setProlonged] = useState(false);
  useEffect(() => {
    if (!active) {
      setProlonged(false);
      return;
    }
    const timer = setTimeout(() => setProlonged(true), LONG_WAIT_MS);
    return () => clearTimeout(timer);
  }, [active]);
  if (!active) return null;
  return (
    <section
      aria-label="Chargement de la page"
      className={css({ display: "grid", gap: "3", py: "4" })}
    >
      <p role="status">
        {prolonged
          ? "Le chargement prend plus de temps que prévu…"
          : "Chargement en cours…"}
      </p>
      <div aria-busy="true" className={css({ display: "grid", gap: "3" })}>
        <Skeleton />
        <Skeleton />
      </div>
    </section>
  );
}
export function ErrorState({
  kind,
  retry,
  pending = false,
}: {
  kind: ApiErrorKind;
  retry?: () => void;
  pending?: boolean;
}) {
  const maintenance = ["network", "configuration", "unavailable"].includes(
    kind,
  );
  const title =
    kind === "missing"
      ? "Page introuvable"
      : maintenance
        ? "Service indisponible"
        : "Une erreur est survenue";
  return (
    <>
      <title>{`${title} — Cahier de doléances`}</title>
      <meta name="robots" content="noindex, nofollow" />
      <h1>{title}</h1>
      <Alert variant={maintenance ? "warning" : "error"}>
        {errorMessages[kind]}
      </Alert>
      <div
        className={css({
          display: "flex",
          flexWrap: "wrap",
          gap: "4",
          alignItems: "center",
          mt: "6",
        })}
      >
        {retry && kind !== "missing" && (
          <Button onClick={retry} loading={pending}>
            Réessayer
          </Button>
        )}
        <a href="/">Retour à l’accueil</a>
      </div>
    </>
  );
}
export function EmptyState({
  children = "Aucun résultat disponible.",
}: {
  children?: string;
}) {
  return <Alert>{children}</Alert>;
}
