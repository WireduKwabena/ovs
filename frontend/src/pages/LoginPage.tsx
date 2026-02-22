// src/pages/LoginPage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LoginForm } from '@/components/auth/LoginForm';
import { useAuth } from '@/hooks/useAuth';
import { Loader } from '@/components/common/Loader';

export const LoginPage: React.FC = () => {
  const { isAuthenticated, userType, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      if (userType === 'admin') {
        navigate('/admin/dashboard', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    }
  }, [isAuthenticated, userType, navigate]);

  // While the auth state is loading, show a full-screen loader
  // to prevent showing the login form to an already authenticated user.
  if (loading || isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader size="lg" />
      </div>
    );
  }

  return <LoginForm />;
};

export default LoginPage;