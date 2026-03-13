// src/components/common/Navbar.tsx (Sidebar-first navigation)
import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Bell,
  LogOut,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  KeyRound,
  Settings2,
  Shield,
  ShieldCheck,
  RefreshCw,
  LayoutDashboard,
  Building2,
  Workflow,
  Users2,
  FolderKanban,
  FileText,
  Video,
  ShieldAlert,
  CreditCard,
  Cpu,
  Bot,
  UserCheck2,
} from 'lucide-react';
import { Button } from '../ui/button';
import type { AppDispatch, RootState } from '@/app/store';
import { useDispatch, useSelector } from 'react-redux';
import { fetchNotifications } from '@/store/notificationSlice';
import type { User, VideoMeetingReminderHealth } from '@/types';
import { createSelector } from '@reduxjs/toolkit';
import { useAuth } from '@/hooks/useAuth';
import { getUserDisplayName, getUserInitial } from '@/utils/userDisplay';
import { videoCallService } from '@/services/videoCall.service';
import { ThemeToggle } from './ThemeToggle';
import { toast } from 'react-toastify';

const selectAuthState = (state: RootState) => state.auth;
const selectNotificationsState = (state: RootState) => state.notifications;

const selectUserData = createSelector([selectAuthState], (auth) => ({
  user: auth.user,
  isAuthenticated: auth.isAuthenticated,
  userType: auth.userType,
  roles: auth.roles ?? [],
  capabilities: auth.capabilities ?? [],
}));

const selectUnreadCount = createSelector(
  [selectNotificationsState],
  (notifications) => notifications.unreadCount || 0,
);

type ReminderRuntimeStatus = 'unknown' | 'healthy' | 'attention' | 'unavailable';
type NavItem = { to: string; label: string };
type NavSection = { key: string; title: string; items: NavItem[] };
type NavIcon = React.ComponentType<{ className?: string }>;

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'cavp.sidebar.collapsed.v1';
const PLATFORM_ADMIN_TENANT_ROUTE_PREFIXES = [
  '/organization',
  '/government',
  '/campaigns',
  '/applications',
  '/workspace',
  '/rubrics',
];

const SECTION_ICON_BY_KEY: Record<string, NavIcon> = {
  candidate: UserCheck2,
  workspace: LayoutDashboard,
  governance: Building2,
  workflow: Workflow,
  oversight: ShieldAlert,
  'admin-dashboard': LayoutDashboard,
  'admin-platform': Building2,
  'admin-operations': ShieldAlert,
  'admin-monitoring': Cpu,
};

const NAV_ITEM_ICON_BY_PATH: Record<string, NavIcon> = {
  '/workspace': LayoutDashboard,
  '/organization/setup': Building2,
  '/organization/dashboard': LayoutDashboard,
  '/organization/members': Users2,
  '/organization/committees': Workflow,
  '/organization/onboarding': KeyRound,
  '/subscribe': CreditCard,
  '/government/positions': Building2,
  '/government/personnel': UserCheck2,
  '/campaigns': FolderKanban,
  '/government/appointments': Workflow,
  '/applications': FileText,
  '/rubrics': FileText,
  '/video-calls': Video,
  '/fraud-insights': ShieldAlert,
  '/background-checks': ShieldAlert,
  '/audit-logs': ShieldCheck,
  '/admin/dashboard': LayoutDashboard,
  '/admin/organizations': Building2,
  '/admin/users': Users2,
  '/admin/control-center': Shield,
  '/admin/analytics': LayoutDashboard,
  '/ml-monitoring': Cpu,
  '/ai-monitor': Bot,
  '/candidate/access': UserCheck2,
  '/notifications': Bell,
  '/security': ShieldCheck,
  '/settings': Settings2,
  '/change-password': KeyRound,
};

const dedupeNavItems = (items: NavItem[]): NavItem[] => {
  const ordered = new Map<string, NavItem>();
  items.forEach((item) => {
    if (!ordered.has(item.to)) {
      ordered.set(item.to, item);
    }
  });
  return Array.from(ordered.values());
};

const dedupeNavSections = (sections: NavSection[]): NavSection[] => {
  const seenPaths = new Set<string>();
  return sections
    .map((section) => {
      const uniqueItems = section.items.filter((item) => {
        if (seenPaths.has(item.to)) {
          return false;
        }
        seenPaths.add(item.to);
        return true;
      });
      return { ...section, items: uniqueItems };
    })
    .filter((section) => section.items.length > 0);
};

