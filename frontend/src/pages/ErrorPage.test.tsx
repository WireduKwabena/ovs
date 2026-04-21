// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";

import ErrorPage from "./ErrorPage";

// ---------------------------------------------------------------------------
// Minimal store helpers
// ---------------------------------------------------------------------------
const makeStore = (message: string | null, status?: string) =>
  configureStore({
    reducer: {
      error: () => ({ message, status: status ?? null }),
    },
  });

const renderPage = (message: string | null, status?: string) =>
  render(
    <Provider store={makeStore(message, status)}>
      <MemoryRouter>
        <ErrorPage />
      </MemoryRouter>
    </Provider>,
  );

describe("ErrorPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders nothing when there is no error message", () => {
    const { container } = renderPage(null);
    expect(container.firstChild).toBeNull();
  });

  it("renders the error overlay when a message is present", () => {
    renderPage("Something went wrong");
    expect(screen.getByText("An Error Occurred")).toBeTruthy();
    expect(screen.getByText("Something went wrong")).toBeTruthy();
  });

  it("shows the HTTP status code when provided", () => {
    renderPage("Not found", "404");
    expect(screen.getByText(/status: 404/i)).toBeTruthy();
  });

  it("shows a Go Back button", () => {
    renderPage("Server failure");
    expect(screen.getByRole("button", { name: /go back/i })).toBeTruthy();
  });
});
