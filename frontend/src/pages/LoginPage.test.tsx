// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mock LoginForm so we don't pull in the full Redux + auth stack
// ---------------------------------------------------------------------------
vi.mock("@/components/auth/LoginForm", () => ({
  LoginForm: () => <div data-testid="login-form">LoginForm</div>,
}));

// Must import AFTER mocks are registered
const { LoginPage } = await import("./LoginPage");

const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

describe("LoginPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the LoginForm component", () => {
    renderPage();
    expect(screen.getByTestId("login-form")).toBeTruthy();
  });
});
