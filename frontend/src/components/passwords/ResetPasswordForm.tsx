// src/components/passwords/ResetPasswordForm.tsx
import React, { useEffect, useState } from "react";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";
import { KeyRound, Eye, EyeOff, Shield } from "lucide-react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { type AppDispatch, type RootState } from "@/app/store";
import { resetPassword, clearError } from "@/store/authSlice";

const schema = yup.object().shape({
  new_password1: yup
    .string()
    .min(8, "Password must be at least 8 characters")
    .required("Password is required"),
  new_password2: yup
    .string()
    .oneOf([yup.ref("new_password1")], "Passwords must match")
    .required("Password confirmation is required"),
});

type ResetPasswordFormData = yup.InferType<typeof schema>;

export const ResetPasswordForm: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const { token } = useParams<{ token: string }>();
  const hasToken = Boolean(token?.trim());
  const navigate = useNavigate();
  const dispatch: AppDispatch = useDispatch();
  const { loading, error } = useSelector((state: RootState) => state.auth);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({ resolver: yupResolver(schema) });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);
  useEffect(() => {
    if (error) toast.error(error, { toastId: `reset-password-${error}` });
  }, [error]);
  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ResetPasswordFormData> = async (data) => {
    if (loading || !hasToken || !token) return;
    try {
      await dispatch(resetPassword({ token, ...data })).unwrap();
      toast.success(
        "Your password has been reset successfully! Please sign in.",
      );
      dispatch(clearError());
      navigate("/login", { replace: true });
    } catch {
      // Error toast handled by effect observing error state.
    }
  };

  const inputClass = (hasError: boolean) =>
    `w-full bg-gray-50 border text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200 pr-10 ${
      hasError ? "border-red-400 bg-red-50" : "border-gray-200"
    }`;

  if (!hasToken) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-3xl border border-gray-100 bg-white shadow-2xl p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className="bg-amber-50 rounded-2xl p-4">
              <KeyRound className="mx-auto h-10 w-10 text-amber-500" />
            </div>
          </div>
          <h1 className="mt-2 text-2xl font-extrabold text-gray-900">
            Invalid reset link
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            This password reset link is missing a token or is malformed.
          </p>
          <div className="mt-6 flex flex-col gap-3">
            <Link
              to="/forgot-password"
              className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-all hover:scale-[1.02]"
            >
              Request a new link
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
                Set a new password
              </h2>
              <p className="mt-4 text-lg text-indigo-100">
                Choose a strong, unique password to keep your account secure.
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
              <KeyRound className="w-8 h-8 text-indigo-600" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-center text-gray-900 tracking-tight">
            Set New Password
          </h1>
          <p className="text-center text-gray-500 mt-2 mb-8">
            Choose a new strong password for your account.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="space-y-2">
              <Label
                htmlFor="new_password1"
                className="text-gray-700 font-medium text-sm"
              >
                New Password
              </Label>
              <div className="relative">
                <Input
                  {...register("new_password1")}
                  id="new_password1"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  disabled={loading}
                  aria-invalid={Boolean(errors.new_password1)}
                  className={inputClass(Boolean(errors.new_password1))}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={loading}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.new_password1 && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.new_password1.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="new_password2"
                className="text-gray-700 font-medium text-sm"
              >
                Confirm New Password
              </Label>
              <div className="relative">
                <Input
                  {...register("new_password2")}
                  id="new_password2"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  disabled={loading}
                  aria-invalid={Boolean(errors.new_password2)}
                  className={inputClass(Boolean(errors.new_password2))}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  disabled={loading}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
                  aria-label={
                    showConfirmPassword ? "Hide password" : "Show password"
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.new_password2 && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.new_password2.message}
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
                  Resetting...
                </span>
              ) : (
                "Reset Password"
              )}
            </Button>
          </form>

          <div className="text-center text-sm text-gray-500 mt-8">
            Remember your password?{" "}
            <Link
              to="/login"
              className="font-semibold text-indigo-600 hover:underline"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
