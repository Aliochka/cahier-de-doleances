import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, LoadingState } from "./data-states";

afterEach(() => vi.useRealTimers());
it("annonce l'attente prolongée après huit secondes et nettoie le délai", () => {
  vi.useFakeTimers();
  const view = render(<LoadingState active />);
  expect(screen.getByRole("status")).toHaveTextContent("Chargement en cours");
  act(() => {
    vi.advanceTimersByTime(8000);
  });
  expect(screen.getByRole("status")).toHaveTextContent("plus de temps");
  view.rerender(<LoadingState active={false} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(vi.getTimerCount()).toBe(0);
  view.rerender(<LoadingState active />);
  expect(screen.getByRole("status")).toHaveTextContent("Chargement en cours");
});
it("réessaie manuellement et distingue maintenance, erreur ponctuelle et absence", async () => {
  const retry = vi.fn();
  const view = render(<ErrorState kind="network" retry={retry} />);
  expect(
    screen.getByRole("heading", { name: "Service indisponible" }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
  expect(retry).toHaveBeenCalledTimes(1);
  view.rerender(<ErrorState kind="application" retry={retry} />);
  expect(
    screen.getByRole("heading", { name: "Une erreur est survenue" }),
  ).toBeInTheDocument();
  view.rerender(<ErrorState kind="missing" retry={retry} />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  view.rerender(<EmptyState />);
  expect(screen.getByText("Aucun résultat disponible.")).toBeInTheDocument();
});
