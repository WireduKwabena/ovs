// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  navigate: vi.fn(),
  twoFactorRequired: true as boolean,
  twoFactorToken: "tok-abc" as string | null,
}));

// Mock redux
vi.mock("react-redux", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useDispatch: () => mocks.dispatch,
    useSelector: (sel: (s: unknown) => unknown) =>
      sel({
        auth: {
          twoFactorRequired: mocks.twoFactorRequired,
          twoFactorToken: mocks.twoFactorToken,
          twoFactorSetupRequired: false,
          twoFactorProvisioningUri: null,
          twoFactorExpiresInSeconds: null,
          twoFactorMessage: null,
          resolvedLoginType: "totp",
          loading: false,
          error: null,
        },
      }),
  };
});

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useLocation: () => ({ state: null, pathname: "/two-factor" }),
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

vi.mock("react-toastify", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// Mock heavy security sub-components
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
  VerificationFactorField: ({ labelOtp }: { labelOtp: string }) => (
    <input aria-label={labelOtp} />
  ),
}));
vi.mock("@/hooks/useBackupCodesProtection", () => ({
  useBackupCodesProtection: () => ({
    issuedBackupCodes: null,
    backupCodesAcknowledged: false,
    backupCodesAttentionState: "none",
    revealBackupCodes: vi.fn(),
    setBackupCodesAcknowledged: vi.fn(),
    confirmLeaveIfNeeded: vi.fn(),
  }),
}));
vi.mock("@/hooks/useVerificationFactorInput", () => ({
  useVerificationFactorInput: () => ({
    mode: "otp",
    displayValue: "",
    setFromInput: vi.fn(),
    toggleModeReset: vi.fn(),
    getValidationError: vi.fn(() => null),
    getPayload: vi.fn(() => ({ otp_code: "123456" })),
    clear: vi.fn(),
  }),
}));

const { TwoFactorPage } = await import("./TwoFactorPage");

describe("TwoFactorPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("redirects to /login when twoFactorRequired is false", () => {
    mocks.twoFactorRequired = false;
    mocks.twoFactorToken = null;

    render(
      <MemoryRouter>
        <TwoFactorPage />
      </MemoryRouter>,
    );

    expect(mocks.navigate).toHaveBeenCalledWith("/login", { replace: true });
    // Reset for subsequent tests
    mocks.twoFactorRequired = true;
    mocks.twoFactorToken = "tok-abc";
  });

  it("renders the verification heading when challenge is active", () => {
    render(
      <MemoryRouter>
        <TwoFactorPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/verify your login/i)).toBeTruthy();
    expect(screen.getByLabelText(/one-time password/i)).toBeTruthy();
  });
});
