// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ForgotPasswordPage from "./ForgotPasswordPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  authState: {
    loading: false,
    error: null as string | null,
    passwordResetEmailSent: false,
  },
}));

vi.mock("react-redux", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-redux")>();
  return {
    ...actual,
    useDispatch: () => mocks.dispatch,
    useSelector: (selector: (state: unknown) => unknown) =>
      selector({ auth: mocks.authState }),
  };
});

vi.mock("@/store/authSlice", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/store/authSlice")>();
  return {
    ...actual,
    clearError: vi.fn(() => ({ type: "auth/clearError" })),
    resetPasswordStatus: vi.fn(() => ({ type: "auth/resetPasswordStatus" })),
    requestPasswordReset: vi.fn(() => ({ type: "auth/requestPasswordReset" })),
  };
});

vi.mock("react-toastify", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderPage = () =>
  render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ForgotPasswordPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.authState.loading = false;
    mocks.authState.error = null;
    mocks.authState.passwordResetEmailSent = false;
  });

  it("renders the forgot password form with email input", () => {
    renderPage();
    expect(screen.getByText(/forgot password/i)).toBeTruthy();
    expect(screen.getByLabelText(/work email/i)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /send reset link/i }),
    ).toBeTruthy();
  });

  it("shows validation error when submitting with empty email", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeTruthy();
    });
    expect(mocks.dispatch).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "auth/requestPasswordReset" }),
    );
  });

  it("dispatches requestPasswordReset on valid email submission", async () => {
    mocks.dispatch.mockResolvedValue({});
    renderPage();

    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(mocks.dispatch).toHaveBeenCalled();
    });
  });

  it("shows success state with Send another link button after email is sent", () => {
    mocks.authState.passwordResetEmailSent = true;
    renderPage();

    expect(
      screen.getByRole("button", { name: /send another link/i }),
    ).toBeTruthy();
    // The main form should not be visible
    expect(
      screen.queryByRole("button", { name: /send reset link/i }),
    ).toBeNull();
  });

  it("shows loading state while the request is in flight", () => {
    mocks.authState.loading = true;
    renderPage();

    expect(screen.getByText(/sending link/i)).toBeTruthy();
  });
});
