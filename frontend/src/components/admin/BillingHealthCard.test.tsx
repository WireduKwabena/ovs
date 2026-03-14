// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import BillingHealthCard from "./BillingHealthCard";

const mocks = vi.hoisted(() => ({
  getHealth: vi.fn(),
}));

vi.mock("@/services/billing.service", () => ({
  billingService: {
    getHealth: mocks.getHealth,
  },
}));

describe("BillingHealthCard", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders billing runtime and payment-failure trace links alongside health data", async () => {
    mocks.getHealth.mockResolvedValue({
      status: "ok",
      access: {
        staff_required: false,
        requester_is_staff: true,
      },
      stripe: {
        sdk_installed: true,
        secret_key_configured: true,
        webhook_secret_configured: true,
      },
      paystack: {
        secret_key_configured: true,
        base_url: "https://api.paystack.co",
        currency: "GHS",
      },
      exchange_rate: {
        api_url_configured: true,
        fallback_rate: 15.5,
        timeout_seconds: 5,
        cache_ttl_seconds: 1200,
      },
      subscription_verify_rate_limit: {
        enabled: true,
        per_minute: 30,
      },
    });

    render(
      <MemoryRouter>
        <BillingHealthCard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.getHealth).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText("Billing Runtime")).toBeTruthy();
    const runtimeTraceLink = screen.getByRole("link", { name: /open runtime errors/i });
    expect(runtimeTraceLink.getAttribute("href")).toBe(
      "/notifications?channel=all&event_type=processing_error&subsystem=billing",
    );
    const paymentTraceLink = screen.getByRole("link", { name: /open payment failures/i });
    expect(paymentTraceLink.getAttribute("href")).toBe(
      "/notifications?channel=all&event_type=billing_payment_failed&subsystem=billing",
    );
  });
});
