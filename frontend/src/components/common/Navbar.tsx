// src/components/common/Navbar.tsx
import React, { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  Briefcase,
  Building2,
  ClipboardCheck,
  Cpu,
  CreditCard,
  FileSearch,
  FileText,
  FolderOpen,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  Scale,
  Search,
  Settings2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserRound,
  Users,
  Video,
  X,
} from "lucide-react";
import { createSelector } from "@reduxjs/toolkit";
import { useDispatch, useSelector } from "react-redux";
import { toast } from "react-toastify";

import type { AppDispatch, RootState } from "@/app/store";
import { useAuth } from "@/hooks/useAuth";
import { videoCallService } from "@/services/videoCall.service";
import { fetchNotifications } from "@/store/notificationSlice";
import type { User, VideoMeetingReminderHealth } from "@/types";
import {
  getCandidatePath,
  getOrgAdminPath,
  getOrganizationSetupPath,
  getPlatformAdminPath,
  getWorkspacePath,
} from "@/utils/appPaths";
import { buildReminderNotificationTraceHref } from "@/utils/notificationTrace";
import { getUserDisplayName, getUserInitial } from "@/utils/userDisplay";

import { Button } from "../ui/button";
import { ThemeToggle } from "./ThemeToggle";

const selectAuthState = (state: RootState) => state.auth;
const selectNotificationsState = (state: RootState) => state.notifications;

const selectUserData = createSelector([selectAuthState], (auth) => ({
  user: auth.user,
  isAuthenticated: auth.isAuthenticated,
  accessToken: auth.tokens?.access ?? null,
  userType: auth.userType,
  roles: auth.roles ?? [],
  capabilities: auth.capabilities ?? [],
}));

const selectUnreadCount = createSelector(
  [selectNotificationsState],
  (notifications) => notifications.unreadCount || 0,
);

type ReminderRuntimeStatus =
  | "unknown"
  | "healthy"
  | "attention"
  | "unavailable";
type NavItem = { to: string; label: string };
type NavIcon = React.ComponentType<{ className?: string }>;

const navIconMap: Record<string, NavIcon> = {
  [getWorkspacePath("home")]: LayoutDashboard,
  [getPlatformAdminPath("dashboard")]: LayoutDashboard,
  [getCandidatePath("home")]: LayoutDashboard,
  [getWorkspacePath("applications")]: FolderOpen,
  [getWorkspacePath("campaigns")]: Briefcase,
  [getWorkspacePath("rubrics")]: ClipboardCheck,
  [getWorkspacePath("video-calls")]: Video,
  [getWorkspacePath("government/appointments")]: Scale,
  [getWorkspacePath("government/positions")]: Building2,
  [getWorkspacePath("government/personnel")]: UserRound,
  "/settings": CreditCard,
  [getWorkspacePath("fraud-insights")]: ShieldAlert,
  [getWorkspacePath("background-checks")]: Search,
  [getWorkspacePath("audit-logs")]: FileSearch,
};

