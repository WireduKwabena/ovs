// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  acceptInvitation: vi.fn(),
}));

vi.mock("@/services/invitation.service", () => ({
  invitationService: { acceptInvitation: mocks.acceptInvitation },
}));

// lucide icons as no-ops to avoid SVG render issues
vi.mock("lucide-react", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    CheckCircle2: () => null,
    AlertTriangle: () => null,
  };
});

const { default: InvitationAcceptPage } =
  await import("./InvitationAcceptPage");

const renderWithToken = (token: string) =>
  render(
    <MemoryRouter initialEntries={[`/invitation/${token}/accept`]}>
      <Routes>
        <Route
          path="/invitation/:token/accept"
          element={<InvitationAcceptPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

describe("InvitationAcceptPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows validating state while accepting the invitation", async () => {
    // Never resolves so we see the loading state
    mocks.acceptInvitation.mockReturnValue(new Promise(() => {}));
    renderWithToken("tok123");
    expect(screen.getByText(/validating invitation/i)).toBeTruthy();
  });

  it("shows success payload after acceptance", async () => {
    mocks.acceptInvitation.mockResolvedValue({
      message: "ok",
      campaign: "VP Vetting 2025",
      candidate_email: "alice@example.com",
      enrollment_status: "registered",
    });
    renderWithToken("tok123");
    await waitFor(() =>
      expect(screen.getByText(/VP Vetting 2025/)).toBeTruthy(),
    );
    expect(screen.getByText("alice@example.com")).toBeTruthy();
    expect(screen.getByText(/enrollment status:/i)).toBeTruthy();
  });

  it("shows error message when acceptance fails", async () => {
    mocks.acceptInvitation.mockRejectedValue({
      response: { data: { error: "Token expired" } },
    });
    renderWithToken("expired-tok");
    await waitFor(() => expect(screen.getByText(/Token expired/)).toBeTruthy());
  });
});
