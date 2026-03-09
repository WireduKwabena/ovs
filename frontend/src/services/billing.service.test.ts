import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("./api", () => ({
  default: {
    get: mocks.get,
    post: mocks.post,
  },
}));

describe("billingService onboarding-token endpoints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads onboarding token state", async () => {
    mocks.get.mockResolvedValueOnce({
      data: {
        status: "ok",
        organization_id: "org-1",
        organization_name: "Org One",
        subscription_id: "sub-1",
        subscription_active: true,
        has_active_token: true,
        token: {
          id: "tok-1",
          subscription_id: "sub-1",
          token_preview: "h_123",
          is_active: true,
          expires_at: null,
          max_uses: 5,
          uses: 1,
          remaining_uses: 4,
          allowed_email_domain: "",
          last_used_at: null,
          revoked_at: null,
          revoked_reason: "",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      },
    });

    const { billingService } = await import("./billing.service");
    const payload = await billingService.getOnboardingTokenState();

    expect(mocks.get).toHaveBeenCalledWith("/billing/onboarding-token/");
    expect(payload.organization_name).toBe("Org One");
  });

  it("posts onboarding token generation payload", async () => {
    mocks.post.mockResolvedValueOnce({
      data: {
        status: "ok",
        organization_id: "org-1",
        organization_name: "Org One",
        token: "org_onb_test",
        onboarding_link: "https://example.com/register?onboarding_token=org_onb_test",
        token_state: {
          id: "tok-1",
          subscription_id: "sub-1",
          token_preview: "h_123",
          is_active: true,
          expires_at: null,
          max_uses: 5,
          uses: 0,
          remaining_uses: 5,
          allowed_email_domain: "",
          last_used_at: null,
          revoked_at: null,
          revoked_reason: "",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      },
    });

    const { billingService } = await import("./billing.service");
    await billingService.generateOnboardingToken({
      rotate: true,
      max_uses: 5,
      expires_in_hours: 72,
      allowed_email_domain: "agency.gov",
    });

    expect(mocks.post).toHaveBeenCalledWith("/billing/onboarding-token/generate/", {
      rotate: true,
      max_uses: 5,
      expires_in_hours: 72,
      allowed_email_domain: "agency.gov",
    });
  });

  it("posts onboarding token revocation payload", async () => {
    mocks.post.mockResolvedValueOnce({
      data: {
        status: "ok",
        organization_id: "org-1",
        organization_name: "Org One",
        subscription_id: "sub-1",
        subscription_active: true,
        has_active_token: false,
        token: null,
      },
    });

    const { billingService } = await import("./billing.service");
    await billingService.revokeOnboardingToken({ reason: "manual_revocation" });

    expect(mocks.post).toHaveBeenCalledWith("/billing/onboarding-token/revoke/", {
      reason: "manual_revocation",
    });
  });
});

