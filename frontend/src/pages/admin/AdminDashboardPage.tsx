// src/pages/admin/AdminDashboardPage.tsx
import React from 'react';
import { Navbar } from '@/components/common/Navbar';
import { AdminDashboard } from '@/components/admin/Dashboard';

export const AdminDashboardPage: React.FC = () => {
  return (
    <>
      <Navbar />
      <AdminDashboard />
    </>
  );
};

export default AdminDashboardPage;