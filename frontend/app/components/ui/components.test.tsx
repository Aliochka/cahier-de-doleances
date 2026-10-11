import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Alert } from "./alert";
import { Button } from "./button";
import { Card } from "./card";
import { Dialog } from "./dialog";
import { Input } from "./input";
import { Skeleton } from "./skeleton";
import { Tabs } from "./tabs";

describe("Contrôles natifs", () => {
  it("préserve les variantes, le type et les états indisponibles des boutons", async () => {
    const click = vi.fn();
    const user = userEvent.setup();
    render(
      <>
        <Button onClick={click}>Principal</Button>
        <Button variant="secondary">Secondaire</Button>
        <Button variant="quiet" disabled onClick={click}>
          Désactivé
        </Button>
        <Button variant="destructive" loading onClick={click}>
          Suppression
        </Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Principal" })).toHaveAttribute(
      "type",
      "button",
    );
    expect(
      screen.getByRole("button", { name: "Secondaire" }).className,
    ).not.toBe(screen.getByRole("button", { name: "Principal" }).className);
    await user.click(screen.getByRole("button", { name: "Principal" }));
    await user.click(screen.getByRole("button", { name: "Désactivé" }));
    await user.click(screen.getByRole("button", { name: "Suppression" }));
    expect(click).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Suppression" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Suppression" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });
  it("associe label, description et erreur tout en conservant les attributs de formulaire", () => {
    render(
      <form aria-label="Exemple">
        <Input
          id="name"
          label="Nom"
          name="name"
          description="Un pseudonyme suffit."
          error="Champ obligatoire."
          required
          defaultValue="Exemple"
        />
        <Input label="Indisponible" disabled />
      </form>,
    );
    const input = screen.getByRole("textbox", { name: "Nom" });
    expect(input).toHaveAccessibleDescription(
      "Un pseudonyme suffit. Champ obligatoire.",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toBeRequired();
    expect(
      new FormData(screen.getByRole<HTMLFormElement>("form")).get("name"),
    ).toBe("Exemple");
    expect(
      screen.getByRole("textbox", { name: "Indisponible" }),
    ).toBeDisabled();
  });
});

it("laisse le parent contrôler les onglets et signale les changements", async () => {
  const user = userEvent.setup();
  const change = vi.fn();
  const example = (value: string) => (
    <Tabs.Root value={value} onValueChange={change}>
      <Tabs.List aria-label="Exemples">
        <Tabs.Trigger value="one">Premier</Tabs.Trigger>
        <Tabs.Trigger value="two">Second</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="one">Contenu premier</Tabs.Content>
      <Tabs.Content value="two">Contenu second</Tabs.Content>
    </Tabs.Root>
  );
  const view = render(example("one"));
  await user.click(screen.getByRole("tab", { name: "Premier" }));
  await waitFor(() =>
    expect(screen.getByRole("tab", { name: "Premier" })).toHaveFocus(),
  );
  await user.click(screen.getByRole("tab", { name: "Second" }));
  await waitFor(() =>
    expect(change).toHaveBeenCalledWith(
      expect.objectContaining({ value: "two" }),
    ),
  );
  view.rerender(example("two"));
  expect(screen.getByRole("tab", { name: "Second" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await waitFor(() =>
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Contenu second"),
  );
});

it("ouvre un dialogue nommé, le ferme au clavier et restitue le focus", async () => {
  const user = userEvent.setup();
  render(
    <Dialog.Root lazyMount unmountOnExit>
      <Dialog.Trigger asChild>
        <Button>Ouvrir</Button>
      </Dialog.Trigger>
      <Dialog.Content title="Confirmation" description="Une explication.">
        <Input label="Message" />
      </Dialog.Content>
    </Dialog.Root>,
  );
  const trigger = screen.getByRole("button", { name: "Ouvrir" });
  await user.click(trigger);
  expect(
    await screen.findByRole("dialog", { name: "Confirmation" }),
  ).toHaveAccessibleDescription("Une explication.");
  await user.click(screen.getByRole("textbox", { name: "Message" }));
  await user.keyboard("{Escape}");
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("sépare l'urgence des alertes de leur variante visuelle", () => {
  render(
    <>
      <Alert variant="error">Erreur informative</Alert>
      <Alert variant="success" announcement="polite">
        Enregistré
      </Alert>
      <Alert variant="warning" announcement="assertive">
        Attention immédiate
      </Alert>
    </>,
  );
  expect(screen.getByText("Erreur informative")).not.toHaveAttribute("role");
  expect(screen.getByRole("status")).toHaveTextContent("Enregistré");
  expect(screen.getByRole("alert")).toHaveTextContent("Attention immédiate");
});

it("conserve une carte sémantique et masque les placeholders décoratifs", () => {
  render(
    <>
      <Card aria-labelledby="card-title">
        <h2 id="card-title">Document</h2>
      </Card>
      <Skeleton data-testid="placeholder" />
    </>,
  );
  expect(screen.getByRole("article", { name: "Document" })).toBeInTheDocument();
  expect(screen.getByTestId("placeholder")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
});
