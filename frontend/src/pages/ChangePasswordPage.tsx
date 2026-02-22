// src/pages/ChangePasswordPage.tsx
import React from 'react';
import { ChangePasswordForm } from '@/components/passwords/ChangePasswordForm';
import { Navbar } from '@/components/common/Navbar';

const ChangePasswordPage: React.FC = () => {
  return (
    <div className="container mx-auto p-4">
      <Navbar />
      <ChangePasswordForm />
    </div>
  );
};

export default ChangePasswordPage;
