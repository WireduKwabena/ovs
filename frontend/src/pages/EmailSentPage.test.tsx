// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { EmailSentPage } from "./EmailSentPage";

const mocks = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/auth.service", () => ({
  authService: { requestPasswordReset: mocks.requestPasswordReset },
}));

vi.mock("react-toastify", () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}));

const renderWithEmail = (email?: string) =>
  render(
    <MemoryRouter
      initialEntries={[
        { pathname: "/email-sent", state: email ? { email } : {} },
      ]}
    >
      <Routes>
        <Route path="/email-sent" element={<EmailSentPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("EmailSentPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows email-context-missing state when no email in location state", () => {
    renderWithEmail();
    expect(screen.getByText(/email context missing/i)).toBeTruthy();
    expect(
      screen.getByRole("link", { name: /request reset link/i }),
    ).toBeTruthy();
  });

  it("shows check-your-inbox state when email is provided", () => {
    renderWithEmail("user@example.com");
    expect(screen.getByText(/check your inbox/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /resend email/i })).toBeTruthy();
  });

  it("masks the email address in the inbox view", () => {
    renderWithEmail("john@company.org");
    // masked: jo****@company.org
    expect(screen.getByText(/jo\*+@company\.org/)).toBeTruthy();
  });

  it("calls authService.requestPasswordReset when Resend email is clicked", async () => {
    mocks.requestPasswordReset.mockResolvedValue({});
    renderWithEmail("user@example.com");

    fireEvent.click(screen.getByRole("button", { name: /resend email/i }));

    await waitFor(() => {
      expect(mocks.requestPasswordReset).toHaveBeenCalledWith(
        "user@example.com",
      );
    });
    await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalled());
  });
});
