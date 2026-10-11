import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { Disclosure } from "./disclosure";

test("disclosure is open initially and supports keyboard toggling", async () => {
  const user = userEvent.setup();
  render(<Disclosure title="À propos">Les paroles citoyennes</Disclosure>);
  const trigger = screen.getByRole("button", { name: "À propos" });
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Les paroles citoyennes")).toBeVisible();
  trigger.focus();
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(trigger).toHaveAttribute("aria-expanded", "false"),
  );
  expect(screen.getByText("Les paroles citoyennes")).not.toBeVisible();
  await user.keyboard(" ");
  await waitFor(() => expect(trigger).toHaveAttribute("aria-expanded", "true"));
});
