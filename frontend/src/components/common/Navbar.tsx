// src/components/common/Navbar.tsx (Fixed - Type-Safe User Display)
import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, LogOut, Menu, X, ChevronDown, KeyRound, Settings2, Shield, ShieldCheck } from 'lucide-react';
import { Button } from '../ui/button';
import type { AppDispatch, RootState } from '@/app/store';
import { useDispatch, useSelector } from 'react-redux';
import { fetchNotifications } from '@/store/notificationSlice';
import type { User } from '@/types';
import { createSelector } from '@reduxjs/toolkit';
import { useAuth } from '@/hooks/useAuth';
import { getUserDisplayName, getUserInitial } from '@/utils/userDisplay';

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
  })
);

const selectUnreadCount = createSelector(
  [selectNotificationsState],
  (notifications) => notifications.unreadCount || 0
);

export const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileMenuMounted, setMobileMenuMounted] = useState(false);
  const [adminMoreMenuOpen, setAdminMoreMenuOpen] = useState(false);
  const dispatch = useDispatch<AppDispatch>();

  
  // ✅ Line 14 should be around here - use memoized selectors
  const { user, isAuthenticated, userType } = useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const adminMoreMenuRef = useRef<HTMLDivElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchNotifications());
    }
  }, [dispatch, isAuthenticated]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
      if (adminMoreMenuRef.current && !adminMoreMenuRef.current.contains(event.target as Node)) {
        setAdminMoreMenuOpen(false);
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

  const roleLabel = userType === 'admin' ? 'Admin' : userType === 'hr_manager' ? 'HR Manager' : userType === 'applicant' ? 'Applicant' : 'User';
  const canManageTwoFactor = userType !== 'applicant';
  const navLinks =
    userType === 'admin'
      ? [
          { to: '/admin/dashboard', label: 'Dashboard' },
          { to: '/admin/cases', label: 'Cases' },
          { to: '/admin/users', label: 'Users' },
          { to: '/admin/rubrics', label: 'Rubrics' },
          { to: '/video-calls', label: 'Video Calls' },
          { to: '/admin/control-center', label: 'Admin Control' },
          { to: '/fraud-insights', label: 'Fraud' },
          { to: '/background-checks', label: 'Checks' },
          { to: '/audit-logs', label: 'Audit' },
          { to: '/ml-monitoring', label: 'ML Ops' },
          { to: '/ai-monitor', label: 'AI Monitor' },
          { to: '/admin/analytics', label: 'Analytics' },
        ]
      : userType === 'applicant'
        ? [
            { to: '/dashboard', label: 'Dashboard' },
            { to: '/applications', label: 'Applications' },
            { to: '/video-calls', label: 'Video Calls' },
          ]
        : [
            { to: '/dashboard', label: 'Dashboard' },
            { to: '/campaigns', label: 'Campaigns' },
            { to: '/applications', label: 'Cases' },
            { to: '/video-calls', label: 'Video Calls' },
            { to: '/fraud-insights', label: 'Fraud' },
            { to: '/background-checks', label: 'Checks' },
            { to: '/audit-logs', label: 'Audit' },
            { to: '/ai-monitor', label: 'AI Monitor' },
          ];

  const desktopPrimaryLinks =
    userType === 'admin'
      ? [
          { to: '/admin/dashboard', label: 'Dashboard' },
          { to: '/admin/cases', label: 'Cases' },
          { to: '/admin/users', label: 'Users' },
          { to: '/admin/rubrics', label: 'Rubrics' },
          { to: '/video-calls', label: 'Video Calls' },
        ]
      : navLinks;

  const desktopOverflowLinks =
    userType === 'admin'
      ? [
          { to: '/admin/control-center', label: 'Admin Control' },
          { to: '/fraud-insights', label: 'Fraud' },
          { to: '/background-checks', label: 'Checks' },
          { to: '/audit-logs', label: 'Audit' },
          { to: '/ml-monitoring', label: 'ML Ops' },
          { to: '/ai-monitor', label: 'AI Monitor' },
          { to: '/admin/analytics', label: 'Analytics' },
        ]
      : [];
  
  const initial = getUserInitial(user, '?');

  const profile_picture_url = userType === 'applicant' ? (user as User)?.profile_picture_url:'';

  return (
    <nav className="bg-slate-50 border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to={userType === 'admin' ? '/admin/dashboard' : '/dashboard'} className="flex items-center">
              <div className="flex items-center">
              <Shield className="h-7 w-7 text-indigo-600 sm:h-8 sm:w-8" />
              <span className="ml-2 text-lg leading-none font-bold text-gray-900 sm:text-xl xl:text-2xl">
                <span className="sm:hidden">OVS</span>
                <span className="hidden sm:inline">VettingSystem</span>
              </span>
            </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden xl:flex items-center space-x-4">
            {desktopPrimaryLinks.map((navItem) => (
              <Link
                key={navItem.to}
                to={navItem.to}
                className="text-sm font-semibold text-slate-800 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded"
              >
                {navItem.label}
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
                  }}
                  className="inline-flex items-center gap-1 text-sm font-semibold text-slate-800 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded"
                >
                  More
                  <ChevronDown className="w-4 h-4 text-slate-600" />
                </Button>
                {adminMoreMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-20 border">
                    {desktopOverflowLinks.map((navItem) => (
                      <Link
                        key={navItem.to}
                        to={navItem.to}
                        className="block px-4 py-2 text-sm font-medium text-slate-800 hover:bg-indigo-50 hover:text-indigo-700"
                        onClick={() => setAdminMoreMenuOpen(false)}
                      >
                        {navItem.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
            <Link
              to="/notifications"
              className="relative p-2 text-slate-800 hover:text-indigo-700 hover:bg-indigo-50 rounded-lg"
            >
              <Bell className="w-6 h-6" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                  {unreadCount}
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
                  <p className="text-xs text-slate-600">{roleLabel}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-600" />
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
                <p className="text-sm text-slate-600">{roleLabel}</p>
              </div>
            </div>
            <div className="space-y-3">
              {navLinks.map((navItem) => (
                <Link
                  key={navItem.to}
                  to={navItem.to}
                  className="flex items-center px-3 py-2 rounded-lg hover:bg-indigo-50 text-slate-800"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {navItem.label}
                </Link>
              ))}
              <Link
                to="/notifications"
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-indigo-50"
                onClick={() => setMobileMenuOpen(false)}
              >
                <span className="text-slate-800">Notifications</span>
                {unreadCount > 0 && (
                  <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded-full">
                    {unreadCount}
                  </span>
                )}
              </Link>
              {canManageTwoFactor && (
                <Link
                  to="/security"
                  className="flex items-center px-3 py-2 rounded-lg hover:bg-indigo-50"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <ShieldCheck className="w-5 h-5 mr-2 text-slate-700" />
                  <span className="text-slate-800">Security</span>
                </Link>
              )}
              <Link
                to="/settings"
                className="flex items-center px-3 py-2 rounded-lg hover:bg-indigo-50"
                onClick={() => setMobileMenuOpen(false)}
              >
                <Settings2 className="w-5 h-5 mr-2 text-slate-700" />
                <span className="text-slate-800">Profile & Settings</span>
              </Link>
              <Link
                to="/change-password"
                className="flex items-center px-3 py-2 rounded-lg hover:bg-indigo-50"
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
