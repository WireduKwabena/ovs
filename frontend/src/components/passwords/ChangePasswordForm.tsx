// src/components/passwords/ChangePasswordForm.tsx
import React, { useState, useEffect } from "react";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";
import { LockKeyhole, Eye, EyeOff, Shield } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { type AppDispatch, type RootState } from "@/app/store";
import { changePassword, clearError } from "@/store/authSlice";

const schema = yup.object().shape({
  old_password: yup.string().required("Old password is required"),
  new_password: yup
    .string()
    .min(8, "New password must be at least 8 characters")
    .required("New password is required"),
  new_password_confirm: yup
    .string()
    .oneOf([yup.ref("new_password")], "Passwords must match")
    .required("Password confirmation is required"),
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
  } = useForm<ChangePasswordFormData>({ resolver: yupResolver(schema) });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);
  useEffect(() => {
    if (error) toast.error(error, { toastId: `change-password-${error}` });
  }, [error]);
  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ChangePasswordFormData> = async (data) => {
    if (loading) return;
    try {
      await dispatch(changePassword(data)).unwrap();
      toast.success("Your password has been changed successfully!");
      dispatch(clearError());
      reset();
    } catch {
      // Error toast is handled by the effect that observes auth error state.
    }
  };

  const inputClass = (hasError: boolean) =>
    `w-full bg-gray-50 border text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200 pr-10 ${
      hasError ? "border-red-400 bg-red-50" : "border-gray-200"
    }`;

  const PasswordToggle = ({
    show,
    onToggle,
    disabled,
  }: {
    show: boolean;
    onToggle: () => void;
    disabled: boolean;
  }) => (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
      aria-label={show ? "Hide password" : "Show password"}
    >
      {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
    </button>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse delay-1000 pointer-events-none" />

      <div className="relative w-full max-w-4xl mx-auto lg:grid lg:grid-cols-2 rounded-3xl shadow-2xl overflow-hidden bg-white border border-gray-100">
        {/* Left decorative panel */}
        <div className="relative hidden lg:flex flex-col bg-indigo-600 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-purple-600" />
          <div className="absolute top-0 left-0 w-64 h-64 bg-white/10 rounded-full -translate-x-1/2 -translate-y-1/2" />
          <div className="absolute bottom-0 right-0 w-80 h-80 bg-white/10 rounded-full translate-x-1/2 translate-y-1/2" />
          <div className="relative z-10 flex flex-col justify-between h-full p-12">
            <div className="flex items-center gap-3">
              <div className="bg-white/20 rounded-lg p-2">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold text-white">
                VettingSystem
              </span>
            </div>
            <div>
              <h2 className="text-4xl font-extrabold tracking-tight text-white leading-tight">
                Keep your account secure
              </h2>
              <p className="mt-4 text-lg text-indigo-100">
                Use a strong, unique password to protect your firm account from
                unauthorized access.
              </p>
            </div>
            <div className="text-sm text-indigo-200">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        {/* Right form panel */}
        <div className="p-8 md:p-12 bg-white">
          <div className="flex justify-center mb-6">
            <div className="bg-indigo-50 rounded-2xl p-4">
              <LockKeyhole className="w-8 h-8 text-indigo-600" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-center text-gray-900 tracking-tight">
            Change Your Password
          </h1>
          <p className="text-center text-gray-500 mt-2 mb-8">
            For your security, choose a strong and unique password.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Current Password */}
            <div className="space-y-2">
              <Label
                htmlFor="old_password"
                className="text-gray-700 font-medium text-sm"
              >
                Current Password
              </Label>
              <div className="relative">
                <Input
                  {...register("old_password")}
                  id="old_password"
                  type={showOldPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your current password"
                  disabled={loading}
                  aria-invalid={Boolean(errors.old_password)}
                  className={inputClass(Boolean(errors.old_password))}
                />
                <PasswordToggle
                  show={showOldPassword}
                  onToggle={() => setShowOldPassword(!showOldPassword)}
                  disabled={loading}
                />
              </div>
              {errors.old_password && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.old_password.message}
                </p>
              )}
            </div>

            {/* New Password */}
            <div className="space-y-2">
              <Label
                htmlFor="new_password"
                className="text-gray-700 font-medium text-sm"
              >
                New Password
              </Label>
              <div className="relative">
                <Input
                  {...register("new_password")}
                  id="new_password"
                  type={showNewPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Enter a new strong password"
                  disabled={loading}
                  aria-invalid={Boolean(errors.new_password)}
                  className={inputClass(Boolean(errors.new_password))}
                />
                <PasswordToggle
                  show={showNewPassword}
                  onToggle={() => setShowNewPassword(!showNewPassword)}
                  disabled={loading}
                />
              </div>
              {errors.new_password && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.new_password.message}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div className="space-y-2">
              <Label
                htmlFor="new_password_confirm"
                className="text-gray-700 font-medium text-sm"
              >
                Confirm New Password
              </Label>
              <div className="relative">
                <Input
                  {...register("new_password_confirm")}
                  id="new_password_confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Confirm your new password"
                  disabled={loading}
                  aria-invalid={Boolean(errors.new_password_confirm)}
                  className={inputClass(Boolean(errors.new_password_confirm))}
                />
                <PasswordToggle
                  show={showConfirmPassword}
                  onToggle={() => setShowConfirmPassword(!showConfirmPassword)}
                  disabled={loading}
                />
              </div>
              {errors.new_password_confirm && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.new_password_confirm.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-base rounded-xl py-3 transition-all duration-200 hover:scale-[1.02] active:scale-95 shadow-md hover:shadow-indigo-200"
              disabled={loading}
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader size="sm" color="white" />
                  Updating...
                </span>
              ) : (
                "Update Password"
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};
