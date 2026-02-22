// src/pages/NotificationsPage.tsx (Safe version)
import React, { useMemo } from 'react';
import { useNotifications } from '@/hooks/useNotifications';
import { Loader } from '@/components/common/Loader';
import { Navbar } from '@/components/common/Navbar';

export const NotificationsPage: React.FC = () => {
  const { notifications, isLoading, markAsRead, markAllAsRead } = useNotifications();

  // ✅ Debug log
  console.log('NotificationsPage - notifications:', notifications);
  console.log('NotificationsPage - isLoading:', isLoading);
  console.log('NotificationsPage - is array?', Array.isArray(notifications));

  // ✅ Safety check - ensure we have an array
  const notificationsArray = useMemo(() => {
    if (!notifications) return [];
    return Array.isArray(notifications) ? notifications : [];
  }, [notifications]);

  // ✅ Filter with safe array
  const unreadNotifications = useMemo(() => {
    return notificationsArray.filter(n => n.status === 'unread' || !n.is_read);
  }, [notificationsArray]);

  const readNotifications = useMemo(() => {
    return notificationsArray.filter(n => n.status === 'read' && n.is_read);
  }, [notificationsArray]);

  if (isLoading && notificationsArray.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          {unreadNotifications.length > 0 && (
            <button
              onClick={() => markAllAsRead()}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Mark All as Read
            </button>
          )}
        </div>

        {/* Unread Notifications */}
        {unreadNotifications.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Unread ({unreadNotifications.length})
            </h2>
            <div className="space-y-4">
              {unreadNotifications.map((notification) => (
                <div
                  key={notification.id}
                  className="bg-blue-50 border-l-4 border-blue-500 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900">{notification.title}</h3>
                      <p className="text-gray-700 mt-1">{notification.message}</p>
                      <p className="text-sm text-gray-500 mt-2">
                        {new Date(notification.created_at).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => markAsRead([notification.id])}
                      className="ml-4 px-3 py-1 text-sm bg-white text-blue-600 rounded hover:bg-blue-100"
                    >
                      Mark as Read
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Read Notifications */}
        {readNotifications.length > 0 && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Read ({readNotifications.length})
            </h2>
            <div className="space-y-4">
              {readNotifications.map((notification) => (
                <div
                  key={notification.id}
                  className="bg-white border border-gray-200 rounded-lg p-4 opacity-75"
                >
                  <h3 className="font-semibold text-gray-900">{notification.title}</h3>
                  <p className="text-gray-700 mt-1">{notification.message}</p>
                  <p className="text-sm text-gray-500 mt-2">
                    {new Date(notification.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {notificationsArray.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No notifications yet</p>
          </div>
        )}
      </div>
    </div>
  );
};