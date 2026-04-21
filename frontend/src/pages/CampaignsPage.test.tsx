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

import CampaignsPage from "./CampaignsPage";

const mocks = vi.hoisted(() => ({
  campaignService: {
    list: vi.fn(),
    create: vi.fn(),
    updateStatus: vi.fn(),
  },
  billingService: {
    getQuota: vi.fn(),
  },
  useAuth: vi.fn(),
}));

vi.mock("@/services/campaign.service", () => ({
  campaignService: mocks.campaignService,
}));

vi.mock("@/services/billing.service", () => ({
  billingService: mocks.billingService,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

describe("CampaignsPage list filters", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hydrates list filters from URL and clears all active filters", async () => {
    mocks.useAuth.mockReturnValue({
      canManageRegistry: true,
      userType: "internal",
    });
    mocks.billingService.getQuota.mockResolvedValue({
      status: "ok",
      candidate: {
        enforced: true,
        scope: "org",
        reason: null,
        plan_id: "growth",
        plan_name: "Growth",
        limit: 100,
        used: 5,
        remaining: 95,
        period_start: "2026-03-01T00:00:00Z",
        period_end: "2026-03-31T23:59:59Z",
      },
    });
    mocks.campaignService.list.mockResolvedValue([
      {
        id: "campaign-1",
        name: "Graduate Vetting 2026",
        description: "Main graduate intake campaign",
        status: "active",
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: "hr-1",
        initiated_by_email: "hr@example.com",
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-01T10:00:00Z",
      },
      {
        id: "campaign-2",
        name: "Archive Intake",
        description: "Legacy archive process",
        status: "draft",
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: "hr-1",
        initiated_by_email: "hr@example.com",
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-01T10:00:00Z",
      },
      {
        id: "campaign-3",
        name: "Executive Vetting",
        description: "Senior role vetting",
        status: "active",
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: "hr-1",
        initiated_by_email: "hr@example.com",
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-01T10:00:00Z",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/campaigns?q=graduate&status=active"]}>
        <CampaignsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.campaignService.list).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByText(/Graduate Vetting 2026/i)).toBeTruthy();
    expect(screen.queryByText(/Archive Intake/i)).toBeNull();
    expect(screen.queryByText(/Executive Vetting/i)).toBeNull();

    fireEvent.click(
      await screen.findByRole("button", { name: /clear exercise filters/i }),
    );

    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
    expect(await screen.findByText(/Archive Intake/i)).toBeTruthy();
    expect(await screen.findByText(/Executive Vetting/i)).toBeTruthy();
  });
});
const makeQuota = () => ({
  status: "ok",
  candidate: {
    enforced: false,
    scope: "org",
    reason: null,
    plan_id: "growth",
    plan_name: "Growth",
    limit: 100,
    used: 5,
    remaining: 95,
    period_start: "2026-03-01T00:00:00Z",
    period_end: "2026-03-31T23:59:59Z",
  },
});

const makeCampaign = (overrides: Record<string, unknown> = {}) => ({
  id: "campaign-draft",
  name: "Draft Exercise",
  description: "A draft exercise",
  status: "draft",
  starts_at: null,
  ends_at: null,
  settings_json: {},
  initiated_by: "user-1",
  initiated_by_email: "user@example.com",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
  ...overrides,
});

describe("CampaignsPage status transitions", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const setup = (campaign = makeCampaign()) => {
    mocks.useAuth.mockReturnValue({
      canManageRegistry: true,
      userType: "internal",
    });
    mocks.billingService.getQuota.mockResolvedValue(makeQuota());
    mocks.campaignService.list.mockResolvedValue([campaign]);

    render(
      <MemoryRouter>
        <CampaignsPage />
      </MemoryRouter>,
    );
  };

  it("shows allowed transitions for a draft campaign", async () => {
    setup(makeCampaign({ status: "draft" }));

    await screen.findByText("Draft Exercise");

    const select = screen.getByTitle(
      /select the next lifecycle status/i,
    ) as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).toContain("active");
    expect(optionValues).toContain("archived");
    expect(optionValues).not.toContain("closed");
  });

  it("disables the Apply button and select for an archived campaign", async () => {
    setup(makeCampaign({ status: "archived" }));

    await screen.findByText("Draft Exercise");

    const select = screen.getByTitle(
      /select the next lifecycle status/i,
    ) as HTMLSelectElement;
    expect(select.disabled).toBe(true);

    const applyButton = screen.getByRole("button", {
      name: /apply/i,
    }) as HTMLButtonElement;
    expect(applyButton.disabled).toBe(true);
  });

  it("calls updateStatus with correct args and reflects new status on success", async () => {
    const campaign = makeCampaign({ status: "draft" });
    mocks.campaignService.updateStatus.mockResolvedValue({
      ...campaign,
      status: "active",
    });
    setup(campaign);

    await screen.findByText("Draft Exercise");

    // Simulate user selecting 'active' in the dropdown first
    const select = screen.getByTitle(/select the next lifecycle status/i);
    fireEvent.change(select, { target: { value: "active" } });

    const applyButton = screen.getByRole("button", { name: /apply/i });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(mocks.campaignService.updateStatus).toHaveBeenCalledWith(
        "campaign-draft",
        "active",
      );
    });

    // After update the badge should show 'active'
    await waitFor(() => {
      expect(screen.getByText("active")).toBeTruthy();
    });
  });

  it("shows error when updateStatus rejects", async () => {
    const campaign = makeCampaign({ status: "draft" });
    mocks.campaignService.updateStatus.mockRejectedValue(
      new Error("Server error"),
    );
    setup(campaign);

    await screen.findByText("Draft Exercise");

    // Must select a new status first so the guard doesn't early-return
    const select = screen.getByTitle(/select the next lifecycle status/i);
    fireEvent.change(select, { target: { value: "active" } });

    const applyButton = screen.getByRole("button", { name: /apply/i });
    fireEvent.click(applyButton);

    // Button should return to normal (not stuck in "Updating…")
    await waitFor(() => {
      expect(screen.queryByText(/updating\.\.\./i)).toBeNull();
    });
    // updateStatus was called
    expect(mocks.campaignService.updateStatus).toHaveBeenCalledTimes(1);
  });
});
