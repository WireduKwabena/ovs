// src/components/common/Navbar.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  Bell,
  Bot,
  Briefcase,
  Building2,
  ChevronDown,
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
  SlidersHorizontal,
  UserRound,
  Users,
  Video,
  X,
} from 'lucide-react';
import { createSelector } from '@reduxjs/toolkit';
import { useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import type { AppDispatch, RootState } from '@/app/store';
import { useAuth } from '@/hooks/useAuth';
import { videoCallService } from '@/services/videoCall.service';
import { fetchNotifications } from '@/store/notificationSlice';
import type { User, VideoMeetingReminderHealth } from '@/types';
import { buildReminderNotificationTraceHref } from '@/utils/notificationTrace';
import { getUserDisplayName, getUserInitial } from '@/utils/userDisplay';

import { Button } from '../ui/button';
import { ThemeToggle } from './ThemeToggle';

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
type NavIcon = React.ComponentType<{ className?: string }>;

const navIconMap: Record<string, NavIcon> = {
  '/workspace': LayoutDashboard,
  '/admin/dashboard': LayoutDashboard,
  '/candidate/access': LayoutDashboard,
  '/organization/dashboard': LayoutDashboard,
  '/applications': FolderOpen,
  '/campaigns': Briefcase,
  '/rubrics': ClipboardCheck,
  '/video-calls': Video,
  '/admin/cases': FolderOpen,
  '/admin/users': Users,
  '/admin/analytics': BarChart3,
  '/admin/control-center': SlidersHorizontal,
  '/ai-monitor': Bot,
  '/ml-monitoring': Cpu,
  '/government/appointments': Scale,
  '/government/positions': Building2,
  '/government/personnel': UserRound,
  '/organization/members': Users,
  '/organization/committees': Users,
  '/organization/onboarding': ClipboardCheck,
  '/settings': CreditCard,
  '/fraud-insights': ShieldAlert,
  '/background-checks': Search,
  '/audit-logs': FileSearch,
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
  const [adminMoreMenuOpen, setAdminMoreMenuOpen] = useState(false);
  const [runtimePopoverOpen, setRuntimePopoverOpen] = useState(false);
  const [reminderRuntimeStatus, setReminderRuntimeStatus] = useState<ReminderRuntimeStatus>('unknown');
  const [reminderRuntimeSnapshot, setReminderRuntimeSnapshot] = useState<VideoMeetingReminderHealth | null>(null);
  const [reminderRuntimeCheckedAt, setReminderRuntimeCheckedAt] = useState<string | null>(null);
  const [reminderRuntimeError, setReminderRuntimeError] = useState<string | null>(null);
  const [reminderRuntimeRefreshing, setReminderRuntimeRefreshing] = useState(false);

  const adminMoreMenuRef = useRef<HTMLDivElement>(null);
  const runtimePopoverRef = useRef<HTMLDivElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);

  const { user, isAuthenticated, userType, roles, capabilities } = useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);

  const resolvedRoles = Array.isArray(roles) ? roles : [];
  const resolvedCapabilities = Array.isArray(capabilities) ? capabilities : [];
  const resolvedOrganizations = Array.isArray(organizations) ? organizations : [];

  const hasRole = (role: string): boolean => resolvedRoles.includes(role);
  const hasCapability = (capability: string): boolean => resolvedCapabilities.includes(capability);

  const hasAdminAccess =
    userType === 'admin' || hasRole('admin') || Boolean((user as User | null)?.is_superuser);
  const canAccessAudit = hasAdminAccess || canViewAuditLogs || hasCapability('gams.audit.view');
  const canAccessRegistry = hasAdminAccess || canManageRegistry;
  const canAccessAppointments = hasAdminAccess || canAccessAppointmentsFromHook;
  const canAccessRubrics = hasAdminAccess || canManageRubrics;
  const canAccessInternalRoutes = hasAdminAccess || canAccessInternalWorkflow;
  const isApplicantUser = userType === 'applicant';
  const canAccessNotifications = !isApplicantUser;
  const canShowOrganizationContext = !isApplicantUser && resolvedOrganizations.length > 0;
  const activeOrganizationLabel = activeOrganization?.name || resolvedOrganizations[0]?.name || 'Default scope';
  const canManageOrganizationBilling = hasAdminAccess || canManageActiveOrganizationGovernance;

  const handleOrganizationSelection = async (rawValue: string) => {
    const nextValue = rawValue === '__default__' ? null : rawValue;
    try {
      await selectActiveOrganization(nextValue);
      toast.success(nextValue ? 'Active organization updated.' : 'Organization context reset to default.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to switch active organization.');
    }
  };

  useEffect(() => {
    if (isAuthenticated && canAccessNotifications) {
      dispatch(fetchNotifications());
    }
  }, [canAccessNotifications, dispatch, isAuthenticated]);

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
      setReminderRuntimeError(error instanceof Error ? error.message : 'Runtime unavailable.');
    } finally {
      if (!options?.silent) {
        setReminderRuntimeRefreshing(false);
      }
    }
  };

  useEffect(() => {
    if (!isAuthenticated || userType !== 'admin') {
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
        setReminderRuntimeError(error instanceof Error ? error.message : 'Runtime unavailable.');
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
  }, [isAuthenticated, userType]);
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (adminMoreMenuRef.current && !adminMoreMenuRef.current.contains(event.target as Node)) {
        setAdminMoreMenuOpen(false);
      }
      if (runtimePopoverRef.current && !runtimePopoverRef.current.contains(event.target as Node)) {
        setRuntimePopoverOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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
    navigate('/login');
  };

  if (!isAuthenticated) {
    return null;
  }

  const displayName = getUserDisplayName(user, 'User');
  const initial = getUserInitial(user, displayName);
  const profilePictureUrl =
    (user as User | null)?.profile_picture_url || (user as User | null)?.avatar_url || '';
  const roleSummary = hasAdminAccess
    ? 'Platform Admin'
    : isApplicantUser
      ? 'Invited Candidate'
      : canManageActiveOrganizationGovernance
        ? 'Organization Governance'
        : 'Internal Operations';
  const canManageTwoFactor = !isApplicantUser;
  const canViewReminderRuntime = hasAdminAccess;

  const reminderStatusMeta: Record<ReminderRuntimeStatus, { dotClass: string; label: string }> = {
    unknown: { dotClass: 'bg-slate-500', label: 'Unknown' },
    healthy: { dotClass: 'bg-emerald-500', label: 'Healthy' },
    attention: { dotClass: 'bg-amber-500', label: 'Attention needed' },
    unavailable: { dotClass: 'bg-rose-500', label: 'Unavailable' },
  };

  const runtimeMeta = reminderStatusMeta[reminderRuntimeStatus];
  const runtimeLastChecked = reminderRuntimeCheckedAt
    ? new Date(reminderRuntimeCheckedAt).toLocaleTimeString()
    : 'Not checked yet';
  const getNavIcon = (navItem: NavItem): NavIcon => navIconMap[navItem.to] ?? FileText;

  const isRouteActive = (to: string): boolean => {
    if (location.pathname === to) {
      return true;
    }
    return location.pathname.startsWith(`${to}/`);
  };

  const desktopNavClass = (to: string): string =>
    [
      'flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300 shadow-sm'
        : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const overflowNavClass = (to: string): string =>
    [
      'flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const mobileNavClass = (to: string): string =>
    [
      'flex items-center rounded-lg px-3 py-2 transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:bg-indigo-50',
    ].join(' ');

  const desktopUtilityLinkClass = (to: string): string =>
    [
      'flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300 shadow-sm'
        : 'border border-slate-200 bg-white text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const homeItem: NavItem = isApplicantUser
    ? { to: '/candidate/access', label: 'Candidate Access' }
    : hasAdminAccess
      ? { to: '/admin/dashboard', label: 'Admin Dashboard' }
      : canManageActiveOrganizationGovernance && activeOrganizationId
        ? { to: '/organization/dashboard', label: 'Dashboard' }
        : { to: '/workspace', label: 'Workspace' };

  const desktopPrimaryLinks: NavItem[] = [homeItem];
  const desktopOverflowLinks: NavItem[] = [];

  const pushUnique = (target: NavItem[], item: NavItem) => {
    if (!target.some((entry) => entry.to === item.to)) {
      target.push(item);
    }
  };

  if (!isApplicantUser && canAccessApplications) {
    pushUnique(desktopPrimaryLinks, { to: '/applications', label: 'Applications' });
  }

  if (!isApplicantUser && canAccessCampaigns) {
    pushUnique(desktopPrimaryLinks, { to: '/campaigns', label: 'Appointment Exercises' });
  }

  if (!isApplicantUser && canAccessRubrics) {
    pushUnique(desktopPrimaryLinks, { to: '/rubrics', label: 'Rubrics' });
  }

  if (!isApplicantUser && (hasAdminAccess || canAccessVideoCalls)) {
    pushUnique(desktopPrimaryLinks, { to: '/video-calls', label: 'Video Calls' });
  }
  if (hasAdminAccess) {
    pushUnique(desktopOverflowLinks, { to: '/admin/cases', label: 'Cases' });
    pushUnique(desktopOverflowLinks, { to: '/admin/users', label: 'Users' });
    pushUnique(desktopOverflowLinks, { to: '/admin/analytics', label: 'Analytics' });
    pushUnique(desktopOverflowLinks, { to: '/admin/control-center', label: 'Control Center' });
    pushUnique(desktopOverflowLinks, { to: '/ai-monitor', label: 'AI Monitor' });
    pushUnique(desktopOverflowLinks, { to: '/ml-monitoring', label: 'ML Monitoring' });
  }

  if (!isApplicantUser && canAccessAppointments) {
    pushUnique(desktopOverflowLinks, {
      to: '/government/appointments',
      label: 'Appointment Workflow',
    });
  }

  if (!isApplicantUser && canAccessRegistry) {
    pushUnique(desktopOverflowLinks, { to: '/government/positions', label: 'Offices' });
    pushUnique(desktopOverflowLinks, { to: '/government/personnel', label: 'Nominees' });
  }

  if (!isApplicantUser && canManageActiveOrganizationGovernance && activeOrganizationId) {
    pushUnique(desktopOverflowLinks, { to: '/organization/members', label: 'Members' });
    pushUnique(desktopOverflowLinks, { to: '/organization/committees', label: 'Committees' });
    pushUnique(desktopOverflowLinks, { to: '/organization/onboarding', label: 'Onboarding' });
    if (canManageOrganizationBilling) {
      pushUnique(desktopOverflowLinks, { to: '/settings', label: 'Subscription' });
    }
  }

  if (!isApplicantUser && canAccessInternalRoutes && !hasAdminAccess) {
    pushUnique(desktopOverflowLinks, { to: '/fraud-insights', label: 'Fraud Insights' });
    pushUnique(desktopOverflowLinks, {
      to: '/background-checks',
      label: 'Background Checks',
    });
  }

  if (!isApplicantUser && canAccessAudit) {
    pushUnique(desktopOverflowLinks, { to: '/audit-logs', label: 'Audit' });
  }

  const navLinks: NavItem[] = [...desktopPrimaryLinks];
  desktopOverflowLinks.forEach((link) => pushUnique(navLinks, link));
  const hasActiveOverflowLink = desktopOverflowLinks.some((navItem) => isRouteActive(navItem.to));

  const renderRuntimePanel = (onNavigate?: () => void) => (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-800 shadow-xl">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Reminder Runtime</h3>
          <p className="text-xs text-slate-600">Status: {runtimeMeta.label}</p>
        </div>
        <span className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Soon Pending</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{reminderRuntimeSnapshot?.soon_retry_pending ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Soon Exhausted</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{reminderRuntimeSnapshot?.soon_retry_exhausted ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Start Pending</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{reminderRuntimeSnapshot?.start_now_retry_pending ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Time Up Exhausted</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{reminderRuntimeSnapshot?.time_up_retry_exhausted ?? 0}</p>
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-600">Last checked: {runtimeLastChecked}</p>
      {reminderRuntimeError ? <p className="mt-2 text-xs text-rose-700">{reminderRuntimeError}</p> : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void refreshReminderRuntime()}
          disabled={reminderRuntimeRefreshing}
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${reminderRuntimeRefreshing ? 'animate-spin' : ''}`} />
          {reminderRuntimeRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
        <Link
          to={buildReminderNotificationTraceHref()}
          onClick={() => {
            setRuntimePopoverOpen(false);
            onNavigate?.();
          }}
          className="inline-flex items-center justify-center rounded-md border border-indigo-300 bg-indigo-50 px-2.5 py-1.5 text-xs font-medium text-indigo-800 hover:bg-indigo-100"
        >
          Open reminder traces
        </Link>
      </div>
    </div>
  );

  const renderRuntimePopover = () => {
    if (!canViewReminderRuntime) {
      return null;
    }

    return (
      <div className="relative flex-1" ref={runtimePopoverRef}>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setRuntimePopoverOpen((previous) => !previous)}
          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm font-semibold text-slate-800 hover:bg-indigo-50 hover:text-indigo-700"
        >
          <span className="inline-flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
            Runtime
          </span>
          <span className="text-xs text-slate-600">{runtimeMeta.label}</span>
        </Button>
        {runtimePopoverOpen ? (
          <div className="absolute left-0 top-[calc(100%+0.5rem)] z-50 w-[22rem] max-w-[calc(100vw-2rem)]">
            {renderRuntimePanel()}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-slate-200 bg-slate-50/95 backdrop-blur lg:flex xl:w-72">
        <div className="flex h-full min-h-0 w-full flex-col">
          <div className="border-b border-slate-200 px-4 py-4 xl:px-5 xl:py-5">
            <Link to={homeItem.to} className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-sm">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-indigo-700">Workspace</p>
                <p className="text-xl font-bold tracking-tight text-slate-900">CAVP</p>
              </div>
            </Link>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto overscroll-y-contain px-3 py-4 [scrollbar-gutter:stable] xl:px-4">
              <div className="space-y-4">
                <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    {profilePictureUrl ? (
                      <img src={profilePictureUrl} alt={displayName || 'user'} className="h-11 w-11 rounded-2xl object-cover" />
                    ) : (
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-600 text-sm font-semibold text-white">
                        {initial}
                      </div>
                    )}
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
                      <p className="truncate text-xs text-slate-600">{(user as User | null)?.email || 'Signed in'}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-800">
                      {roleSummary}
                    </span>
                    {canShowOrganizationContext ? (
                      <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-700">
                        Scoped Access
                      </span>
                    ) : null}
                  </div>
                  {canShowOrganizationContext ? (
                    <div className="mt-4">
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                        Active Organization
                      </p>
                      {canSwitchOrganization ? (
                        <select
                          className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900"
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
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800">
                          {activeOrganizationLabel}
                        </div>
                      )}
                    </div>
                  ) : null}
                </section>

                <section className="space-y-2">
                  <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Navigation</p>
                  {desktopPrimaryLinks.map((navItem) => {
                    const NavIcon = getNavIcon(navItem);
                    return (
                      <Link key={navItem.to} to={navItem.to} className={desktopNavClass(navItem.to)}>
                        <span className="inline-flex min-w-0 items-center gap-3">
                          <NavIcon className="h-4 w-4 shrink-0" />
                          <span className="truncate">{navItem.label}</span>
                        </span>
                      </Link>
                    );
                  })}

                  {desktopOverflowLinks.length > 0 ? (
                    <div className="rounded-2xl border border-slate-200 bg-white p-2" ref={adminMoreMenuRef}>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          setAdminMoreMenuOpen((previous) => !previous);
                          setRuntimePopoverOpen(false);
                        }}
                        className={[
                          'flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm font-semibold',
                          hasActiveOverflowLink
                            ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                            : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
                        ].join(' ')}
                      >
                        <span>More</span>
                        <ChevronDown className={`h-4 w-4 text-slate-700 transition-transform ${adminMoreMenuOpen ? 'rotate-180' : ''}`} />
                      </Button>
                      {adminMoreMenuOpen ? (
                        <div className="mt-2 space-y-1">
                          {desktopOverflowLinks.map((navItem) => {
                            const NavIcon = getNavIcon(navItem);
                            return (
                              <Link
                                key={navItem.to}
                                to={navItem.to}
                                className={overflowNavClass(navItem.to)}
                                onClick={() => setAdminMoreMenuOpen(false)}
                              >
                                <span className="inline-flex min-w-0 items-center gap-3">
                                  <NavIcon className="h-4 w-4 shrink-0" />
                                  <span className="truncate">{navItem.label}</span>
                                </span>
                              </Link>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>

                <section className="space-y-2">
                  <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Utilities</p>
                  {canAccessNotifications ? (
                    <Link to="/notifications" className={desktopUtilityLinkClass('/notifications')}>
                      <span className="inline-flex items-center gap-2">
                        <Bell className="h-4 w-4" />
                        Notifications
                      </span>
                      {unreadCount > 0 ? (
                        <span className="inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
                          {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                      ) : null}
                    </Link>
                  ) : null}

                  <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-2">
                    <ThemeToggle className="flex-1 justify-center" />
                    {renderRuntimePopover()}
                  </div>
                </section>
              </div>
            </div>

            <div className="border-t border-slate-200 bg-white/90 p-3 xl:p-4">
              <div className="space-y-2">
                <Link to="/settings" className={desktopUtilityLinkClass('/settings')}>
                  <span className="inline-flex items-center gap-2">
                    <Settings2 className="h-4 w-4" />
                    Profile & Settings
                  </span>
                </Link>
                {canManageTwoFactor ? (
                  <Link to="/security" className={desktopUtilityLinkClass('/security')}>
                    <span className="inline-flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4" />
                      Security
                    </span>
                  </Link>
                ) : null}
                <Link to="/change-password" className={desktopUtilityLinkClass('/change-password')}>
                  <span className="inline-flex items-center gap-2">
                    <KeyRound className="h-4 w-4" />
                    Change Password
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm font-semibold text-red-700 transition hover:bg-red-100"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <nav className="sticky top-0 z-50 border-b border-slate-200 bg-slate-50 shadow-sm lg:hidden">
        <div className="mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link to={homeItem.to} className="flex items-center gap-2">
                <Shield className="h-7 w-7 text-indigo-600 sm:h-8 sm:w-8" />
                <span className="text-lg font-bold leading-none text-slate-900 sm:text-xl">CAVP</span>
              </Link>
            </div>

            <div className="flex items-center lg:hidden">
              <Button
                type="button"
                variant="ghost"
                ref={mobileMenuButtonRef}
                onClick={() => {
                  setAdminMoreMenuOpen(false);
                  setRuntimePopoverOpen(false);
                  if (!mobileMenuOpen) {
                    setMobileMenuMounted(true);
                  }
                  setMobileMenuOpen((previous) => !previous);
                }}
                aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                aria-expanded={mobileMenuOpen ? 'true' : 'false'}
                aria-controls="mobile-nav-drawer"
                className="rounded-md p-2 text-slate-800 hover:bg-indigo-50 hover:text-indigo-700"
              >
                {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </Button>
            </div>
          </div>
        </div>
      </nav>
      {mobileMenuMounted ? (
        <div
          className={[
            'fixed inset-x-0 bottom-0 top-16 z-40 lg:hidden transition-opacity duration-200',
            mobileMenuOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
          ].join(' ')}
        >
          <button
            type="button"
            aria-label="Close navigation menu"
            className={[
              'absolute inset-0 bg-slate-900/30 transition-opacity duration-200',
              mobileMenuOpen ? 'opacity-100' : 'opacity-0',
            ].join(' ')}
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
              'absolute right-0 top-0 h-full w-full max-w-sm overflow-y-auto overscroll-y-contain border-l border-slate-200 bg-white px-4 py-4 shadow-2xl transition-transform duration-300 ease-out [scrollbar-gutter:stable]',
              mobileMenuOpen ? 'translate-x-0' : 'translate-x-full',
            ].join(' ')}
          >
            <div className="mb-4 flex items-center space-x-3">
              {profilePictureUrl ? (
                <img src={profilePictureUrl} alt={displayName || 'user'} className="h-10 w-10 rounded-full" />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-lg font-semibold text-white">
                  {initial}
                </div>
              )}
              <div>
                <p className="text-base font-medium text-slate-900">{displayName}</p>
                <p className="text-sm text-slate-600">{(user as User | null)?.email || 'Signed in'}</p>
              </div>
            </div>

            <div className="space-y-3">
              {canShowOrganizationContext ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  {canSwitchOrganization ? (
                    <select
                      className="h-10 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-900"
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
                    <p className="text-sm text-slate-800">{activeOrganizationLabel}</p>
                  )}
                </div>
              ) : null}

              {navLinks.map((navItem) => {
                const NavIcon = getNavIcon(navItem);
                return (
                  <Link
                    key={navItem.to}
                    to={navItem.to}
                    className={mobileNavClass(navItem.to)}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <NavIcon className="mr-2 h-4 w-4 shrink-0" />
                    {navItem.label}
                  </Link>
                );
              })}

              {canAccessNotifications ? (
                <Link
                  to="/notifications"
                  className={[
                    'flex items-center justify-between rounded-lg px-3 py-2 transition-colors',
                    isRouteActive('/notifications')
                      ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                      : 'text-slate-800 hover:bg-indigo-50',
                  ].join(' ')}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <span className="text-slate-800">Notifications</span>
                  {unreadCount > 0 ? (
                    <span className="rounded-full bg-red-600 px-2 py-1 text-xs font-bold text-white">
                      {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                  ) : null}
                </Link>
              ) : null}

              {canViewReminderRuntime ? (
                <button
                  type="button"
                  onClick={() => setRuntimePopoverOpen((previous) => !previous)}
                  className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left"
                >
                  <span className="inline-flex items-center gap-2 text-slate-800">
                    <span className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
                    Reminder Runtime
                  </span>
                  <span className="text-xs font-semibold text-slate-700">{runtimeMeta.label}</span>
                </button>
              ) : null}

              {canViewReminderRuntime && runtimePopoverOpen ? (
                <div>{renderRuntimePanel(() => setMobileMenuOpen(false))}</div>
              ) : null}

              <div>
                <ThemeToggle className="w-full justify-center" />
              </div>

              {canManageTwoFactor ? (
                <Link
                  to="/security"
                  className={[
                    'flex items-center rounded-lg px-3 py-2 transition-colors',
                    isRouteActive('/security')
                      ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                      : 'hover:bg-indigo-50',
                  ].join(' ')}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <ShieldCheck className="mr-2 h-5 w-5 text-slate-700" />
                  <span className="text-slate-800">Security</span>
                </Link>
              ) : null}

              <Link
                to="/settings"
                className={[
                  'flex items-center rounded-lg px-3 py-2 transition-colors',
                  isRouteActive('/settings')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'hover:bg-indigo-50',
                ].join(' ')}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Settings2 className="mr-2 h-5 w-5 text-slate-700" />
                <span className="text-slate-800">Profile & Settings</span>
              </Link>

              <Link
                to="/change-password"
                className={[
                  'flex items-center rounded-lg px-3 py-2 transition-colors',
                  isRouteActive('/change-password')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'hover:bg-indigo-50',
                ].join(' ')}
                onClick={() => setMobileMenuOpen(false)}
              >
                <KeyRound className="mr-2 h-5 w-5 text-slate-700" />
                <span className="text-slate-800">Change Password</span>
              </Link>

              <button
                type="button"
                onClick={() => {
                  handleLogout();
                  setMobileMenuOpen(false);
                }}
                className="flex w-full items-center rounded-lg px-3 py-2 text-red-600 hover:bg-red-50"
              >
                <LogOut className="mr-2 h-5 w-5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};
