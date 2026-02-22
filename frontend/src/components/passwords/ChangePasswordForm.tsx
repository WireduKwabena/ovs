// src/components/passwords/ChangePasswordForm.tsx
import React, { useState, useEffect } from 'react';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { toast } from 'react-toastify';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader } from '@/components/common/Loader';
import { LockKeyhole, Eye, EyeOff } from 'lucide-react';
import { useDispatch, useSelector } from 'react-redux';
import { type AppDispatch, type RootState } from '@/app/store';
import { changePassword, clearError } from '@/store/authSlice';
import { unwrapResult } from '@reduxjs/toolkit';

const schema = yup.object().shape({
  old_password: yup.string().required('Old password is required'),
  new_password: yup.string().min(8, 'New password must be at least 8 characters').required('New password is required'),
  new_password_confirm: yup
    .string()
    .oneOf([yup.ref('new_password')], 'Passwords must match')
    .required('Password confirmation is required'),
});

type ChangePasswordFormData = yup.InferType<typeof schema>;

export const ChangePasswordForm: React.FC = () => {
    const dispatch: AppDispatch = useDispatch();
    const { loading, error } = useSelector((state: RootState) => state.auth);
    const [showOldPassword, setShowOldPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ChangePasswordFormData>({
    resolver: yupResolver(schema),
  });

  useEffect(() => {
    if (error) {
      toast.error(error);
    }
    // Clear the error when the component unmounts
    return () => {
        dispatch(clearError());
    }
  }, [error, dispatch]);

  const onSubmit: SubmitHandler<ChangePasswordFormData> = async (data) => {
    try {
        const actionResult = await dispatch(changePassword(data));
        unwrapResult(actionResult);
        toast.success('Your password has been changed successfully!');
        reset();
      } catch (err) {
        // Error toast is handled by the useEffect hook
      }
  };

  return (
    <div className="min-h-screen bg-transparent text-white flex items-center justify-center p-4">
      <div className="w-full max-w-4xl mx-auto lg:grid lg:grid-cols-2 rounded-3xl shadow-2xl overflow-hidden bg-gray-800 border border-gray-700">
        {/* Left Side: Decorative */}
        <div className="relative hidden lg:block overflow-hidden">
          <div className="absolute inset-0 bg-linear-to-br from-purple-600 to-blue-500"></div>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-lg border-r border-white/20"></div>
          <div className="relative z-10 flex flex-col justify-between h-full p-12">
            <div>
              <h2 className="text-4xl font-bold tracking-tighter text-white">
                Online Vetting System
              </h2>
              <p className="mt-4 text-lg text-gray-200">
                Keep your account secure by using a strong and unique password.
              </p>
            </div>
            <div className="mt-auto text-sm text-gray-300">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        {/* Right Side: Form */}
        <div className="p-8 md:p-12 bg-gray-800">
          <div className="flex flex-col items-center text-center mb-8">
            <div className="p-4 bg-linear-to-br from-purple-600 to-blue-500 rounded-full mb-4">
              <LockKeyhole className="h-12 w-12 text-white" />
            </div>
            <h1 className="text-4xl font-bold tracking-tighter">Change Your Password</h1>
            <p className="text-gray-400 mt-2">
              For your security, choose a strong and unique password.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="old_password" className="text-gray-300 font-medium">Current Password</Label>
              <div className="relative">
                <Input
                  {...register('old_password')}
                  id="old_password"
                  type={showOldPassword ? 'text' : 'password'}
                  placeholder="Enter your current password"
                  className={`w-full bg-gray-700 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.old_password ? 'border-red-500' : ''}`}
                />
                <button
                  type="button"
                  onClick={() => setShowOldPassword(!showOldPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200"
                  aria-label={showOldPassword ? 'Hide password' : 'Show password'}
                >
                  {showOldPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.old_password && (
                <p className="text-sm text-red-400 mt-1">{errors.old_password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password" className="text-gray-300 font-medium">New Password</Label>
              <div className="relative">
                <Input
                  {...register('new_password')}
                  id="new_password"
                  type={showNewPassword ? 'text' : 'password'}
                  placeholder="Enter a new strong password"
                  className={`w-full bg-gray-700 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.new_password ? 'border-red-500' : ''}`}
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200"
                  aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                >
                  {showNewPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.new_password && (
                <p className="text-sm text-red-400 mt-1">{errors.new_password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password_confirm" className="text-gray-300 font-medium">Confirm New Password</Label>
              <div className="relative">
                <Input
                  {...register('new_password_confirm')}
                  id="new_password_confirm"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Confirm your new password"
                  className={`w-full bg-gray-700 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.new_password_confirm ? 'border-red-500' : ''}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200"
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.new_password_confirm && (
                <p className="text-sm text-red-400 mt-1">{errors.new_password_confirm.message}</p>
              )}
            </div>
            <Button type="submit" size="lg" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg rounded-lg py-3 transition-transform duration-200 active:scale-95" disabled={loading}>
              {loading ? (
                <Loader size="sm" />
              ) : (
                'Update Password'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};
