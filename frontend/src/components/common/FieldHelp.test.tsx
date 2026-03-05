// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { HelpTooltip } from "./FieldHelp";

describe("FieldHelp", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens tooltip on click and closes on outside click", async () => {
    render(
      <div>
        <HelpTooltip text="Explain this field" />
        <button type="button">outside</button>
      </div>,
    );

    const trigger = screen.getByRole("button", { name: "Help: Explain this field" });
    const tooltip = screen.getByRole("tooltip");

    expect(tooltip.className.includes("hidden")).toBe(true);

    fireEvent.click(trigger);

    await waitFor(() => {
      expect(tooltip.className.includes("block")).toBe(true);
      expect(tooltip.className.includes("hidden")).toBe(false);
    });

    fireEvent.mouseDown(document.body);

    await waitFor(() => {
      expect(tooltip.className.includes("hidden")).toBe(true);
    });
  });

  it("closes tooltip on Escape key press", async () => {
    render(<HelpTooltip text="Keyboard close help" />);

    const trigger = screen.getByRole("button", { name: "Help: Keyboard close help" });
    const tooltip = screen.getByRole("tooltip");

    fireEvent.click(trigger);

    await waitFor(() => {
      expect(tooltip.className.includes("block")).toBe(true);
      expect(tooltip.className.includes("hidden")).toBe(false);
    });

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(tooltip.className.includes("hidden")).toBe(true);
    });
  });
});
