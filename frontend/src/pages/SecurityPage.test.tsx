// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getTwoFactorStatus: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/auth.service", () => ({
  authService: { getTwoFactorStatus: mocks.getTwoFactorStatus },
}));
vi.mock("react-toastify", () => ({
  toast: { error: mocks.toastError, success: vi.fn() },
}));
vi.mock("@/components/security/ProvisioningQrCard", () => ({
  ProvisioningQrCard: () => <div data-testid="qr-card" />,
}));
vi.mock("@/components/security/EmergencyBackupCodesCard", () => ({
  EmergencyBackupCodesCard: () => <div data-testid="backup-codes-card" />,
}));
vi.mock("@/components/security/BackupCodesAttentionBadge", () => ({
  BackupCodesAttentionBadge: () => null,
}));
vi.mock("@/components/security/VerificationFactorField", () => ({
  VerificationFactorField: () => <input aria-label="otp" />,
}));
vi.mock("@/hooks/useBackupCodesProtection", () => ({
  useBackupCodesProtection: () => ({
    issuedBackupCodes: null,
    backupCodesAcknowledged: false,
    backupCodesAttentionState: "none",
    revealBackupCodes: vi.fn(),
    clearBackupCodes: vi.fn(),
    setBackupCodesAcknowledged: vi.fn(),
  }),
}));
vi.mock("@/hooks/useVerificationFactorInput", () => ({
  useVerificationFactorInput: () => ({
    value: "",
    onChange: vi.fn(),
    onClear: vi.fn(),
    inputType: "text",
  }),
}));

const { default: SecurityPage } = await import("./SecurityPage");

const buildTwoFactorStatus = (overrides: Record<string, unknown> = {}) => ({
  two_factor_required: false,
  is_two_factor_enabled: false,
  backup_codes_remaining: 0,
  applicant_exempt: false,
  ...overrides,
});

describe("SecurityPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls getTwoFactorStatus on mount", async () => {
    mocks.getTwoFactorStatus.mockResolvedValue(buildTwoFactorStatus());
    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(mocks.getTwoFactorStatus).toHaveBeenCalledOnce(),
    );
  });

  it("shows error state when status fetch fails", async () => {
    mocks.getTwoFactorStatus.mockRejectedValue(new Error("Network error"));
    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/network error/i)).toBeTruthy(),
    );
  });

  it("shows 2FA disabled state when 2FA is not enabled", async () => {
    mocks.getTwoFactorStatus.mockResolvedValue(buildTwoFactorStatus());
    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/not enabled/i)).toBeTruthy());
  });
});
