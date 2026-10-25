import { Form } from "react-router";
import { css } from "../../../styled-system/css";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

export function SearchControls({
  draft,
  onDraftChange,
  error,
  pending = false,
  path,
}: {
  draft: string;
  onDraftChange: (value: string) => void;
  error?: string;
  pending?: boolean;
  path?: string;
}) {
  return (
    <Form
      method="get"
      action={path ?? "/recherche"}
      role="search"
      className={css({
        display: "grid",
        gap: "4",
        mb: "8",
        maxWidth: "reading",
      })}
    >
      {path && <input type="hidden" name="tab" value="search" />}
      <Input
        id="search-query"
        name="q"
        type="search"
        label={
          path
            ? "Rechercher dans les réponses"
            : "Votre question ou votre sujet"
        }
        description="Une question naturelle ou quelques mots suffisent. 512 caractères maximum."
        placeholder="Par exemple : Pouvoir d’achat"
        maxLength={512}
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        error={error}
      />
      <div>
        <Button type="submit" aria-busy={pending || undefined}>
          Rechercher
        </Button>
      </div>
    </Form>
  );
}