export const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();

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

  const { user, isAuthenticated, userType, roles, capabilities } = useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileMenuMounted, setMobileMenuMounted] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    try {
      return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);

  const [reminderRuntimeStatus, setReminderRuntimeStatus] = useState<ReminderRuntimeStatus>('unknown');
  const [reminderRuntimeSnapshot, setReminderRuntimeSnapshot] = useState<VideoMeetingReminderHealth | null>(null);
  const [reminderRuntimeCheckedAt, setReminderRuntimeCheckedAt] = useState<string | null>(null);
  const [reminderRuntimeError, setReminderRuntimeError] = useState<string | null>(null);
  const [reminderRuntimeRefreshing, setReminderRuntimeRefreshing] = useState(false);

  const resolvedRoles = Array.isArray(roles) ? roles : [];
  const resolvedCapabilities = Array.isArray(capabilities) ? capabilities : [];
  const resolvedOrganizations = Array.isArray(organizations) ? organizations : [];

  const hasRole = (role: string): boolean => resolvedRoles.includes(role);
  const hasCapability = (capability: string): boolean => resolvedCapabilities.includes(capability);

  const hasAdminAccess =
    userType === 'admin' || hasRole('admin') || Boolean((user as User | null)?.is_superuser);
  const isPlatformAdmin = hasAdminAccess;
  const isPlatformAdminTenantMode =
    isPlatformAdmin &&
    Boolean(activeOrganizationId) &&
    PLATFORM_ADMIN_TENANT_ROUTE_PREFIXES.some(
      (prefix) =>
        location.pathname === prefix || location.pathname.startsWith(`${prefix}/`),
    );
  const canAccessAudit = hasAdminAccess || canViewAuditLogs || hasCapability('gams.audit.view');
  const canAccessRegistry = hasAdminAccess || canManageRegistry;
  const canAccessAppointments = hasAdminAccess || canAccessAppointmentsFromHook;
  const canAccessRubrics = hasAdminAccess || canManageRubrics;
  const canAccessInternalRoutes = hasAdminAccess || canAccessInternalWorkflow;
  const isApplicantUser = userType === 'applicant';
  const canAccessNotifications = !isApplicantUser;
  const canShowOrganizationContext =
    !isApplicantUser &&
    (resolvedOrganizations.length > 0 || Boolean(activeOrganizationId)) &&
    (!isPlatformAdmin || isPlatformAdminTenantMode);
  const activeOrganizationLabel =
    activeOrganization?.name || resolvedOrganizations[0]?.name || 'Default scope';
  const canManageOrganizationBilling = hasAdminAccess || canManageActiveOrganizationGovernance;

  const runtimeStatusMeta: Record<ReminderRuntimeStatus, { label: string; dotClass: string }> = {
    unknown: { label: 'Unknown', dotClass: 'bg-slate-500' },
    healthy: { label: 'Healthy', dotClass: 'bg-emerald-500' },
    attention: { label: 'Attention', dotClass: 'bg-amber-500' },
    unavailable: { label: 'Unavailable', dotClass: 'bg-rose-500' },
  };

  const applyReminderHealthPayload = (payload: VideoMeetingReminderHealth) => {
    const hasRetryIssues =
      payload.soon_retry_pending > 0 ||
      payload.soon_retry_exhausted > 0 ||
      payload.start_now_retry_pending > 0 ||
      payload.start_now_retry_exhausted > 0 ||
      payload.time_up_retry_pending > 0 ||
      payload.time_up_retry_exhausted > 0;
    setReminderRuntimeStatus(hasRetryIssues ? 'attention' : 'healthy');
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
      setReminderRuntimeStatus('unavailable');
      const message = error instanceof Error ? error.message : 'Reminder runtime unavailable.';
      setReminderRuntimeError(message);
    } finally {
      if (!options?.silent) {
        setReminderRuntimeRefreshing(false);
      }
    }
  };

  const handleOrganizationSelection = async (rawValue: string) => {
    const nextValue = rawValue === '__default__' ? null : rawValue;
    try {
      await selectActiveOrganization(nextValue);
      toast.success(nextValue ? 'Active organization updated.' : 'Organization context reset to default.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to switch active organization.');
    }
  };

  const handleReturnToPlatform = async () => {
    try {
      await selectActiveOrganization(null);
      toast.success('Returned to platform scope.');
      navigate('/admin/dashboard');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to return to platform scope.');
    }
  };

  useEffect(() => {
    if (isAuthenticated && canAccessNotifications) {
      dispatch(fetchNotifications());
    }
  }, [canAccessNotifications, dispatch, isAuthenticated]);

  useEffect(() => {
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
        setReminderRuntimeStatus('unavailable');
        const message = error instanceof Error ? error.message : 'Reminder runtime unavailable.';
        setReminderRuntimeError(message);
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
  }, [hasAdminAccess, isAuthenticated]);

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
      return Array.from(nodes).filter((node) => node.getAttribute('aria-hidden') !== 'true');
    };

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMobileMenuOpen(false);
        return;
      }

      if (event.key !== 'Tab') {
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

    document.body.style.overflow = 'hidden';
    window.setTimeout(() => {
      const focusableNodes = getFocusableInDrawer();
      if (focusableNodes.length > 0) {
        focusableNodes[0].focus();
      } else {
        mobileDrawerRef.current?.focus();
      }
    }, 0);
    document.addEventListener('keydown', handleKeydown);

    const menuButton = mobileMenuButtonRef.current;
    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener('keydown', handleKeydown);
      const fallbackTarget = menuButton;
      if (fallbackTarget && document.contains(fallbackTarget)) {
        fallbackTarget.focus();
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
  }, [mobileMenuOpen, mobileMenuMounted]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, isSidebarCollapsed ? '1' : '0');
    } catch {
      // no-op when storage is unavailable
    }
  }, [isSidebarCollapsed]);

  if (!isAuthenticated) {
    return null;
  }

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const displayName = getUserDisplayName(user, 'User');
  const initial = getUserInitial(user, '?');
  const profilePictureUrl = (user as User)?.profile_picture_url || '';
  const canManageTwoFactor = !isApplicantUser;

  const internalHomePath = canManageActiveOrganizationGovernance
    ? activeOrganizationId
      ? '/organization/dashboard'
      : '/organization/setup'
    : '/workspace';

  const getInternalLandingLabel = (path: string): string => {
    switch (path) {
      case '/organization/dashboard':
        return 'Dashboard';
      case '/organization/setup':
        return 'Organization Setup';
      case '/workspace':
        return 'Workspace';
      default:
        return 'Workspace';
    }
  };

  const candidateLinks: NavItem[] = [{ to: '/candidate/access', label: 'Candidate Access' }];

  const internalWorkflowLinks: NavItem[] = dedupeNavItems([
    ...(canAccessRegistry ? [{ to: '/government/positions', label: 'Offices' }] : []),
    ...(canAccessRegistry ? [{ to: '/government/personnel', label: 'Nominees' }] : []),
    ...(canAccessCampaigns ? [{ to: '/campaigns', label: 'Appointment Exercises' }] : []),
    ...(canAccessAppointments ? [{ to: '/government/appointments', label: 'Appointment Workflow' }] : []),
    ...(canAccessApplications ? [{ to: '/applications', label: 'Vetting Dossiers' }] : []),
    ...(canAccessRubrics ? [{ to: '/rubrics', label: 'Rubrics' }] : []),
    ...(canAccessVideoCalls ? [{ to: '/video-calls', label: 'Video Calls' }] : []),
  ]);

  const internalGovernanceLinks: NavItem[] = dedupeNavItems([
    ...(canManageActiveOrganizationGovernance && !activeOrganizationId
      ? [{ to: '/organization/setup', label: 'Organization Setup' }]
      : []),
    ...(canManageActiveOrganizationGovernance && activeOrganizationId
      ? [
          { to: '/organization/dashboard', label: 'Dashboard' },
          { to: '/organization/members', label: 'Members' },
          { to: '/organization/committees', label: 'Committees' },
          { to: '/organization/onboarding', label: 'Onboarding' },
          ...(canManageOrganizationBilling ? [{ to: '/subscribe', label: 'Subscription' }] : []),
        ]
      : []),
  ]);

  const platformTenantWorkflowLinks: NavItem[] = dedupeNavItems([
    ...(canAccessRegistry ? [{ to: '/government/positions', label: 'Offices' }] : []),
    ...(canAccessCampaigns ? [{ to: '/campaigns', label: 'Appointment Exercises' }] : []),
    ...(canAccessAppointments ? [{ to: '/government/appointments', label: 'Nominations' }] : []),
    ...(canAccessApplications ? [{ to: '/applications', label: 'Vetting Dossiers' }] : []),
  ]);

  const platformTenantGovernanceLinks: NavItem[] = dedupeNavItems([
    ...(activeOrganizationId ? [{ to: '/organization/members', label: 'Members' }] : []),
    ...(activeOrganizationId ? [{ to: '/organization/committees', label: 'Committees' }] : []),
  ]);

  const internalOversightLinks: NavItem[] = dedupeNavItems([
    ...(canAccessInternalRoutes ? [{ to: '/fraud-insights', label: 'Risk Signals' }] : []),
    ...(canAccessInternalRoutes ? [{ to: '/background-checks', label: 'Checks' }] : []),
    ...(canAccessAudit ? [{ to: '/audit-logs', label: 'Audit' }] : []),
  ]);

  const adminPlatformLinks: NavItem[] = dedupeNavItems([
    { to: '/admin/organizations', label: 'Organizations' },
    { to: '/admin/users', label: 'Organization Admins' },
  ]);

  const adminOperationsLinks: NavItem[] = dedupeNavItems([
    { to: '/video-calls', label: 'Runtime' },
    { to: '/audit-logs', label: 'Audit' },
    { to: '/fraud-insights', label: 'Risk Signals' },
    { to: '/background-checks', label: 'Checks' },
  ]);

  const adminMonitoringLinks: NavItem[] = dedupeNavItems([
    { to: '/admin/analytics', label: 'Analytics' },
    { to: '/ml-monitoring', label: 'ML Ops' },
    { to: '/ai-monitor', label: 'AI Monitor' },
  ]);

  const navSections: NavSection[] = hasAdminAccess
    ? isPlatformAdminTenantMode
      ? dedupeNavSections([
          { key: 'workspace', title: 'Dashboard', items: [{ to: '/organization/dashboard', label: 'Dashboard' }] },
          { key: 'governance', title: 'Organization Governance', items: platformTenantGovernanceLinks },
          { key: 'workflow', title: 'Appointment Workflow', items: platformTenantWorkflowLinks },
        ])
      : dedupeNavSections([
          { key: 'admin-dashboard', title: 'Dashboard', items: [{ to: '/admin/dashboard', label: 'Dashboard' }] },
          { key: 'admin-platform', title: 'Platform', items: adminPlatformLinks },
          { key: 'admin-operations', title: 'Operations', items: adminOperationsLinks },
          { key: 'admin-monitoring', title: 'Monitoring', items: adminMonitoringLinks },
        ])
    : isApplicantUser
      ? [{ key: 'candidate', title: 'Candidate Portal', items: candidateLinks }]
      : dedupeNavSections([
          {
            key: 'workspace',
            title: 'Workspace',
            items: [{ to: internalHomePath, label: getInternalLandingLabel(internalHomePath) }],
          },
          { key: 'governance', title: 'Organization Governance', items: internalGovernanceLinks },
          { key: 'workflow', title: 'Appointment Workflow', items: internalWorkflowLinks },
          { key: 'oversight', title: 'Oversight', items: internalOversightLinks },
        ]);

  const homePath = hasAdminAccess
    ? isPlatformAdminTenantMode
      ? '/organization/dashboard'
      : '/admin/dashboard'
    : isApplicantUser
      ? '/candidate/access'
      : internalHomePath;

  const getNavItemIcon = (path: string): NavIcon => {
    return NAV_ITEM_ICON_BY_PATH[path] || LayoutDashboard;
  };

  const isRouteActive = (to: string): boolean => {
    if (location.pathname === to) {
      return true;
    }
    return location.pathname.startsWith(`${to}/`);
  };

  const desktopNavClass = (to: string): string =>
    [
      'group flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const mobileNavClass = (to: string): string =>
    [
      'flex items-center rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const runtimeMeta = runtimeStatusMeta[reminderRuntimeStatus];
  const runtimeLastChecked = reminderRuntimeCheckedAt
    ? new Date(reminderRuntimeCheckedAt).toLocaleTimeString()
    : 'Not checked yet';

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-slate-50 lg:hidden">
        <div className="mx-auto flex h-16 items-center justify-between px-4">
          <Link to={homePath} className="inline-flex items-center gap-2">
            <Shield className="h-7 w-7 text-indigo-600" />
            <span className="text-lg font-bold text-slate-900">CAVP</span>
          </Link>
          <div className="flex items-center gap-2">
            {canAccessNotifications ? (
              <Link
                to="/notifications"
                className={`relative rounded-lg p-2 ${
                  isRouteActive('/notifications')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'text-slate-800 hover:bg-indigo-50'
                }`}
              >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 ? (
                  <span className="absolute -right-1 -top-1 inline-flex min-h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
              </Link>
            ) : null}
            <ThemeToggle compact />
            <Button
              type="button"
              variant="ghost"
              ref={mobileMenuButtonRef}
              onClick={() => {
                if (!mobileMenuOpen) {
                  setMobileMenuMounted(true);
                }
                setMobileMenuOpen((previous) => !previous);
              }}
              aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileMenuOpen ? 'true' : 'false'}
              aria-controls="mobile-sidebar-drawer"
              className="p-2 text-slate-800 hover:bg-indigo-50"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>
      </header>

      <aside
        className={`hidden h-screen shrink-0 border-r border-slate-200 bg-slate-50 transition-[width] duration-200 lg:flex lg:flex-col ${
          isSidebarCollapsed ? 'w-20' : 'w-72'
        }`}
      >
        <div className="flex h-full flex-col px-4 py-4">
          <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'justify-between'} gap-2`}>
            <Link
              to={homePath}
              className={`inline-flex items-center rounded-lg px-1 py-1 ${isSidebarCollapsed ? 'justify-center' : 'gap-2'}`}
              title={isSidebarCollapsed ? 'Dashboard' : undefined}
            >
              <Shield className="h-8 w-8 text-indigo-600" />
              {!isSidebarCollapsed ? <span className="text-xl font-bold text-slate-900">CAVP</span> : null}
            </Link>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsSidebarCollapsed((previous) => !previous)}
              className="hidden h-8 w-8 p-0 text-slate-800 hover:bg-indigo-50 lg:inline-flex"
              aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isSidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            </Button>
          </div>

          {canShowOrganizationContext ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
              {!isSidebarCollapsed ? (
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-700">Active Organization</p>
              ) : null}
              {canSwitchOrganization ? (
                <select
                  className={`h-9 rounded-md border border-slate-300 bg-white px-2 text-xs font-medium text-slate-800 ${
                    isSidebarCollapsed ? 'mt-0 w-full' : 'mt-2 w-full'
                  }`}
                  value={activeOrganizationId || '__default__'}
                  onChange={(event) => {
                    void handleOrganizationSelection(event.target.value);
                  }}
                  disabled={switchingActiveOrganization}
                  aria-label="Switch active organization"
                >
                  <option value="__default__">Default scope</option>
                  {resolvedOrganizations.map((org) => (
                    <option key={org.id} value={org.id}>
                      {isSidebarCollapsed ? org.code || org.name : org.name}
                    </option>
                  ))}
                </select>
              ) : (
                <p className={`${isSidebarCollapsed ? 'text-center text-xs' : 'mt-2 text-sm'} font-medium text-slate-900`}>
                  {isSidebarCollapsed ? activeOrganizationLabel.slice(0, 10) : activeOrganizationLabel}
                </p>
              )}
              {isPlatformAdminTenantMode ? (
                <button
                  type="button"
                  onClick={() => void handleReturnToPlatform()}
                  disabled={switchingActiveOrganization}
                  className={`mt-2 inline-flex items-center justify-center rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 ${
                    isSidebarCollapsed ? 'w-full' : ''
                  }`}
                >
                  Return to Platform
                </button>
              ) : null}
            </div>
          ) : null}

          {hasAdminAccess && !isPlatformAdminTenantMode ? (
            <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-700">Reminder Runtime</p>
                <span className={`inline-block h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
              </div>
              <p className="mt-1 text-xs font-semibold text-slate-900">{runtimeMeta.label}</p>
              <p className="mt-1 text-[11px] text-slate-700">Last checked: {runtimeLastChecked}</p>
              {reminderRuntimeSnapshot ? (
                <p className="mt-1 text-[11px] text-slate-700">
                  Pending retries: {reminderRuntimeSnapshot.soon_retry_pending + reminderRuntimeSnapshot.start_now_retry_pending + reminderRuntimeSnapshot.time_up_retry_pending}
                </p>
              ) : null}
              {reminderRuntimeError ? <p className="mt-1 text-[11px] text-rose-700">{reminderRuntimeError}</p> : null}
              <button
                type="button"
                onClick={() => void refreshReminderRuntime()}
                disabled={reminderRuntimeRefreshing}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${reminderRuntimeRefreshing ? 'animate-spin' : ''}`} />
                {reminderRuntimeRefreshing ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          ) : null}

          <nav className="mt-4 flex-1 space-y-4 overflow-y-auto pr-1">
            {navSections.map((section) => (
              <section key={section.key}>
                <div
                  className={`mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-700 ${
                    isSidebarCollapsed ? 'flex justify-center' : 'flex items-center gap-1.5'
                  }`}
                  title={isSidebarCollapsed ? section.title : undefined}
                >
                  {React.createElement(SECTION_ICON_BY_KEY[section.key] || LayoutDashboard, {
                    className: 'h-3.5 w-3.5',
                  })}
                  {!isSidebarCollapsed ? <span>{section.title}</span> : null}
                </div>
                <div className="space-y-1">
                  {section.items.map((navItem) => (
                    <Link
                      key={navItem.to}
                      to={navItem.to}
                      className={desktopNavClass(navItem.to)}
                      aria-label={navItem.label}
                      title={isSidebarCollapsed ? navItem.label : undefined}
                    >
                      <span className={`inline-flex items-center ${isSidebarCollapsed ? 'justify-center' : 'gap-2'}`}>
                        {React.createElement(getNavItemIcon(navItem.to), { className: 'h-4 w-4 shrink-0' })}
                        {!isSidebarCollapsed ? <span>{navItem.label}</span> : null}
                      </span>
                    </Link>
                  ))}
                </div>
              </section>
            ))}
          </nav>

          <div className="mt-4 space-y-2 border-t border-slate-200 pt-4">
            {canAccessNotifications ? (
              <Link
                to="/notifications"
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                  isRouteActive('/notifications')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  <Bell className="h-4 w-4" />
                  {!isSidebarCollapsed ? 'Notifications' : null}
                </span>
                {unreadCount > 0 ? (
                  <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
              </Link>
            ) : null}

            {canManageTwoFactor ? (
              <Link
                to="/security"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                  isRouteActive('/security')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700'
                }`}
                aria-label="Security"
                title={isSidebarCollapsed ? 'Security' : undefined}
              >
                <ShieldCheck className="h-4 w-4" />
                {!isSidebarCollapsed ? 'Security' : null}
              </Link>
            ) : null}

            <Link
              to="/settings"
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                isRouteActive('/settings')
                  ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                  : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700'
              }`}
              aria-label="Profile & Settings"
              title={isSidebarCollapsed ? 'Profile & Settings' : undefined}
            >
              <Settings2 className="h-4 w-4" />
              {!isSidebarCollapsed ? 'Profile & Settings' : null}
            </Link>

            <Link
              to="/change-password"
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                isRouteActive('/change-password')
                  ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                  : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700'
              }`}
              aria-label="Change Password"
              title={isSidebarCollapsed ? 'Change Password' : undefined}
            >
              <KeyRound className="h-4 w-4" />
              {!isSidebarCollapsed ? 'Change Password' : null}
            </Link>

            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <ThemeToggle className="w-full justify-center" />
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'gap-3'}`}>
                {profilePictureUrl ? (
                  <img src={profilePictureUrl} alt={displayName || 'user'} className="h-9 w-9 rounded-full" />
                ) : (
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 font-semibold text-white">
                    {initial}
                  </div>
                )}
                {!isSidebarCollapsed ? (
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
                    <p className="truncate text-xs text-slate-700">{(user as User | null)?.email || ''}</p>
                  </div>
                ) : null}
              </div>
              <Button
                type="button"
                onClick={handleLogout}
                variant="ghost"
                className={`mt-3 flex w-full items-center px-2 py-2 text-sm text-red-600 hover:bg-red-50 hover:text-red-700 ${
                  isSidebarCollapsed ? 'justify-center' : 'justify-start gap-2'
                }`}
                aria-label="Logout"
                title={isSidebarCollapsed ? 'Logout' : undefined}
              >
                <LogOut className="h-4 w-4" />
                {!isSidebarCollapsed ? 'Logout' : null}
              </Button>
            </div>
          </div>
        </div>
      </aside>

      {mobileMenuMounted ? (
        <div
          className={`fixed inset-0 z-50 lg:hidden transition-opacity duration-200 ${
            mobileMenuOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
          }`}
        >
          <button
            type="button"
            aria-label="Close navigation menu"
            className={`absolute inset-0 bg-slate-900/30 transition-opacity duration-200 ${
              mobileMenuOpen ? 'opacity-100' : 'opacity-0'
            }`}
            onClick={() => setMobileMenuOpen(false)}
          />
          <div
            id="mobile-sidebar-drawer"
            ref={mobileDrawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            tabIndex={-1}
            className={`absolute left-0 top-0 h-full w-full max-w-sm overflow-y-auto border-r border-slate-200 bg-white px-4 py-4 shadow-2xl transition-transform duration-300 ease-out ${
              mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <div className="mb-4 flex items-center justify-between">
              <Link
                to={homePath}
                className="inline-flex items-center gap-2"
                onClick={() => setMobileMenuOpen(false)}
              >
                <Shield className="h-7 w-7 text-indigo-600" />
                <span className="text-lg font-bold text-slate-900">CAVP</span>
              </Link>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setMobileMenuOpen(false)}
                className="p-2 text-slate-800 hover:bg-indigo-50"
                aria-label="Close navigation menu"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            {canShowOrganizationContext ? (
              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-700">Active Organization</p>
                {canSwitchOrganization ? (
                  <select
                    className="mt-2 h-10 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-900"
                    value={activeOrganizationId || '__default__'}
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
                  <p className="mt-2 text-sm text-slate-800">{activeOrganizationLabel}</p>
                )}
                {isPlatformAdminTenantMode ? (
                  <button
                    type="button"
                    onClick={async () => {
                      await handleReturnToPlatform();
                      setMobileMenuOpen(false);
                    }}
                    disabled={switchingActiveOrganization}
                    className="mt-2 inline-flex w-full items-center justify-center rounded-md border border-slate-300 px-2 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Return to Platform
                  </button>
                ) : null}
              </div>
            ) : null}

            <nav className="space-y-4">
              {navSections.map((section) => (
                <section key={section.key}>
                  <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-700">
                    {section.title}
                  </p>
                  <div className="space-y-1">
                    {section.items.map((navItem) => (
                      <Link
                        key={navItem.to}
                        to={navItem.to}
                        className={mobileNavClass(navItem.to)}
                        onClick={() => setMobileMenuOpen(false)}
                      >
                        {navItem.label}
                      </Link>
                    ))}
                  </div>
                </section>
              ))}
            </nav>

            <div className="mt-4 space-y-2 border-t border-slate-200 pt-4">
              {canAccessNotifications ? (
                <Link
                  to="/notifications"
                  className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                    isRouteActive('/notifications')
                      ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                      : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700'
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <span className="inline-flex items-center gap-2">
                    <Bell className="h-4 w-4" />
                    Notifications
                  </span>
                  {unreadCount > 0 ? (
                    <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                  ) : null}
                </Link>
              ) : null}

              {canManageTwoFactor ? (
                <Link
                  to="/security"
                  className={mobileNavClass('/security')}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Security
                </Link>
              ) : null}

              <Link
                to="/settings"
                className={mobileNavClass('/settings')}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Settings2 className="mr-2 h-4 w-4" />
                Profile & Settings
              </Link>

              <Link
                to="/change-password"
                className={mobileNavClass('/change-password')}
                onClick={() => setMobileMenuOpen(false)}
              >
                <KeyRound className="mr-2 h-4 w-4" />
                Change Password
              </Link>

              <div className="pt-2">
                <ThemeToggle className="w-full justify-center" />
              </div>

              <button
                type="button"
                onClick={() => {
                  handleLogout();
                  setMobileMenuOpen(false);
                }}
                className="flex w-full items-center rounded-lg px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};
