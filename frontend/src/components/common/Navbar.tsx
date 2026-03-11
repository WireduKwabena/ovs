// src/components/common/Navbar.tsx (Fixed - Type-Safe User Display)
import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, LogOut, Menu, X, ChevronDown, KeyRound, Settings2, Shield, ShieldCheck, RefreshCw } from 'lucide-react';
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

// ✅ CRITICAL: Define selectors OUTSIDE the component
const selectAuthState = (state: RootState) => state.auth;
const selectNotificationsState = (state: RootState) => state.notifications;

// ✅ Create memoized selectors
const selectUserData = createSelector(
  [selectAuthState],
  (auth) => ({
    user: auth.user,
    isAuthenticated: auth.isAuthenticated,
    userType: auth.userType,
    roles: auth.roles ?? [],
    capabilities: auth.capabilities ?? [],
  })
);

const selectUnreadCount = createSelector(
  [selectNotificationsState],
  (notifications) => notifications.unreadCount || 0
);

type ReminderRuntimeStatus = 'unknown' | 'healthy' | 'attention' | 'unavailable';

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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileMenuMounted, setMobileMenuMounted] = useState(false);
  const [adminMoreMenuOpen, setAdminMoreMenuOpen] = useState(false);
  const [runtimePopoverOpen, setRuntimePopoverOpen] = useState(false);
  const dispatch = useDispatch<AppDispatch>();

  
  // ✅ Line 14 should be around here - use memoized selectors
  const { user, isAuthenticated, userType, roles, capabilities } = useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [reminderRuntimeStatus, setReminderRuntimeStatus] = useState<ReminderRuntimeStatus>('unknown');
  const [reminderRuntimeSnapshot, setReminderRuntimeSnapshot] = useState<VideoMeetingReminderHealth | null>(null);
  const [reminderRuntimeCheckedAt, setReminderRuntimeCheckedAt] = useState<string | null>(null);
  const [reminderRuntimeError, setReminderRuntimeError] = useState<string | null>(null);
  const [reminderRuntimeRefreshing, setReminderRuntimeRefreshing] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const adminMoreMenuRef = useRef<HTMLDivElement>(null);
  const runtimePopoverRef = useRef<HTMLDivElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);
  const resolvedRoles = Array.isArray(roles) ? roles : [];
  const resolvedCapabilities = Array.isArray(capabilities) ? capabilities : [];
  const resolvedOrganizations = Array.isArray(organizations) ? organizations : [];

  const hasRole = (role: string): boolean => resolvedRoles.includes(role);
  const hasCapability = (capability: string): boolean => resolvedCapabilities.includes(capability);

  const hasAdminAccess =
    userType === "admin" || hasRole("admin") || Boolean((user as User | null)?.is_superuser);
  const canAccessAudit = hasAdminAccess || canViewAuditLogs || hasCapability("gams.audit.view");
  const canAccessRegistry = hasAdminAccess || canManageRegistry;
  const canAccessAppointments = hasAdminAccess || canAccessAppointmentsFromHook;
  const canAccessRubrics = hasAdminAccess || canManageRubrics;
  const canAccessInternalRoutes = hasAdminAccess || canAccessInternalWorkflow;
  const isApplicantUser = userType === "applicant";
  const canShowOrganizationContext = !isApplicantUser && resolvedOrganizations.length > 0;
  const activeOrganizationLabel = activeOrganization?.name || resolvedOrganizations[0]?.name || 'Default scope';

  const handleOrganizationSelection = async (rawValue: string) => {
    const nextValue = rawValue === "__default__" ? null : rawValue;
    try {
      await selectActiveOrganization(nextValue);
      toast.success(nextValue ? "Active organization updated." : "Organization context reset to default.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to switch active organization.");
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchNotifications());
    }
  }, [dispatch, isAuthenticated]);

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
  }, [isAuthenticated, userType]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
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
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
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
    // If open, we don't need a timeout
    if (mobileMenuOpen || !mobileMenuMounted) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setMobileMenuMounted(false);
    }, 240);

    return () => window.clearTimeout(timeout);
  }, [mobileMenuOpen, mobileMenuMounted]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!isAuthenticated) return null;

  const displayName = getUserDisplayName(user, 'User');

  const roleLabel = hasAdminAccess
    ? "Admin"
    : isApplicantUser
      ? "Candidate Access"
      : canManageActiveOrganizationGovernance
        ? "Organization Admin"
        : canAccessInternalRoutes
          ? "Operations User"
          : "User";
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

  const isRouteActive = (to: string): boolean => {
    if (location.pathname === to) {
      return true;
    }
    return location.pathname.startsWith(`${to}/`);
  };

  const desktopNavClass = (to: string): string =>
    [
      'text-sm font-semibold px-2 py-1 rounded transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:text-indigo-700 hover:bg-indigo-50',
    ].join(' ');

  const overflowNavClass = (to: string): string =>
    [
      'block px-4 py-2 text-sm font-medium transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900'
        : 'text-slate-800 hover:bg-indigo-50 hover:text-indigo-700',
    ].join(' ');

  const mobileNavClass = (to: string): string =>
    [
      'flex items-center px-3 py-2 rounded-lg transition-colors',
      isRouteActive(to)
        ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
        : 'text-slate-800 hover:bg-indigo-50',
    ].join(' ');

  const renderNavLabel = (navItem: { to: string; label: string }) => {
    if (!canViewReminderRuntime || navItem.to !== '/video-calls') {
      return navItem.label;
    }

    return (
      <span className="inline-flex items-center gap-1.5">
        <span>{navItem.label}</span>
        <span
          className={`inline-block h-2 w-2 rounded-full ${runtimeMeta.dotClass}`}
          title={`Reminder runtime: ${runtimeMeta.label}`}
          aria-label={`Reminder runtime ${runtimeMeta.label}`}
        />
      </span>
    );
  };

  const renderRuntimePopover = () => {
    if (!canViewReminderRuntime) {
      return null;
    }

    return (
      <div className="relative" ref={runtimePopoverRef}>
        <Button
          type="button"
          onClick={() => setRuntimePopoverOpen((previous) => !previous)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50"
          aria-expanded={runtimePopoverOpen ? 'true' : 'false'}
          aria-haspopup="dialog"
        >
          <span className={`h-2.5 w-2.5 rounded-full ${runtimeMeta.dotClass}`} />
          Runtime
        </Button>
        {runtimePopoverOpen && (
          <div className="absolute right-0 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-900">Reminder Runtime</p>
              <span className="text-[11px] font-semibold text-slate-700">{runtimeMeta.label}</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-700">Last checked: {runtimeLastChecked}</p>

            {reminderRuntimeSnapshot ? (
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-800">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Soon Pending</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.soon_retry_pending}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Soon Exhausted</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.soon_retry_exhausted}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Start Pending</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.start_now_retry_pending}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Start Exhausted</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.start_now_retry_exhausted}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Time-up Pending</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.time_up_retry_pending}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="font-semibold text-slate-700">Time-up Exhausted</p>
                  <p className="text-sm font-bold text-slate-900">{reminderRuntimeSnapshot.time_up_retry_exhausted}</p>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-700">No runtime snapshot available yet.</p>
            )}

            {reminderRuntimeError ? (
              <p className="mt-2 text-xs text-rose-700">{reminderRuntimeError}</p>
            ) : null}

            <button
              type="button"
              onClick={() => void refreshReminderRuntime()}
              disabled={reminderRuntimeRefreshing}
              className="mt-3 inline-flex items-center gap-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${reminderRuntimeRefreshing ? 'animate-spin' : ''}`} />
              {reminderRuntimeRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        )}
      </div>
    );
  };

  const candidateLinks = [{ to: '/candidate/access', label: 'Candidate Access' }];
  const internalPrimaryLinks = [
    { to: '/dashboard', label: 'Dashboard' },
    ...(canAccessCampaigns ? [{ to: '/campaigns', label: 'Campaigns' }] : []),
    ...(canAccessApplications ? [{ to: '/applications', label: 'Cases' }] : []),
    ...(canAccessRubrics ? [{ to: '/rubrics', label: 'Rubrics' }] : []),
    ...(canAccessVideoCalls ? [{ to: '/video-calls', label: 'Video Calls' }] : []),
  ];
  const internalOverflowLinks = [
    ...(canManageActiveOrganizationGovernance && !activeOrganizationId
      ? [{ to: '/organization/setup', label: 'Org Setup' }]
      : []),
    ...(canManageActiveOrganizationGovernance && activeOrganizationId
      ? [
          { to: '/organization/dashboard', label: 'Org Workspace' },
          { to: '/organization/members', label: 'Org Members' },
          { to: '/organization/committees', label: 'Committees' },
          { to: '/organization/onboarding', label: 'Onboarding' },
        ]
      : []),
    ...(canAccessAppointments ? [{ to: '/government/appointments', label: 'Appointments' }] : []),
    ...(canAccessRegistry ? [{ to: '/government/positions', label: 'Positions' }] : []),
    ...(canAccessRegistry ? [{ to: '/government/personnel', label: 'Personnel' }] : []),
    ...(canAccessInternalRoutes ? [{ to: '/fraud-insights', label: 'Fraud' }] : []),
    ...(canAccessInternalRoutes ? [{ to: '/background-checks', label: 'Checks' }] : []),
    ...(canAccessAudit ? [{ to: '/audit-logs', label: 'Audit' }] : []),
  ];
  const adminPrimaryLinks = [
    { to: '/admin/dashboard', label: 'Dashboard' },
    { to: '/admin/cases', label: 'Cases' },
    { to: '/admin/users', label: 'Users' },
    { to: '/rubrics', label: 'Rubrics' },
  ];
  const adminOverflowLinks = [
    ...(!activeOrganizationId ? [{ to: '/organization/setup', label: 'Org Setup' }] : []),
    ...(activeOrganizationId
      ? [
          { to: '/organization/dashboard', label: 'Org Workspace' },
          { to: '/organization/members', label: 'Org Members' },
          { to: '/organization/committees', label: 'Committees' },
          { to: '/organization/onboarding', label: 'Onboarding' },
        ]
      : []),
    { to: '/government/appointments', label: 'Appointments' },
    { to: '/government/positions', label: 'Positions' },
    { to: '/government/personnel', label: 'Personnel' },
    { to: '/video-calls', label: 'Video Calls' },
    { to: '/admin/control-center', label: 'Admin Control' },
    { to: '/fraud-insights', label: 'Fraud' },
    { to: '/background-checks', label: 'Checks' },
    { to: '/audit-logs', label: 'Audit' },
    { to: '/ml-monitoring', label: 'ML Ops' },
    { to: '/ai-monitor', label: 'AI Monitor' },
    { to: '/admin/analytics', label: 'Analytics' },
  ];

  const navLinks = hasAdminAccess
    ? [...adminPrimaryLinks, ...adminOverflowLinks]
    : isApplicantUser
      ? candidateLinks
      : [...internalPrimaryLinks, ...internalOverflowLinks];

  const desktopPrimaryLinks = hasAdminAccess
    ? adminPrimaryLinks
    : isApplicantUser
      ? candidateLinks
      : internalPrimaryLinks;

  const desktopOverflowLinks = hasAdminAccess
    ? adminOverflowLinks
    : isApplicantUser
      ? []
      : internalOverflowLinks;
  const hasActiveOverflowLink = desktopOverflowLinks.some((item) => isRouteActive(item.to));
  
  const initial = getUserInitial(user, '?');

  const profile_picture_url = (user as User)?.profile_picture_url || "";

  const homePath = hasAdminAccess ? "/admin/dashboard" : isApplicantUser ? "/candidate/access" : "/dashboard";

  return (
    <nav className="bg-slate-50 border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to={homePath} className="flex items-center">
              <div className="flex items-center">
              <Shield className="h-7 w-7 text-indigo-600 sm:h-8 sm:w-8" />
              <span className="ml-2 text-lg leading-none font-bold text-gray-900 sm:text-xl xl:text-2xl">
                <span className="sm:hidden">CAVP</span>
                <span className="hidden sm:inline">CAVP</span>
              </span>
            </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden xl:flex items-center space-x-2">
            {desktopPrimaryLinks.map((navItem) => (
              <Link
                key={navItem.to}
                to={navItem.to}
                className={desktopNavClass(navItem.to)}
              >
                {renderNavLabel(navItem)}
              </Link>
            ))}
            {desktopOverflowLinks.length > 0 && (
              <div className="relative" ref={adminMoreMenuRef}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setAdminMoreMenuOpen(!adminMoreMenuOpen);
                    setProfileMenuOpen(false);
                    setRuntimePopoverOpen(false);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-1 text-sm font-semibold rounded ${
                    hasActiveOverflowLink
                      ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                      : 'text-slate-800 hover:text-indigo-700 hover:bg-indigo-50'
                  }`}
                >
                  More
                  <ChevronDown className="w-4 h-4 text-slate-700" />
                </Button>
                {adminMoreMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-20 border">
                    {desktopOverflowLinks.map((navItem) => (
                      <Link
                        key={navItem.to}
                        to={navItem.to}
                        className={overflowNavClass(navItem.to)}
                        onClick={() => setAdminMoreMenuOpen(false)}
                      >
                        {renderNavLabel(navItem)}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
            {canShowOrganizationContext ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">Org</span>
                {canSwitchOrganization ? (
                  <select
                    className="h-9 rounded-md border border-slate-300 bg-white px-2 text-xs font-medium text-slate-800"
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
                  <span className="inline-flex h-9 items-center rounded-md border border-slate-300 bg-white px-2 text-xs font-medium text-slate-800">
                    {activeOrganizationLabel}
                  </span>
                )}
              </div>
            ) : null}
            {renderRuntimePopover()}
            <ThemeToggle compact />
            <Link
              to="/notifications"
              className={`relative rounded-lg p-2 ${
                isRouteActive('/notifications')
                  ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                  : 'text-slate-800 hover:text-indigo-700 hover:bg-indigo-50'
              }`}
            >
              <Bell className="w-6 h-6" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </Link>

            <div className="relative" ref={profileMenuRef}>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setProfileMenuOpen(!profileMenuOpen);
                  setAdminMoreMenuOpen(false);
                  setRuntimePopoverOpen(false);
                }}
                aria-expanded={profileMenuOpen ? "true" : "false"}
                aria-haspopup="true"
                aria-label="Toggle profile menu"
                className="flex items-center space-x-2 ml-4 p-2 text-slate-800 rounded-lg hover:bg-indigo-50"
              >
                {profile_picture_url ? (
                  <img src={profile_picture_url} alt={displayName || 'user'} className="w-8 h-8 rounded-full" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
                    {initial}
                  </div>
                )}
                <div className="ml-2 text-left">
                  <p className="text-sm font-medium text-indigo-600">
                    {displayName}
                  </p>
                  <p className="text-xs text-slate-700">{roleLabel}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-700" />
              </Button>
              {profileMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg py-1 z-20 border">
                  <Link
                    to="/settings"
                    className="flex items-center w-full px-4 py-2 text-sm font-medium text-slate-800 hover:bg-indigo-50"
                    onClick={() => setProfileMenuOpen(false)}
                  >
                    <Settings2 className="w-4 h-4 mr-2" />
                    Profile & Settings
                  </Link>
                  {canManageTwoFactor && (
                    <Link
                      to="/security"
                      className="flex items-center w-full px-4 py-2 text-sm font-medium text-slate-800 hover:bg-indigo-50"
                      onClick={() => setProfileMenuOpen(false)}
                    >
                      <ShieldCheck className="w-4 h-4 mr-2" />
                      Security
                    </Link>
                  )}
                  <Link
                    to="/change-password"
                    className="flex items-center w-full px-4 py-2 text-sm font-medium text-slate-800 hover:bg-indigo-50"
                    onClick={() => setProfileMenuOpen(false)}
                  >
                    <KeyRound className="w-4 h-4 mr-2" />
                    Change Password
                  </Link>
                  <Button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 hover:text-red-700 justify-start"
                    variant="ghost"
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="xl:hidden flex items-center">
            <Button
              type="button"
              variant="ghost"
              ref={mobileMenuButtonRef}
              onClick={() => {
                setProfileMenuOpen(false);
                setAdminMoreMenuOpen(false);
                setRuntimePopoverOpen(false);
                if (!mobileMenuOpen) {
                  setMobileMenuMounted(true);
                }
                setMobileMenuOpen((previous) => !previous);
              }}
              aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileMenuOpen ? "true" : "false"}
              aria-controls="mobile-nav-drawer"
              className="p-2 rounded-md text-slate-800 hover:text-indigo-700 hover:bg-indigo-50"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuMounted && (
        <div
          className={`fixed inset-x-0 top-16 bottom-0 z-40 xl:hidden transition-opacity duration-200 ${
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
            id="mobile-nav-drawer"
            ref={mobileDrawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            tabIndex={-1}
            className={`absolute right-0 top-0 h-full w-full max-w-sm overflow-y-auto border-l border-gray-200 bg-white px-4 py-4 shadow-2xl transition-transform duration-300 ease-out ${
              mobileMenuOpen ? 'translate-x-0' : 'translate-x-full'
            }`}
          >
            <div className="flex items-center space-x-3 mb-4">
              {profile_picture_url ? (
                <img src={profile_picture_url} alt={displayName || 'user'} className="w-10 h-10 rounded-full" />
              ) : (
                <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold text-lg">
                  {initial}
                </div>
              )}
              <div>
                <p className="text-base font-medium text-gray-900">
                  {displayName}
                </p>
                <p className="text-sm text-slate-700">{roleLabel}</p>
              </div>
            </div>
            <div className="space-y-3">
              {canShowOrganizationContext ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Organization Context</p>
                  {canSwitchOrganization ? (
                    <select
                      className="mt-2 h-10 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-900"
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
                    <p className="mt-2 text-sm text-slate-800">{activeOrganizationLabel}</p>
                  )}
                </div>
              ) : null}
              {navLinks.map((navItem) => (
                <Link
                  key={navItem.to}
                  to={navItem.to}
                  className={mobileNavClass(navItem.to)}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {renderNavLabel(navItem)}
                </Link>
              ))}
              <Link
                to="/notifications"
                className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                  isRouteActive('/notifications')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'hover:bg-indigo-50 text-slate-800'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <span className="text-slate-800">Notifications</span>
                {unreadCount > 0 && (
                  <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded-full">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </Link>
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
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
                  <p className="font-semibold text-slate-900">Last checked: {runtimeLastChecked}</p>
                  {reminderRuntimeSnapshot ? (
                    <ul className="mt-2 space-y-1">
                      <li>Soon: {reminderRuntimeSnapshot.soon_retry_pending} pending / {reminderRuntimeSnapshot.soon_retry_exhausted} exhausted</li>
                      <li>Start: {reminderRuntimeSnapshot.start_now_retry_pending} pending / {reminderRuntimeSnapshot.start_now_retry_exhausted} exhausted</li>
                      <li>Time-up: {reminderRuntimeSnapshot.time_up_retry_pending} pending / {reminderRuntimeSnapshot.time_up_retry_exhausted} exhausted</li>
                    </ul>
                  ) : (
                    <p className="mt-2">No runtime snapshot available yet.</p>
                  )}
                  {reminderRuntimeError ? <p className="mt-2 text-rose-700">{reminderRuntimeError}</p> : null}
                  <button
                    type="button"
                    onClick={() => void refreshReminderRuntime()}
                    disabled={reminderRuntimeRefreshing}
                    className="mt-3 inline-flex items-center gap-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${reminderRuntimeRefreshing ? 'animate-spin' : ''}`} />
                    {reminderRuntimeRefreshing ? 'Refreshing...' : 'Refresh'}
                  </button>
                </div>
              ) : null}
              <div>
                <ThemeToggle className="w-full justify-center" />
              </div>
              {canManageTwoFactor && (
                <Link
                  to="/security"
                  className={`flex items-center px-3 py-2 rounded-lg transition-colors ${
                    isRouteActive('/security')
                      ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                      : 'hover:bg-indigo-50'
                  }`}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <ShieldCheck className="w-5 h-5 mr-2 text-slate-700" />
                  <span className="text-slate-800">Security</span>
                </Link>
              )}
              <Link
                to="/settings"
                className={`flex items-center px-3 py-2 rounded-lg transition-colors ${
                  isRouteActive('/settings')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'hover:bg-indigo-50'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Settings2 className="w-5 h-5 mr-2 text-slate-700" />
                <span className="text-slate-800">Profile & Settings</span>
              </Link>
              <Link
                to="/change-password"
                className={`flex items-center px-3 py-2 rounded-lg transition-colors ${
                  isRouteActive('/change-password')
                    ? 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-300'
                    : 'hover:bg-indigo-50'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <KeyRound className="w-5 h-5 mr-2 text-slate-700" />
                <span className="text-slate-800">Change Password</span>
              </Link>
              <button
                type="button"
                onClick={() => {
                  handleLogout();
                  setMobileMenuOpen(false);
                }}
                className="w-full flex items-center px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg"
              >
                <LogOut className="w-5 h-5 mr-2" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};

