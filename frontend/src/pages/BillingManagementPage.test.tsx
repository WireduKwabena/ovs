// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getHealth: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/billing.service", () => ({
  billingService: { getHealth: mocks.getHealth },
}));
vi.mock("react-toastify", () => ({ toast: { error: mocks.toastError } }));

const { BillingManagementPage } =
  await import("./platform-admin/BillingManagementPage");

const buildHealth = () => ({
  stripe: {
    sdk_installed: true,
    secret_key_configured: true,
    webhook_secret_configured: true,
  },
  exchange_rate: {
    fallback_rate: 1,
    cache_ttl_seconds: 300,
  },
  paystack: {
    secret_key_configured: true,
  },
});

describe("BillingManagementPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls billingService.getHealth on mount", async () => {
    mocks.getHealth.mockResolvedValue(buildHealth());
    render(
      <MemoryRouter>
        <BillingManagementPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.getHealth).toHaveBeenCalled());
  });

  it("renders Billing & Plans heading", async () => {
    mocks.getHealth.mockResolvedValue(buildHealth());
    render(
      <MemoryRouter>
        <BillingManagementPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/billing & plans/i)).toBeTruthy(),
    );
  });

  it("renders the static plan names", async () => {
    mocks.getHealth.mockResolvedValue(buildHealth());
    render(
      <MemoryRouter>
        <BillingManagementPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Starter")).toBeTruthy();
      expect(screen.getByText("Growth")).toBeTruthy();
      expect(screen.getByText("Enterprise")).toBeTruthy();
    });
  });
});
