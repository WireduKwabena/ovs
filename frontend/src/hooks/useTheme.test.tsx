// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ThemeProvider, themeStorageKey, useTheme } from "./useTheme";

const ThemeHarness: React.FC = () => {
  const { resolvedTheme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button type="button" onClick={toggleTheme}>
        Toggle Theme
      </button>
    </div>
  );
};

describe("ThemeProvider", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    window.localStorage.clear();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: "(prefers-color-scheme: dark)",
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  it("defaults to light resolved theme and applies document attribute", () => {
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("resolved-theme").textContent).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("toggles and persists theme choice", () => {
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem(themeStorageKey)).toBe("dark");
  });
});
