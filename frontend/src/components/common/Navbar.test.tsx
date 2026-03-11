// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { Navbar } from "./Navbar";

const mocks = vi.hoisted(() => ({
  fetchNotifications: vi.fn(() => ({ type: "notifications/fetchAll" })),
  getReminderHealth: vi.fn(),
  logout: vi.fn(),
  selectActiveOrganization: vi.fn(),
}));

const authHookState = vi.hoisted(() => ({
  organizations: [] as Array<{
    id: string;
    code: string;
    name: string;
    organization_type: string;
  }>,
  activeOrganization: null as
    | {
        id: string;
        code: string;
        name: string;
        organization_type: string;
      }
    | null,
  activeOrganizationId: null as string | null,
  canManageActiveOrganizationGovernance: false,
  canSwitchOrganization: false,
  switchingActiveOrganization: false,
  canViewAuditLogs: false,
  canManageRegistry: false,
  canAccessAppointments: false,
  canAccessApplications: false,
  canAccessCampaigns: false,
  canAccessVideoCalls: false,
  canAccessInternalWorkflow: false,
  canManageRubrics: false,
}));

vi.mock("@/store/notificationSlice", () => ({
  default: (state = { notifications: [], unreadCount: 0, loading: false, error: null }) => state,
  fetchNotifications: mocks.fetchNotifications,
}));

vi.mock("@/services/videoCall.service", () => ({
  videoCallService: {
    getReminderHealth: mocks.getReminderHealth,
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    logout: mocks.logout,
    organizations: authHookState.organizations,
    activeOrganization: authHookState.activeOrganization,
    activeOrganizationId: authHookState.activeOrganizationId,
    canManageActiveOrganizationGovernance: authHookState.canManageActiveOrganizationGovernance,
    canSwitchOrganization: authHookState.canSwitchOrganization,
    switchingActiveOrganization: authHookState.switchingActiveOrganization,
    selectActiveOrganization: mocks.selectActiveOrganization,
    canViewAuditLogs: authHookState.canViewAuditLogs,
    canManageRegistry: authHookState.canManageRegistry,
    canAccessAppointments: authHookState.canAccessAppointments,
    canAccessApplications: authHookState.canAccessApplications,
    canAccessCampaigns: authHookState.canAccessCampaigns,
    canAccessVideoCalls: authHookState.canAccessVideoCalls,
    canAccessInternalWorkflow: authHookState.canAccessInternalWorkflow,
    canManageRubrics: authHookState.canManageRubrics,
  }),
}));

const createState = (overrides?: Record<string, any>) => {
  const baseState = {
    auth: {
      user: {
        id: "u-1",
        email: "hr@example.com",
        first_name: "Internal",
        last_name: "Manager",
        full_name: "Operations User",
        phone_number: "",
        profile_picture_url: "",
        avatar_url: "",
        date_of_birth: "",
        user_type: "internal",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      tokens: { access: "token-access", refresh: "token-refresh" },
      isAuthenticated: true,
      userType: "internal",
      roles: [],
      capabilities: [],
      loading: false,
      error: null,
      passwordResetEmailSent: false,
      twoFactorRequired: false,
      twoFactorToken: null,
      twoFactorSetupRequired: false,
      twoFactorProvisioningUri: null,
      twoFactorExpiresInSeconds: null,
      twoFactorMessage: null,
    },
    notifications: {
      unreadCount: 2,
    },
  };

  return {
    ...baseState,
    ...overrides,
    auth: {
      ...baseState.auth,
      ...(overrides?.auth || {}),
      user: {
        ...baseState.auth.user,
        ...((overrides?.auth && overrides.auth.user) || {}),
      },
    },
    notifications: {
      ...baseState.notifications,
      ...(overrides?.notifications || {}),
    },
  } as any;
};

const renderNavbar = (route = "/dashboard", stateOverrides?: Record<string, unknown>) => {
  const preloadedState = createState(stateOverrides);
  const store = configureStore({
    reducer: (state = preloadedState) => state,
    preloadedState,
  });

  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <Navbar />
      </MemoryRouter>
    </Provider>,
  );
};

