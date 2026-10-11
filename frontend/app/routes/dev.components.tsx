import { useState } from "react";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import { Tabs } from "../components/ui/tabs";

const swatches = [
  { name: "Papier", style: css({ background: "background" }) },
  { name: "Surface", style: css({ background: "surface" }) },
  {
    name: "Bleu principal",
    style: css({ background: "primary", color: "onPrimary" }),
  },
  {
    name: "Rouge tampon",
    style: css({ background: "accent", color: "onPrimary" }),
  },
];
const row = css({
  display: "flex",
  flexWrap: "wrap",
  gap: "3",
  alignItems: "center",
});

export default function Components() {
  const [tab, setTab] = useState("presentation");
  return (
    <PageContainer>
      <title>Composants — Cahier de doléances</title>
      <meta name="robots" content="noindex, nofollow" />
      <h1>Atelier des composants</h1>
      <p>Cette page de démonstration est réservée au développement.</p>
      <div className={css({ display: "grid", gap: "10", mt: "8" })}>
        <section aria-labelledby="palette">
          <h2 id="palette">Couleurs et typographie</h2>
          <div className={row}>
            {swatches.map((swatch) => (
              <Card key={swatch.name} className={swatch.style}>
                {swatch.name}
              </Card>
            ))}
          </div>
          <h3 className={css({ mt: "6" })}>Une hiérarchie sobre</h3>
          <p className={css({ maxWidth: "reading" })}>
            Les titres évoquent les archives. Les textes courants utilisent la
            police du système pour rester lisibles pendant de longues sessions
            de lecture.
          </p>
          <p className={css({ color: "muted", fontSize: "caption" })}>
            Une légende apporte un complément discret.
          </p>
        </section>
        <section aria-labelledby="buttons">
          <h2 id="buttons">Boutons</h2>
          <div className={row}>
            <Button>Principal</Button>
            <Button variant="secondary">Secondaire</Button>
            <Button variant="quiet">Discret</Button>
            <Button variant="destructive">Supprimer</Button>
            <Button size="small">Petit</Button>
            <Button size="large">Grand</Button>
            <Button disabled>Désactivé</Button>
            <Button loading>Chargement</Button>
          </div>
          <p>Utilisez Tab pour visualiser le focus clavier.</p>
        </section>
        <section aria-labelledby="fields">
          <h2 id="fields">Champs</h2>
          <div
            className={css({ display: "grid", gap: "6", maxWidth: "reading" })}
          >
            <Input
              label="Intitulé"
              description="Une description facultative."
              name="example"
            />
            <Input
              label="Champ avec erreur"
              error="Renseignez ce champ."
              required
            />
            <Input
              label="Champ désactivé"
              disabled
              defaultValue="Indisponible"
            />
          </div>
        </section>
        <section aria-labelledby="cards">
          <h2 id="cards">Cartes</h2>
          <Card aria-labelledby="document">
            <h3 id="document">Un document à consulter</h3>
            <p>
              Une surface simple pour de futurs contenus, sans interaction
              imposée.
            </p>
            <p>
              TexteSansEspacePourVérifierLaLectureSurUnPetitÉcranEtÉviterToutDébordementHorizontal
            </p>
          </Card>
        </section>
        <section aria-labelledby="tabs">
          <h2 id="tabs">Onglets</h2>
          <Tabs.Root
            value={tab}
            onValueChange={(details) => setTab(details.value)}
          >
            <Tabs.List aria-label="Démonstration">
              <Tabs.Trigger value="presentation">Présentation</Tabs.Trigger>
              <Tabs.Trigger value="examples">Exemples</Tabs.Trigger>
              <Tabs.Trigger value="unavailable" disabled>
                Indisponible
              </Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="presentation">
              Le premier panneau est rendu côté serveur.
            </Tabs.Content>
            <Tabs.Content value="examples">
              Le second panneau est sélectionné au clavier ou à la souris.
            </Tabs.Content>
            <Tabs.Content value="unavailable">Indisponible</Tabs.Content>
          </Tabs.Root>
          <Tabs.Root defaultValue="one" variant="enclosed">
            <Tabs.List aria-label="Variante encadrée">
              <Tabs.Trigger value="one">Encadré</Tabs.Trigger>
              <Tabs.Trigger value="two">Autre panneau</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="one">
              Une seconde variante visuelle.
            </Tabs.Content>
            <Tabs.Content value="two">Un autre contenu.</Tabs.Content>
          </Tabs.Root>
        </section>
        <section aria-labelledby="dialogs">
          <h2 id="dialogs">Dialogues</h2>
          <Dialog.Root lazyMount unmountOnExit>
            <Dialog.Trigger asChild>
              <Button>Afficher un dialogue</Button>
            </Dialog.Trigger>
            <Dialog.Content
              title="Un dialogue accessible"
              description="Le focus reste dans cette fenêtre jusqu’à sa fermeture."
            >
              <Input label="Texte de démonstration" />
              <div className={css({ mt: "6" })}>
                <Dialog.CloseTrigger asChild>
                  <Button variant="secondary">Fermer</Button>
                </Dialog.CloseTrigger>
              </div>
            </Dialog.Content>
          </Dialog.Root>
        </section>
        <section aria-labelledby="alerts">
          <h2 id="alerts">Alertes</h2>
          <div className={css({ display: "grid", gap: "4" })}>
            <Alert heading="Information">
              Un message sans annonce automatique.
            </Alert>
            <Alert variant="success" announcement="polite">
              Démonstration : opération réussie.
            </Alert>
            <Alert variant="warning">Démonstration : point à vérifier.</Alert>
            <Alert variant="error" announcement="assertive">
              Démonstration : erreur urgente.
            </Alert>
          </div>
        </section>
        <section aria-labelledby="loading">
          <h2 id="loading">Chargement</h2>
          <p role="status">Exemple de contenu en chargement.</p>
          <div aria-busy="true" className={css({ display: "grid", gap: "3" })}>
            <Skeleton />
            <Skeleton />
            <Skeleton variant="block" />
          </div>
        </section>
      </div>
    </PageContainer>
  );
}
