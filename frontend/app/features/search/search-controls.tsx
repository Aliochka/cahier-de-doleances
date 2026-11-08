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
  corpus = "tous",
  onCorpusChange,
  corpora,
}: {
  draft: string;
  onDraftChange: (value: string) => void;
  error?: string;
  pending?: boolean;
  path?: string;
  corpus?: "tous" | "2019" | "1789";
  onCorpusChange?: (value: "tous" | "2019" | "1789") => void;
  corpora?: import("../../lib/api").CorpusOption[];
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
        description={
          path
            ? "Saisissez des mots-clés. Recherche plein texte en français, limitée à 512 caractères."
            : "Une question naturelle ou quelques mots suffisent. 512 caractères maximum."
        }
        placeholder="Par exemple : Pouvoir d’achat"
        maxLength={512}
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        error={error}
      />
      {!path && (
        <div
          className={css({
            display: "grid",
            gap: "2",
            minWidth: 0,
            fontFamily: "interface",
          })}
        >
          <label
            htmlFor="search-corpus"
            className={css({ fontWeight: "semibold" })}
          >
            Corpus
          </label>
          <select
            id="search-corpus"
            name="corpus"
            value={corpus}
            onChange={(e) => {
              onCorpusChange?.(e.target.value as "tous" | "2019" | "1789");
              e.currentTarget.form?.requestSubmit();
            }}
            className={css({
              minHeight: "control",
              width: "100%",
              px: "3",
              background: "surface",
              borderWidth: "thin",
              borderColor: "controlBorder",
              borderRadius: "control",
              fontFamily: "interface",
            })}
          >
            <option value="tous">Tous les corpus disponibles</option>
            <option value="2019">Grand Débat national — 2019</option>
            <option
              value="1789"
              disabled={
                corpora?.find((c) => c.id === "1789")?.available !== true
              }
            >
              Cahiers de doléances — 1789
            </option>
          </select>
        </div>
      )}
      <div>
        <Button type="submit" aria-busy={pending || undefined}>
          Rechercher
        </Button>
      </div>
    </Form>
  );
}