describe("Navbar runtime + active tab behavior", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authHookState.organizations = [];
    authHookState.activeOrganization = null;
    authHookState.activeOrganizationId = null;
    authHookState.canManageActiveOrganizationGovernance = false;
    authHookState.canSwitchOrganization = false;
    authHookState.switchingActiveOrganization = false;
    authHookState.canViewAuditLogs = false;
    authHookState.canManageRegistry = false;
    authHookState.canAccessAppointments = false;
    authHookState.canAccessApplications = false;
    authHookState.canAccessCampaigns = false;
    authHookState.canAccessVideoCalls = false;
    authHookState.canAccessInternalWorkflow = false;
    authHookState.canManageRubrics = false;
  });

  it("opens runtime popover and shows latest reminder counts", async () => {
    mocks.getReminderHealth.mockResolvedValue({
      generated_at: "2026-03-04T12:00:00Z",
      max_retries: 3,
      soon_retry_pending: 2,
      soon_retry_exhausted: 1,
      start_now_retry_pending: 0,
      start_now_retry_exhausted: 1,
      time_up_retry_pending: 0,
      time_up_retry_exhausted: 0,
    });

    renderNavbar("/video-calls", {
      auth: {
        userType: "admin",
        user: {
          user_type: "admin",
          email: "admin@example.com",
          full_name: "Admin User",
          first_name: "Admin",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /runtime/i }));

    expect(await screen.findByText("Reminder Runtime")).toBeTruthy();
    const soonPendingCard = screen.getByText("Soon Pending").closest("div");
    expect(soonPendingCard).toBeTruthy();
    expect(within(soonPendingCard as HTMLElement).getByText("2")).toBeTruthy();
    expect(screen.getByText("Soon Exhausted")).toBeTruthy();
    expect(screen.getByText("Last checked:", { exact: false })).toBeTruthy();
  });

  it("highlights the active navbar tab based on current route", async () => {
    mocks.getReminderHealth.mockResolvedValue({
      generated_at: "2026-03-04T12:00:00Z",
      max_retries: 3,
      soon_retry_pending: 0,
      soon_retry_exhausted: 0,
      start_now_retry_pending: 0,
      start_now_retry_exhausted: 0,
      time_up_retry_pending: 0,
      time_up_retry_exhausted: 0,
    });

    renderNavbar("/video-calls", {
      auth: {
        userType: "admin",
        user: {
          user_type: "admin",
          email: "admin@example.com",
          full_name: "Admin User",
          first_name: "Admin",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    const videoCallLinks = screen.queryAllByRole("link", { name: /video calls/i });
    if (videoCallLinks.length > 0) {
      const hasActiveDesktopLink = videoCallLinks.some((link) =>
        link.className.includes("bg-indigo-100"),
      );
      expect(hasActiveDesktopLink).toBe(true);
      return;
    }

    const moreButton = screen.getByRole("button", { name: /more/i });
    expect(moreButton.className.includes("bg-indigo-100")).toBe(true);
  });

  it("shows unavailable status in runtime popover when health endpoint fails", async () => {
    mocks.getReminderHealth.mockRejectedValue(new Error("Runtime unavailable"));

    renderNavbar("/dashboard", {
      auth: {
        userType: "admin",
        user: {
          user_type: "admin",
          email: "admin@example.com",
          full_name: "Admin User",
          first_name: "Admin",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.getReminderHealth).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /runtime/i }));

    expect(await screen.findByText("Reminder Runtime")).toBeTruthy();
    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(screen.getByText(/runtime unavailable/i)).toBeTruthy();
  });

  it("does not poll reminder runtime for internal users", async () => {
    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        user: {
          user_type: "internal",
          email: "hr@example.com",
          full_name: "Operations User",
          first_name: "Internal",
          last_name: "Manager",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });
    expect(mocks.getReminderHealth).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /runtime/i })).toBeNull();
  });

  it("hides campaigns and rubrics links for applicants", async () => {
    renderNavbar("/dashboard", {
      auth: {
        userType: "applicant",
        user: {
          user_type: "applicant",
          email: "candidate@example.com",
          full_name: "Candidate User",
          first_name: "Candidate",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByRole("link", { name: /campaigns/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /rubrics/i })).toBeNull();
  });

  it("shows campaigns and rubrics links for internal users", async () => {
    authHookState.canAccessCampaigns = true;
    authHookState.canManageRubrics = true;

    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        user: {
          user_type: "internal",
          email: "hr@example.com",
          full_name: "Operations User",
          first_name: "Internal",
          last_name: "Manager",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    expect(screen.getAllByRole("link", { name: /campaigns/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /rubrics/i }).length).toBeGreaterThan(0);
  });

  it("hides government workflow links when internal lacks workflow capabilities", async () => {
    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: [],
        user: {
          user_type: "internal",
          email: "operator@example.com",
          full_name: "Ops User",
          first_name: "Ops",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByRole("link", { name: /appointments/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /positions/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /personnel/i })).toBeNull();
  });

  it("shows government workflow links when internal has registry capability", async () => {
    authHookState.canAccessAppointments = true;
    authHookState.canManageRegistry = true;
    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: ["gams.registry.manage"],
        user: {
          user_type: "internal",
          email: "registry@example.com",
          full_name: "Registry User",
          first_name: "Registry",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.getAllByRole("link", { name: /appointments/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /positions/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /personnel/i }).length).toBeGreaterThan(0);
  });

  it("shows org-admin workspace links for users with governance access", async () => {
    authHookState.canManageActiveOrganizationGovernance = true;
    authHookState.activeOrganizationId = "org-1";
    authHookState.canAccessAppointments = true;
    authHookState.canManageRegistry = true;
    authHookState.canAccessCampaigns = true;
    authHookState.canAccessApplications = true;
    authHookState.canAccessVideoCalls = true;
    authHookState.canManageRubrics = true;
    authHookState.canAccessInternalWorkflow = true;

    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: ["gams.registry.manage"],
        user: {
          user_type: "internal",
          email: "registry.admin@example.com",
          full_name: "Registry Admin",
          first_name: "Registry",
          last_name: "Admin",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.getAllByRole("link", { name: /org workspace/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /org members/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /committees/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /onboarding/i }).length).toBeGreaterThan(0);
  });

  it("hides org-admin workspace links when governance access is unavailable", async () => {
    authHookState.canManageActiveOrganizationGovernance = false;
    authHookState.activeOrganizationId = "org-1";
    authHookState.canAccessAppointments = true;
    authHookState.canManageRegistry = true;

    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: [],
        user: {
          user_type: "internal",
          email: "ops.user@example.com",
          full_name: "Ops User",
          first_name: "Ops",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.queryByRole("link", { name: /org workspace/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /org members/i })).toBeNull();
  });

  it("shows audit link for internal users with audit capability", async () => {
    authHookState.canViewAuditLogs = true;
    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: ["gams.audit.view"],
        user: {
          user_type: "internal",
          email: "auditor@example.com",
          full_name: "Audit Reader",
          first_name: "Audit",
          last_name: "Reader",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.getAllByRole("link", { name: /audit/i }).length).toBeGreaterThan(0);
  });

  it("hides audit link for internal users without audit capability", async () => {
    authHookState.canAccessAppointments = true;
    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: [],
        user: {
          user_type: "internal",
          email: "operator@example.com",
          full_name: "Ops User",
          first_name: "Ops",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.queryByRole("link", { name: /audit/i })).toBeNull();
  });

  it("shows organization switcher and dispatches active-organization selection", async () => {
    authHookState.organizations = [
      {
        id: "org-1",
        code: "ORG1",
        name: "Registry Commission",
        organization_type: "agency",
      },
      {
        id: "org-2",
        code: "ORG2",
        name: "Appointments Council",
        organization_type: "agency",
      },
    ];
    authHookState.activeOrganization = authHookState.organizations[0];
    authHookState.activeOrganizationId = "org-1";
    authHookState.canSwitchOrganization = true;
    mocks.selectActiveOrganization.mockResolvedValue(undefined);

    renderNavbar("/dashboard", {
      auth: {
        userType: "internal",
        capabilities: ["gams.registry.manage"],
        user: {
          user_type: "internal",
          email: "registry@example.com",
          full_name: "Registry User",
          first_name: "Registry",
          last_name: "User",
        },
      },
    });

    await waitFor(() => {
      expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    const organizationSwitch = screen.getByLabelText(/switch active organization/i);
    fireEvent.change(organizationSwitch, { target: { value: "org-2" } });

    await waitFor(() => {
      expect(mocks.selectActiveOrganization).toHaveBeenCalledWith("org-2");
    });
  });
});