export const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    logout,
    organizations,
    activeOrganization,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
    canSwitchOrganization,
    switchingActiveOrganization,
    selectActiveOrganization,
    canViewAuditLogs,
    canManageRegistry,
    canAccessAppointments: canAccessAppointmentsFromHook,
    canAccessApplications,
    canAccessCampaigns,
    canAccessVideoCalls,
    canAccessInternalWorkflow,
    canManageRubrics,
  } = useAuth();
  const dispatch = useDispatch<AppDispatch>();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileMenuMounted, setMobileMenuMounted] = useState(false);
  const [runtimePopoverOpen, setRuntimePopoverOpen] = useState(false);
  const [moreExpanded, setMoreExpanded] = useState(false);
  const [reminderRuntimeStatus, setReminderRuntimeStatus] =
    useState<ReminderRuntimeStatus>("unknown");
  const [reminderRuntimeSnapshot, setReminderRuntimeSnapshot] =
    useState<VideoMeetingReminderHealth | null>(null);
  const [reminderRuntimeCheckedAt, setReminderRuntimeCheckedAt] = useState<
    string | null
  >(null);
  const [reminderRuntimeError, setReminderRuntimeError] = useState<
    string | null
  >(null);
  const [reminderRuntimeRefreshing, setReminderRuntimeRefreshing] =
    useState(false);

  const runtimePopoverRef = useRef<HTMLDivElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);

  const { user, isAuthenticated, accessToken, userType, roles, capabilities } =
    useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);

  const resolvedRoles = Array.isArray(roles) ? roles : [];
  const resolvedCapabilities = Array.isArray(capabilities) ? capabilities : [];
  const resolvedOrganizations = Array.isArray(organizations)
    ? organizations
    : [];

  const hasRole = (role: string): boolean => resolvedRoles.includes(role);
  const hasCapability = (capability: string): boolean =>
    resolvedCapabilities.includes(capability);

  const hasAdminAccess =
    userType === "platform_admin" ||
    userType === "admin" ||
    hasRole("admin") ||
    Boolean((user as User | null)?.is_superuser);
  const canAccessAudit =
    hasAdminAccess || canViewAuditLogs || hasCapability("gams.audit.view");
  const canAccessRegistry = canManageRegistry;
  const canAccessAppointments = canAccessAppointmentsFromHook;
  const canAccessRubrics = canManageRubrics;
  const canAccessInternalRoutes = canAccessInternalWorkflow;
  const isApplicantUser = userType === "applicant";
  const canAccessNotifications = !isApplicantUser;
  const canShowOrganizationContext =
    !hasAdminAccess && !isApplicantUser && resolvedOrganizations.length > 0;
  const activeOrganizationLabel =
    activeOrganization?.name ||
    resolvedOrganizations[0]?.name ||
    "Default scope";
  const canManageOrganizationBilling = canManageActiveOrganizationGovernance;
  const handleOrganizationSelection = async (rawValue: string) => {
    const nextValue = rawValue === "__default__" ? null : rawValue;
    try {
      await selectActiveOrganization(nextValue);
      toast.success(
        nextValue
          ? "Active organization updated."
          : "Organization context reset to default.",
      );
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to switch active organization.",
      );
    }
  };

  useEffect(() => {
    if (isAuthenticated && accessToken && canAccessNotifications) {
      dispatch(fetchNotifications());
    }
  }, [accessToken, canAccessNotifications, dispatch, isAuthenticated]);

  const applyReminderHealthPayload = (payload: VideoMeetingReminderHealth) => {
    const hasRetryIssues =
      payload.soon_retry_pending > 0 ||
      payload.soon_retry_exhausted > 0 ||
      payload.start_now_retry_pending > 0 ||
      payload.start_now_retry_exhausted > 0 ||
      payload.time_up_retry_pending > 0 ||
      payload.time_up_retry_exhausted > 0;

    setReminderRuntimeStatus(hasRetryIssues ? "attention" : "healthy");
    setReminderRuntimeSnapshot(payload);
    setReminderRuntimeCheckedAt(new Date().toISOString());
    setReminderRuntimeError(null);
  };

  const refreshReminderRuntime = async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setReminderRuntimeRefreshing(true);
    }

    try {
      const payload = await videoCallService.getReminderHealth();
      applyReminderHealthPayload(payload);
    } catch (error) {
      setReminderRuntimeStatus("unavailable");
      setReminderRuntimeError(
        error instanceof Error ? error.message : "Runtime unavailable.",
      );
    } finally {
      if (!options?.silent) {
        setReminderRuntimeRefreshing(false);
      }
    }
  };

  useEffect(() => {
    // reminder-health is an admin-only endpoint — only poll for platform/system admins.
    // canAccessVideoCalls is true for all internal workflow roles (vetting, registry, etc.)
    // and would cause 403s for non-admin users.
    if (!isAuthenticated || !hasAdminAccess) {
      return;
    }

    let mounted = true;

    const pollReminderHealth = async () => {
      try {
        const payload = await videoCallService.getReminderHealth();
        if (!mounted) {
          return;
        }
        applyReminderHealthPayload(payload);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setReminderRuntimeStatus("unavailable");
        setReminderRuntimeError(
          error instanceof Error ? error.message : "Runtime unavailable.",
        );
      }
    };

    void pollReminderHealth();
    const interval = window.setInterval(() => {
      void pollReminderHealth();
    }, 60_000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, [isAuthenticated, hasAdminAccess]);
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        runtimePopoverRef.current &&
        !runtimePopoverRef.current.contains(event.target as Node)
      ) {
        setRuntimePopoverOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!mobileMenuOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const getFocusableInDrawer = (): HTMLElement[] => {
      const drawer = mobileDrawerRef.current;
      if (!drawer) {
        return [];
      }

      const nodes = drawer.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      return Array.from(nodes).filter(
        (node) => node.getAttribute("aria-hidden") !== "true",
      );
    };

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobileMenuOpen(false);
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const drawer = mobileDrawerRef.current;
      if (!drawer) {
        return;
      }

      const focusableNodes = getFocusableInDrawer();
      if (focusableNodes.length === 0) {
        event.preventDefault();
        drawer.focus();
        return;
      }

      const first = focusableNodes[0];
      const last = focusableNodes[focusableNodes.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (event.shiftKey) {
        if (!active || active === first || !drawer.contains(active)) {
          event.preventDefault();
          last.focus();
        }
        return;
      }

      if (active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.body.style.overflow = "hidden";
    window.setTimeout(() => {
      const focusableNodes = getFocusableInDrawer();
      if (focusableNodes.length > 0) {
        focusableNodes[0].focus();
      } else {
        mobileDrawerRef.current?.focus();
      }
    }, 0);
    document.addEventListener("keydown", handleKeydown);

    const menuButton = mobileMenuButtonRef.current;
    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", handleKeydown);
      if (menuButton && document.contains(menuButton)) {
        menuButton.focus();
      } else if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  }, [mobileMenuOpen]);

  useEffect(() => {
    if (mobileMenuOpen || !mobileMenuMounted) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setMobileMenuMounted(false);
    }, 240);

    return () => window.clearTimeout(timeout);
  }, [mobileMenuMounted, mobileMenuOpen]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!isAuthenticated) {
    return null;
  }

  const displayName = getUserDisplayName(user, "User");
  const initial = getUserInitial(user, displayName);
  const profilePictureUrl =
    (user as User | null)?.profile_picture_url ||
    (user as User | null)?.avatar_url ||
    "";
  const canManageTwoFactor = !isApplicantUser;

  const reminderStatusMeta: Record<
    ReminderRuntimeStatus,
    { dotClass: string; label: string }
  > = {
    unknown: { dotClass: "bg-slate-500", label: "Unknown" },
    healthy: { dotClass: "bg-emerald-500", label: "Healthy" },
    attention: { dotClass: "bg-amber-500", label: "Attention needed" },
    unavailable: { dotClass: "bg-rose-500", label: "Unavailable" },
  };

  const runtimeMeta = reminderStatusMeta[reminderRuntimeStatus];
  const runtimeLastChecked = reminderRuntimeCheckedAt
    ? new Date(reminderRuntimeCheckedAt).toLocaleTimeString()
    : "Not checked yet";
  const workspaceHomePath = getWorkspacePath("home");
  const candidateHomePath = getCandidatePath("home");
  const platformDashboardPath = getPlatformAdminPath("dashboard");
  const workspaceApplicationsPath = getWorkspacePath("applications");
  const workspaceNotificationsPath = getWorkspacePath("notifications");
  const workspaceCampaignsPath = getWorkspacePath("campaigns");
  const workspaceRubricsPath = getWorkspacePath("rubrics");
  const workspaceVideoCallsPath = getWorkspacePath("video-calls");
  const workspaceAppointmentsPath = getWorkspacePath("government/appointments");
  const workspacePositionsPath = getWorkspacePath("government/positions");
  const workspacePersonnelPath = getWorkspacePath("government/personnel");
  const workspaceFraudInsightsPath = getWorkspacePath("fraud-insights");
  const workspaceBackgroundChecksPath = getWorkspacePath("background-checks");
  const workspaceAuditLogsPath = getWorkspacePath("audit-logs");
  const organizationDashboardPath =
    canManageActiveOrganizationGovernance && activeOrganizationId
      ? getOrgAdminPath(activeOrganizationId, "dashboard")
      : getOrganizationSetupPath("/dashboard");
  const organizationMembersPath = activeOrganizationId
    ? getOrgAdminPath(activeOrganizationId, "members")
    : getOrganizationSetupPath("/dashboard");
  const organizationCommitteesPath = activeOrganizationId
    ? getOrgAdminPath(activeOrganizationId, "committees")
    : getOrganizationSetupPath("/dashboard");
  const organizationOnboardingPath = activeOrganizationId
    ? getOrgAdminPath(activeOrganizationId, "onboarding")
    : getOrganizationSetupPath("/dashboard");
  const organizationCasesPath = activeOrganizationId
    ? getOrgAdminPath(activeOrganizationId, "cases")
    : getOrganizationSetupPath("/dashboard");
  const routeAliasesByTarget: Record<string, string[]> = {
    [workspaceHomePath]: ["/workspace"],
    [candidateHomePath]: ["/candidate/access"],
    [platformDashboardPath]: [
      "/admin/dashboard",
      "/admin/analytics",
      "/admin/control-center",
      "/admin/platform/analytics",
      "/admin/platform/control-center",
      "/admin/platform/ai-monitor",
      "/admin/platform/ml-monitoring",
      "/admin/platform/register",
      "/ai-monitor",
      "/ml-monitoring",
    ],
    [workspaceApplicationsPath]: ["/applications"],
    [workspaceNotificationsPath]: ["/notifications"],
    [workspaceCampaignsPath]: ["/campaigns"],
    [workspaceRubricsPath]: ["/rubrics"],
    [workspaceVideoCallsPath]: ["/video-calls"],
    [workspaceAppointmentsPath]: ["/government/appointments"],
    [workspacePositionsPath]: ["/government/positions"],
    [workspacePersonnelPath]: ["/government/personnel"],
    [workspaceFraudInsightsPath]: ["/fraud-insights"],
    [workspaceBackgroundChecksPath]: ["/background-checks"],
    [workspaceAuditLogsPath]: ["/audit-logs"],
    [organizationDashboardPath]: ["/organization/dashboard"],
    [organizationCasesPath]: [
      "/admin/cases",
      "/admin/applications",
      "/organization/cases",
    ],
    [organizationMembersPath]: ["/organization/members"],
    [organizationCommitteesPath]: ["/organization/committees"],
    [organizationOnboardingPath]: ["/organization/onboarding"],
  };
  const getNavIcon = (navItem: NavItem): NavIcon => {
    if (navIconMap[navItem.to]) {
      return navIconMap[navItem.to];
    }
    if (navItem.to.includes("/admin/org/")) {
      if (navItem.to.includes("/dashboard")) return LayoutDashboard;
      if (navItem.to.includes("/cases")) return FolderOpen;
      if (navItem.to.includes("/users") || navItem.to.includes("/members"))
        return Users;
      if (navItem.to.includes("/committees")) return Users;
      if (navItem.to.includes("/onboarding")) return ClipboardCheck;
    }
    return FileText;
  };

  const isRouteActive = (to: string): boolean => {
    const targets = [to, ...(routeAliasesByTarget[to] ?? [])];
    return targets.some(
      (targetPath) =>
        location.pathname === targetPath ||
        location.pathname.startsWith(`${targetPath}/`),
    );
  };

  const sidebarSurfaceClass =
    "rounded-[1.75rem] border border-border/70 bg-card/70 p-4 shadow-sm backdrop-blur-xl";
  const sidebarSectionClass = "mt-6 border-t border-border/70 pt-5";
  const sidebarSectionLabelClass =
    "text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground";
  const sidebarLinkBaseClass =
    "group flex w-full items-center justify-between rounded-[1rem] px-3 py-2.5 text-sm font-medium transition-all duration-200";
  const sidebarIconClass = (active: boolean): string =>
    [
      "inline-flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200",
      active
        ? "bg-primary/12 text-primary shadow-sm"
        : "bg-muted/70 text-muted-foreground group-hover:bg-background group-hover:text-foreground",
    ].join(" ");
  const renderSectionHeader = (label: string) => (
    <div className="mb-2 flex items-center gap-3 px-2">
      <p className={sidebarSectionLabelClass}>{label}</p>
      <span className="h-px flex-1 bg-border/70" />
    </div>
  );

  const desktopNavClass = (to: string): string =>
    [
      sidebarLinkBaseClass,
      isRouteActive(to)
        ? "bg-primary/10 text-primary ring-1 ring-primary/15 shadow-sm"
        : "text-foreground hover:bg-accent/80 hover:text-accent-foreground",
    ].join(" ");

  const mobileNavClass = (to: string): string =>
    [
      "flex items-center rounded-[1rem] px-3 py-2.5 text-sm font-medium transition-all duration-200",
      isRouteActive(to)
        ? "bg-primary/10 text-primary ring-1 ring-primary/15"
        : "text-foreground hover:bg-accent/80 hover:text-accent-foreground",
    ].join(" ");

  const desktopUtilityLinkClass = (to: string): string =>
    [
      sidebarLinkBaseClass,
      isRouteActive(to)
        ? "bg-primary/10 text-primary ring-1 ring-primary/15 shadow-sm"
        : "text-foreground hover:bg-accent/80 hover:text-accent-foreground",
    ].join(" ");

  const homeItem: NavItem = isApplicantUser
    ? { to: candidateHomePath, label: "Candidate Access" }
    : hasAdminAccess
      ? { to: platformDashboardPath, label: "Platform Dashboard" }
      : canManageActiveOrganizationGovernance
        ? { to: organizationDashboardPath, label: "Organization Dashboard" }
        : { to: workspaceHomePath, label: "Workspace" };

  const desktopPrimaryLinks: NavItem[] = [homeItem];

  const pushUnique = (target: NavItem[], item: NavItem) => {
    if (!target.some((entry) => entry.to === item.to)) {
      target.push(item);
    }
  };

  if (!hasAdminAccess && !isApplicantUser && canAccessApplications) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceApplicationsPath,
      label: "Applications",
    });
  }

  if (!hasAdminAccess && !isApplicantUser && canAccessCampaigns) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceCampaignsPath,
      label: "Appointment Exercises",
    });
  }

  if (!hasAdminAccess && !isApplicantUser && canAccessRubrics) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceRubricsPath,
      label: "Rubrics",
    });
  }

  if (!hasAdminAccess && !isApplicantUser && canAccessVideoCalls) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceVideoCallsPath,
      label: "Video Calls",
    });
  }

  const desktopSecondaryLinks: NavItem[] = [];

  if (!hasAdminAccess && !isApplicantUser && canAccessAppointments) {
    pushUnique(desktopSecondaryLinks, {
      to: workspaceAppointmentsPath,
      label: "Appointment Workflow",
    });
  }

  if (!hasAdminAccess && !isApplicantUser && canAccessRegistry) {
    pushUnique(desktopSecondaryLinks, {
      to: workspacePositionsPath,
      label: "Offices",
    });
    pushUnique(desktopSecondaryLinks, {
      to: workspacePersonnelPath,
      label: "Nominees",
    });
  }

  if (
    !hasAdminAccess &&
    !isApplicantUser &&
    canManageActiveOrganizationGovernance &&
    activeOrganizationId
  ) {
    pushUnique(desktopPrimaryLinks, {
      to: organizationCasesPath,
      label: "Cases",
    });
    pushUnique(desktopSecondaryLinks, {
      to: organizationMembersPath,
      label: "Members",
    });
    pushUnique(desktopSecondaryLinks, {
      to: organizationCommitteesPath,
      label: "Committees",
    });
    pushUnique(desktopSecondaryLinks, {
      to: organizationOnboardingPath,
      label: "Onboarding",
    });
    if (canManageOrganizationBilling) {
      pushUnique(desktopSecondaryLinks, {
        to: "/settings",
        label: "Subscription",
      });
    }
  }

  if (!isApplicantUser && canAccessInternalRoutes && !hasAdminAccess) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceFraudInsightsPath,
      label: "Fraud Insights",
    });
    pushUnique(desktopPrimaryLinks, {
      to: workspaceBackgroundChecksPath,
      label: "Background Checks",
    });
  }

  if (!isApplicantUser && canAccessAudit) {
    pushUnique(desktopPrimaryLinks, {
      to: workspaceAuditLogsPath,
      label: "Audit",
    });
  }

  const navLinks: NavItem[] = desktopPrimaryLinks;

  const renderRuntimePanel = (onNavigate?: () => void) => (
    <div className="rounded-3xl border border-border/70 bg-card/92 p-4 text-sm text-card-foreground shadow-[0_24px_60px_rgba(15,23,42,0.18)] backdrop-blur-xl">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Cpu className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-card-foreground">
              Reminder Runtime
            </h3>
            <p className="text-xs text-muted-foreground">
              Status: {runtimeMeta.label}
            </p>
          </div>
        </div>
        <span className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-border/70 bg-muted/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Soon Pending
          </p>
          <p className="mt-2 text-2xl font-bold text-card-foreground">
            {reminderRuntimeSnapshot?.soon_retry_pending ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-border/70 bg-muted/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Soon Exhausted
          </p>
          <p className="mt-2 text-2xl font-bold text-card-foreground">
            {reminderRuntimeSnapshot?.soon_retry_exhausted ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-border/70 bg-muted/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Start Pending
          </p>
          <p className="mt-2 text-2xl font-bold text-card-foreground">
            {reminderRuntimeSnapshot?.start_now_retry_pending ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-border/70 bg-muted/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Time Up Exhausted
          </p>
          <p className="mt-2 text-2xl font-bold text-card-foreground">
            {reminderRuntimeSnapshot?.time_up_retry_exhausted ?? 0}
          </p>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Last checked: {runtimeLastChecked}
      </p>
      {reminderRuntimeError ? (
        <p className="mt-2 text-xs text-destructive">{reminderRuntimeError}</p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void refreshReminderRuntime()}
          disabled={reminderRuntimeRefreshing}
          className="inline-flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${reminderRuntimeRefreshing ? "animate-spin" : ""}`}
          />
          {reminderRuntimeRefreshing ? "Refreshing..." : "Refresh"}
        </button>
        <Link
          to={buildReminderNotificationTraceHref()}
          onClick={() => {
            setRuntimePopoverOpen(false);
            onNavigate?.();
          }}
          className="inline-flex items-center justify-center rounded-md border border-primary/25 bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary hover:bg-primary/15"
        >
          Open reminder traces
        </Link>
      </div>
    </div>
  );

  const renderRuntimePopover = () => {
    return null;
    // Reminder runtime feature is disabled — remove this guard when re-enabling.

    return (
      <div className="relative" ref={runtimePopoverRef}>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setRuntimePopoverOpen((previous) => !previous)}
          className={[
            sidebarLinkBaseClass,
            "h-auto border-0 bg-transparent px-3 py-2.5 text-left shadow-none",
            runtimePopoverOpen
              ? "bg-primary/10 text-primary ring-1 ring-primary/15"
              : "text-foreground hover:bg-accent/80 hover:text-accent-foreground",
          ].join(" ")}
        >
          <span className="inline-flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`}
            />
            Reminder Runtime
          </span>
          <span className="text-xs text-muted-foreground">
            {runtimeMeta.label}
          </span>
        </Button>
        {runtimePopoverOpen ? (
          <div className="absolute left-0 top-[calc(100%+0.5rem)] z-50 w-88 max-w-[calc(100vw-2rem)]">
            {renderRuntimePanel()}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <>
      <aside
        data-testid="desktop-sidebar"
        className="app-sidebar-scroll fixed inset-y-0 left-0 z-40 hidden w-64 overflow-y-auto overscroll-y-contain border-r border-border/70 bg-background/95 shadow-[18px_0_48px_rgba(15,23,42,0.08)] backdrop-blur-xl [scrollbar-gutter:stable] lg:flex xl:w-72"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-linear-to-b from-primary/12 via-primary/6 to-transparent"
        />
        <div className="relative flex min-h-full w-full flex-col px-3 py-4 lg:px-3.5 xl:px-4">
          <div className="px-2 pb-5">
            <Link to={homeItem.to} className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-500 via-blue-500 to-indigo-500 text-white shadow-[0_14px_32px_rgba(59,130,246,0.25)]">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                  Workspace
                </p>
                <p className="text-xl font-bold tracking-tight text-foreground">
                  CAVP
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Government appointments and vetting
                </p>
              </div>
            </Link>
          </div>

          <section className={sidebarSurfaceClass}>
            <div className="flex items-center gap-3">
              {profilePictureUrl ? (
                <img
                  src={profilePictureUrl}
                  alt={displayName || "user"}
                  className="h-11 w-11 rounded-2xl object-cover"
                />
              ) : (
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-500 via-blue-500 to-indigo-500 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(59,130,246,0.2)]">
                  {initial}
                </div>
              )}
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {displayName}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {(user as User | null)?.email || "Signed in"}
                </p>
              </div>
            </div>
            {canShowOrganizationContext ? (
              <div className="mt-4">
                <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Active Organization
                </p>
                {canSwitchOrganization ? (
                  <select
                    className="h-10 w-full rounded-2xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-xs"
                    value={activeOrganizationId || "__default__"}
                    onChange={(event) => {
                      void handleOrganizationSelection(event.target.value);
                    }}
                    disabled={switchingActiveOrganization}
                    aria-label="Switch active organization"
                  >
                    <option value="__default__">Default scope</option>
                    {resolvedOrganizations.map((org) => (
                      <option key={org.id} value={org.id}>
                        {org.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="rounded-2xl bg-muted/70 px-3 py-2 text-sm font-medium text-foreground">
                    {activeOrganizationLabel}
                  </div>
                )}
              </div>
            ) : null}
          </section>

          <section className={sidebarSectionClass}>
            {renderSectionHeader("Navigation")}
            <div className="space-y-1.5">
              {desktopPrimaryLinks.map((navItem) => {
                const NavIcon = getNavIcon(navItem);
                const active = isRouteActive(navItem.to);
                return (
                  <Link
                    key={navItem.to}
                    to={navItem.to}
                    className={desktopNavClass(navItem.to)}
                  >
                    <span className="inline-flex min-w-0 items-center gap-3">
                      <span className={sidebarIconClass(active)}>
                        <NavIcon className="h-4 w-4 shrink-0" />
                      </span>
                      <span className="truncate">{navItem.label}</span>
                    </span>
                    <span
                      aria-hidden="true"
                      className={[
                        "h-2 w-2 rounded-full transition-all duration-200",
                        active
                          ? "bg-primary opacity-100"
                          : "bg-transparent opacity-0 group-hover:opacity-30",
                      ].join(" ")}
                    />
                  </Link>
                );
              })}

              {desktopSecondaryLinks.length > 0 && (
                <button
                  type="button"
                  aria-label="More"
                  onClick={() => setMoreExpanded((prev) => !prev)}
                  className={[
                    sidebarLinkBaseClass,
                    "border-0 bg-transparent text-foreground hover:bg-accent/80 hover:text-accent-foreground",
                  ].join(" ")}
                >
                  <span className="inline-flex min-w-0 items-center gap-3">
                    <span className={sidebarIconClass(false)}>
                      <FileText className="h-4 w-4 shrink-0" />
                    </span>
                    <span className="truncate">
                      {moreExpanded ? "Less" : "More"}
                    </span>
                  </span>
                </button>
              )}

              {moreExpanded &&
                desktopSecondaryLinks.length > 0 &&
                desktopSecondaryLinks.map((navItem) => {
                  const NavIcon = getNavIcon(navItem);
                  const active = isRouteActive(navItem.to);
                  return (
                    <Link
                      key={navItem.to}
                      to={navItem.to}
                      className={desktopNavClass(navItem.to)}
                    >
                      <span className="inline-flex min-w-0 items-center gap-3">
                        <span className={sidebarIconClass(active)}>
                          <NavIcon className="h-4 w-4 shrink-0" />
                        </span>
                        <span className="truncate">{navItem.label}</span>
                      </span>
                    </Link>
                  );
                })}
            </div>
          </section>

          <section className={sidebarSectionClass}>
            {renderSectionHeader("Utilities")}
            <div className="space-y-1.5">
              {canAccessNotifications ? (
                <Link
                  to={workspaceNotificationsPath}
                  className={desktopUtilityLinkClass(
                    workspaceNotificationsPath,
                  )}
                >
                  <span className="inline-flex items-center gap-2">
                    <span
                      className={sidebarIconClass(
                        isRouteActive(workspaceNotificationsPath),
                      )}
                    >
                      <Bell className="h-4 w-4" />
                    </span>
                    Notifications
                  </span>
                  {unreadCount > 0 ? (
                    <span className="inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                  ) : null}
                </Link>
              ) : null}

              <ThemeToggle className="w-full justify-between rounded-[1rem] border-0 bg-transparent px-3 py-2.5 font-medium text-foreground shadow-none hover:bg-accent/80 hover:text-accent-foreground" />

              {renderRuntimePopover()}
            </div>
          </section>

          <section className={sidebarSectionClass}>
            {renderSectionHeader("Account")}
            <div className="space-y-1.5">
              <Link
                to="/settings"
                className={desktopUtilityLinkClass("/settings")}
              >
                <span className="inline-flex items-center gap-2">
                  <span
                    className={sidebarIconClass(isRouteActive("/settings"))}
                  >
                    <Settings2 className="h-4 w-4" />
                  </span>
                  Profile & Settings
                </span>
              </Link>
              {canManageTwoFactor ? (
                <Link
                  to="/security"
                  className={desktopUtilityLinkClass("/security")}
                >
                  <span className="inline-flex items-center gap-2">
                    <span
                      className={sidebarIconClass(isRouteActive("/security"))}
                    >
                      <ShieldCheck className="h-4 w-4" />
                    </span>
                    Security
                  </span>
                </Link>
              ) : null}
              <Link
                to="/change-password"
                className={desktopUtilityLinkClass("/change-password")}
              >
                <span className="inline-flex items-center gap-2">
                  <span
                    className={sidebarIconClass(
                      isRouteActive("/change-password"),
                    )}
                  >
                    <KeyRound className="h-4 w-4" />
                  </span>
                  Change Password
                </span>
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-2 rounded-[1rem] bg-destructive/10 px-3 py-2.5 text-sm font-semibold text-destructive transition-all duration-200 hover:bg-destructive/15"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          </section>
        </div>
      </aside>

      <nav className="sticky top-0 z-50 border-b border-border/70 bg-background/95 shadow-sm backdrop-blur-xl lg:hidden">
        <div className="mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link to={homeItem.to} className="flex items-center gap-2">
                <Shield className="h-7 w-7 text-primary sm:h-8 sm:w-8" />
                <span className="text-lg font-bold leading-none text-foreground sm:text-xl">
                  CAVP
                </span>
              </Link>
            </div>

            <div className="flex items-center lg:hidden">
              <Button
                type="button"
                variant="ghost"
                ref={mobileMenuButtonRef}
                onClick={() => {
                  setRuntimePopoverOpen(false);
                  if (!mobileMenuOpen) {
                    setMobileMenuMounted(true);
                  }
                  setMobileMenuOpen((previous) => !previous);
                }}
                aria-label={
                  mobileMenuOpen
                    ? "Close navigation menu"
                    : "Open navigation menu"
                }
                aria-expanded={mobileMenuOpen ? "true" : "false"}
                aria-controls="mobile-nav-drawer"
                className="rounded-md p-2 text-foreground hover:bg-accent hover:text-accent-foreground"
              >
                {mobileMenuOpen ? (
                  <X className="h-6 w-6" />
                ) : (
                  <Menu className="h-6 w-6" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </nav>
      {mobileMenuMounted ? (
        <div
          className={[
            "fixed inset-x-0 bottom-0 top-16 z-40 lg:hidden transition-opacity duration-200",
            mobileMenuOpen
              ? "pointer-events-auto opacity-100"
              : "pointer-events-none opacity-0",
          ].join(" ")}
        >
          <button
            type="button"
            aria-label="Close navigation menu"
            className={[
              "absolute inset-0 bg-foreground/20 transition-opacity duration-200",
              mobileMenuOpen ? "opacity-100" : "opacity-0",
            ].join(" ")}
            onClick={() => setMobileMenuOpen(false)}
          />
          <div
            id="mobile-nav-drawer"
            ref={mobileDrawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            tabIndex={-1}
            className={[
              "app-sidebar-scroll absolute right-0 top-0 h-full w-full max-w-sm overflow-y-auto overscroll-y-contain border-l border-border/70 bg-background/95 px-4 py-4 shadow-[0_18px_50px_rgba(15,23,42,0.18)] transition-transform duration-300 ease-out backdrop-blur-xl [scrollbar-gutter:stable]",
              mobileMenuOpen ? "translate-x-0" : "translate-x-full",
            ].join(" ")}
          >
            <div className="mb-4 flex items-center space-x-3">
              {profilePictureUrl ? (
                <img
                  src={profilePictureUrl}
                  alt={displayName || "user"}
                  className="h-10 w-10 rounded-full"
                />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-linear-to-br from-cyan-500 via-blue-500 to-indigo-500 text-lg font-semibold text-white">
                  {initial}
                </div>
              )}
              <div>
                <p className="text-base font-medium text-foreground">
                  {displayName}
                </p>
                <p className="text-sm text-muted-foreground">
                  {(user as User | null)?.email || "Signed in"}
                </p>
              </div>
            </div>

            <div className="space-y-4">
              {canShowOrganizationContext ? (
                <div className="rounded-[1.5rem] border border-border/70 bg-card/70 p-3.5 shadow-sm backdrop-blur-sm">
                  {canSwitchOrganization ? (
                    <select
                      className="h-10 w-full rounded-xl border border-border/70 bg-background px-2 text-sm text-foreground"
                      value={activeOrganizationId || "__default__"}
                      onChange={(event) => {
                        void handleOrganizationSelection(event.target.value);
                      }}
                      disabled={switchingActiveOrganization}
                      aria-label="Switch active organization"
                    >
                      <option value="__default__">Default scope</option>
                      {resolvedOrganizations.map((org) => (
                        <option key={org.id} value={org.id}>
                          {org.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <p className="text-sm text-foreground">
                      {activeOrganizationLabel}
                    </p>
                  )}
                </div>
              ) : null}

              <div className="border-t border-border/70 pt-4">
                {renderSectionHeader("Navigation")}
                <div className="space-y-1.5">
                  {navLinks.map((navItem) => {
                    const NavIcon = getNavIcon(navItem);
                    const active = isRouteActive(navItem.to);
                    return (
                      <Link
                        key={navItem.to}
                        to={navItem.to}
                        className={mobileNavClass(navItem.to)}
                        onClick={() => setMobileMenuOpen(false)}
                      >
                        <span className={`${sidebarIconClass(active)} mr-2`}>
                          <NavIcon className="h-4 w-4 shrink-0" />
                        </span>
                        {navItem.label}
                      </Link>
                    );
                  })}
                  {desktopSecondaryLinks.map((navItem) => {
                    const NavIcon = getNavIcon(navItem);
                    const active = isRouteActive(navItem.to);
                    return (
                      <Link
                        key={navItem.to}
                        to={navItem.to}
                        className={mobileNavClass(navItem.to)}
                        onClick={() => setMobileMenuOpen(false)}
                      >
                        <span className={`${sidebarIconClass(active)} mr-2`}>
                          <NavIcon className="h-4 w-4 shrink-0" />
                        </span>
                        {navItem.label}
                      </Link>
                    );
                  })}
                </div>
              </div>

              <div className="border-t border-border/70 pt-4">
                {renderSectionHeader("Utilities")}
                <div className="space-y-1.5">
                  {canAccessNotifications ? (
                    <Link
                      to={workspaceNotificationsPath}
                      className={[
                        "flex items-center justify-between rounded-[1rem] px-3 py-2.5 text-sm font-medium transition-all duration-200",
                        isRouteActive(workspaceNotificationsPath)
                          ? "bg-primary/10 text-primary ring-1 ring-primary/15"
                          : "text-foreground hover:bg-accent/80 hover:text-accent-foreground",
                      ].join(" ")}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <span className="inline-flex items-center gap-2">
                        <span
                          className={`${sidebarIconClass(isRouteActive(workspaceNotificationsPath))} mr-0`}
                        >
                          <Bell className="h-4 w-4" />
                        </span>
                        Notifications
                      </span>
                      {unreadCount > 0 ? (
                        <span className="rounded-full bg-destructive px-2 py-1 text-xs font-bold text-destructive-foreground">
                          {unreadCount > 99 ? "99+" : unreadCount}
                        </span>
                      ) : null}
                    </Link>
                  ) : null}

                  {/* Reminder Runtime button — feature disabled, hidden until re-enabled */}

                  <ThemeToggle className="w-full justify-between rounded-[1rem] border-0 bg-transparent px-3 py-2.5 font-medium text-foreground shadow-none hover:bg-accent/80 hover:text-accent-foreground" />
                </div>
              </div>

              <div className="border-t border-border/70 pt-4">
                {renderSectionHeader("Account")}
                <div className="space-y-1.5">
                  {canManageTwoFactor ? (
                    <Link
                      to="/security"
                      className={mobileNavClass("/security")}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <span
                        className={`${sidebarIconClass(isRouteActive("/security"))} mr-2`}
                      >
                        <ShieldCheck className="h-5 w-5" />
                      </span>
                      <span>Security</span>
                    </Link>
                  ) : null}

                  <Link
                    to="/settings"
                    className={mobileNavClass("/settings")}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span
                      className={`${sidebarIconClass(isRouteActive("/settings"))} mr-2`}
                    >
                      <Settings2 className="h-5 w-5" />
                    </span>
                    <span>Profile & Settings</span>
                  </Link>

                  <Link
                    to="/change-password"
                    className={mobileNavClass("/change-password")}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span
                      className={`${sidebarIconClass(isRouteActive("/change-password"))} mr-2`}
                    >
                      <KeyRound className="h-5 w-5" />
                    </span>
                    <span>Change Password</span>
                  </Link>

                  <button
                    type="button"
                    onClick={() => {
                      handleLogout();
                      setMobileMenuOpen(false);
                    }}
                    className="flex w-full items-center rounded-[1rem] bg-destructive/10 px-3 py-2.5 text-sm font-semibold text-destructive transition-all duration-200 hover:bg-destructive/15"
                  >
                    <LogOut className="mr-2 h-5 w-5" />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};
