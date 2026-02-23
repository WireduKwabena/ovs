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
import { KeyRound, Eye, EyeOff } from "lucide-react";
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
  } = useForm<ResetPasswordFormData>({
    resolver: yupResolver(schema),
  });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  useEffect(() => {
    if (error) {
      toast.error(error, { toastId: `reset-password-${error}` });
    }
  }, [error]);

  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ResetPasswordFormData> = async (data) => {
    if (loading) {
      return;
    }

    if (!hasToken || !token) {
      toast.error("No reset token found. Please use the link from your email.");
      return;
    }

    try {
      await dispatch(resetPassword({ token, ...data })).unwrap();
      toast.success(
        "Your password has been reset successfully! Please sign in."
      );
      dispatch(clearError());
      navigate("/login", { replace: true });
    } catch {
      // Error toast is handled by the effect observing store error state.
    }
  };

  if (!hasToken) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl border border-gray-700 bg-gray-800 p-8 text-center">
          <KeyRound className="mx-auto h-14 w-14 text-amber-400" />
          <h1 className="mt-4 text-2xl font-semibold">Invalid reset link</h1>
          <p className="mt-2 text-sm text-gray-400">
            This password reset link is missing a token or is malformed.
          </p>
          <div className="mt-6 flex flex-col gap-3">
            <Link
              to="/forgot-password"
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Request a new link
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-md border border-gray-600 px-4 py-2.5 text-sm font-medium text-gray-200 hover:bg-gray-700"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
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
                Set a strong, new password to keep your account secure.
              </p>
            </div>
            <div className="mt-auto text-sm text-gray-300">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        {/* Right Side: Form */}
        <div className="p-8 md:p-12 bg-gray-800">
          <div className="flex justify-center mb-6">
            <KeyRound className="h-16 w-16 text-blue-400" />
          </div>
          <h1 className="text-4xl font-bold text-center tracking-tighter">
            Set New Password
          </h1>
          <p className="text-center text-gray-400 mt-2 mb-8">
            Choose a new strong password for your account.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label
                htmlFor="new_password1"
                className="text-gray-300 font-medium"
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
                  aria-describedby={
                    errors.new_password1 ? "reset-password-error-new-password1" : undefined
                  }
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${
                    errors.new_password1 ? "border-red-500" : ""
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={loading}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
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
                <p id="reset-password-error-new-password1" className="text-sm text-red-400 mt-1">
                  {errors.new_password1.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="new_password2"
                className="text-gray-300 font-medium"
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
                  aria-describedby={
                    errors.new_password2 ? "reset-password-error-new-password2" : undefined
                  }
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${
                    errors.new_password2 ? "border-red-500" : ""
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  disabled={loading}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
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
                <p id="reset-password-error-new-password2" className="text-sm text-red-400 mt-1">
                  {errors.new_password2.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg rounded-lg py-3 transition-transform duration-200 active:scale-95"
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

          <div className="text-center text-sm text-gray-400 mt-8">
            Remember your password?{" "}
            <Link
              to="/login"
              className="font-medium text-blue-400 hover:underline"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
