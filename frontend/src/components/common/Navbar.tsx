// src/components/common/Navbar.tsx (Fixed - Type-Safe User Display)
import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, LogOut, Menu, X, ChevronDown, KeyRound, Shield, ShieldCheck } from 'lucide-react';
import { Button } from '../ui/button';
import type { AppDispatch, RootState } from '@/app/store';
import { useDispatch, useSelector } from 'react-redux';
import { fetchNotifications } from '@/store/notificationSlice';
import type { AdminUser, User } from '@/types';
import { createSelector } from '@reduxjs/toolkit';
import { useAuth } from '@/hooks/useAuth';

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
  const dispatch = useDispatch<AppDispatch>();

  
  // ✅ Line 14 should be around here - use memoized selectors
  const { user, isAuthenticated, userType } = useSelector(selectUserData);
  const unreadCount = useSelector(selectUnreadCount);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

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
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!isAuthenticated) return null;

  const displayName = userType === 'admin' 
    ? (user as AdminUser)?.username 
    : (user as User)?.full_name;

  const roleLabel = userType === 'admin' ? 'Admin' : userType === 'hr_manager' ? 'HR Manager' : userType === 'applicant' ? 'Applicant' : 'User';
  const canManageTwoFactor = userType !== 'applicant';
  const navLinks =
    userType === 'admin'
      ? [
          { to: '/admin/dashboard', label: 'Dashboard' },
          { to: '/admin/cases', label: 'Cases' },
          { to: '/admin/rubrics', label: 'Rubrics' },
          { to: '/admin/analytics', label: 'Analytics' },
        ]
      : userType === 'applicant'
        ? [
            { to: '/dashboard', label: 'Dashboard' },
            { to: '/applications', label: 'Applications' },
          ]
        : [
            { to: '/dashboard', label: 'Dashboard' },
            { to: '/campaigns', label: 'Campaigns' },
            { to: '/applications', label: 'Cases' },
          ];
  
  const initial = displayName?.charAt(0).toUpperCase() || '?';

  const profile_picture_url = userType === 'applicant' ? (user as User)?.profile_picture_url:'';

  return (
    <nav className="bg-white shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to={userType === 'admin' ? '/admin/dashboard' : '/dashboard'} className="flex items-center">
              <div className="flex items-center">
              <Shield className="w-8 h-8 text-indigo-600" />
              <span className="ml-2 text-2xl font-bold text-gray-900">VettingSystem</span>
            </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-4">
            {navLinks.map((navItem) => (
              <Link
                key={navItem.to}
                to={navItem.to}
                className="text-sm font-medium text-gray-600 hover:text-indigo-600 px-2 py-1 rounded"
              >
                {navItem.label}
              </Link>
            ))}
            <Link
              to="/notifications"
              className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
            >
              <Bell className="w-6 h-6" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </Link>

            <div className="relative" ref={profileMenuRef}>
              <button onClick={() => setProfileMenuOpen(!profileMenuOpen)} className="flex items-center space-x-2 ml-4 p-2 rounded-lg hover:bg-gray-100">
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
                  <p className="text-xs text-gray-500">{roleLabel}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </button>
              {profileMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg py-1 z-20 border">
                  {canManageTwoFactor && (
                    <Link
                      to="/security"
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      onClick={() => setProfileMenuOpen(false)}
                    >
                      <ShieldCheck className="w-4 h-4 mr-2" />
                      Security
                    </Link>
                  )}
                  <Link
                    to="/change-password"
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    onClick={() => setProfileMenuOpen(false)}
                  >
                    <KeyRound className="w-4 h-4 mr-2" />
                    Change Password
                  </Link>
                  <Button
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
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-gray-200">
          <div className="px-4 py-3 space-y-3">
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
                <p className="text-sm text-gray-500">{roleLabel}</p>
              </div>
            </div>
            {navLinks.map((navItem) => (
              <Link
                key={navItem.to}
                to={navItem.to}
                className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-100 text-gray-700"
                onClick={() => setMobileMenuOpen(false)}
              >
                {navItem.label}
              </Link>
            ))}
            <Link
              to="/notifications"
              className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-100"
              onClick={() => setMobileMenuOpen(false)}
            >
              <span className="text-gray-700">Notifications</span>
              {unreadCount > 0 && (
                <span className="bg-red-600 text-white text-xs font-bold px-2 py-1 rounded-full">
                  {unreadCount}
                </span>
              )}
            </Link>
            {canManageTwoFactor && (
              <Link
                to="/security"
                className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-100"
                onClick={() => setMobileMenuOpen(false)}
              >
                <ShieldCheck className="w-5 h-5 mr-2 text-gray-600" />
                <span className="text-gray-700">Security</span>
              </Link>
            )}
            <Link
              to="/change-password"
              className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-100"
              onClick={() => setMobileMenuOpen(false)}
            >
              <KeyRound className="w-5 h-5 mr-2 text-gray-600" />
              <span className="text-gray-700">Change Password</span>
            </Link>
            <button
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
      )}
    </nav>
  );
};

