// src/components/passwords/ForgotPasswordForm.tsx
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";
import { Mail, Shield } from "lucide-react";
import { Link } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { type AppDispatch, type RootState } from "@/app/store";
import {
  clearError,
  requestPasswordReset,
  resetPasswordStatus,
} from "@/store/authSlice";

const schema = yup.object().shape({
  email: yup
    .string()
    .email("Invalid email format")
    .required("Email is required"),
});

type ForgotPasswordFormData = { email: string };

export const ForgotPasswordForm: React.FC = () => {
  const dispatch: AppDispatch = useDispatch();
  const { loading, error, passwordResetEmailSent } = useSelector(
    (state: RootState) => state.auth,
  );
  const [requestedEmail, setRequestedEmail] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: yupResolver(schema),
    defaultValues: { email: "" },
  });

  useEffect(() => {
    dispatch(clearError());
    dispatch(resetPasswordStatus());
  }, [dispatch]);

  useEffect(() => {
    if (error) toast.error(error, { toastId: `forgot-password-${error}` });
  }, [error]);

  useEffect(() => {
    return () => {
      dispatch(resetPasswordStatus());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ForgotPasswordFormData> = async (data) => {
    if (loading) return;
    const email = data.email.trim();
    setRequestedEmail(email);
    await dispatch(requestPasswordReset({ email }));
  };

  const handleSendAnotherLink = useCallback(() => {
    dispatch(resetPasswordStatus());
    dispatch(clearError());
    reset({ email: requestedEmail });
  }, [dispatch, requestedEmail, reset]);

  const maskedRequestedEmail = useMemo(() => {
    const email = requestedEmail.trim();
    if (!email.includes("@")) return "";
    const [localPart, domain] = email.split("@");
    if (!localPart || !domain) return "";
    const safeLocalPart =
      localPart.length <= 2
        ? `${localPart[0] || ""}*`
        : `${localPart.slice(0, 2)}${"*".repeat(Math.max(localPart.length - 2, 2))}`;
    return `${safeLocalPart}@${domain}`;
  }, [requestedEmail]);

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
                Secure password recovery
              </h2>
              <p className="mt-4 text-lg text-indigo-100">
                We'll send a secure reset link directly to your email address.
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
              <Mail className="w-8 h-8 text-indigo-600" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-center text-gray-900 tracking-tight">
            Forgot Password?
          </h1>

          {passwordResetEmailSent ? (
            <div className="text-center py-8">
              <div className="bg-green-50 border border-green-100 rounded-2xl p-6 mt-4">
                <h3 className="text-xl font-bold text-gray-900">
                  Check your inbox
                </h3>
                <p className="text-gray-500 mt-2 text-sm">
                  A password reset link has been sent to your email. Please
                  follow the link to reset your password.
                </p>
                {maskedRequestedEmail && (
                  <p className="text-sm font-semibold text-indigo-600 mt-3">
                    Sent to: {maskedRequestedEmail}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-3 mt-6">
                <button
                  type="button"
                  onClick={handleSendAnotherLink}
                  className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-medium border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Send another link
                </button>
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center px-6 py-3 rounded-xl text-base font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-all hover:scale-[1.02] active:scale-95 shadow-md"
                >
                  Back to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <>
              <p className="text-center text-gray-500 mt-2 mb-8">
                Enter your email and we&apos;ll send you a reset link.
              </p>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                <div className="space-y-2">
                  <Label
                    htmlFor="email"
                    className="text-gray-700 font-medium text-sm"
                  >
                    Email Address
                  </Label>
                  <Input
                    {...register("email")}
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    disabled={loading}
                    aria-invalid={Boolean(errors.email)}
                    className={`w-full bg-gray-50 border text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200 ${
                      errors.email
                        ? "border-red-400 bg-red-50"
                        : "border-gray-200"
                    }`}
                  />
                  {errors.email && (
                    <p className="text-sm text-red-500 mt-1">
                      {errors.email.message}
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
                      Sending...
                    </span>
                  ) : (
                    "Send Reset Link"
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
            </>
          )}
        </div>
      </div>
    </div>
  );
};
