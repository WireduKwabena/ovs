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
import { Mail } from "lucide-react";
import { Link } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { type AppDispatch, type RootState } from "@/app/store";
import { clearError, requestPasswordReset, resetPasswordStatus } from "@/store/authSlice";

const schema = yup.object().shape({
  email: yup
    .string()
    .email("Invalid email format")
    .required("Email is required"),
});

type ForgotPasswordFormData = {
  email: string;
};

export const ForgotPasswordForm: React.FC = () => {
  const dispatch: AppDispatch = useDispatch();
  const { loading, error, passwordResetEmailSent } = useSelector(
    (state: RootState) => state.auth
  );
  const [requestedEmail, setRequestedEmail] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: yupResolver(schema),
    defaultValues: {
      email: "",
    },
  });

  useEffect(() => {
    dispatch(clearError());
    dispatch(resetPasswordStatus());
  }, [dispatch]);

  useEffect(() => {
    if (error) {
      toast.error(error, { toastId: `forgot-password-${error}` });
    }
  }, [error]);

  useEffect(() => {
    // Reset status when the component unmounts
    return () => {
      dispatch(resetPasswordStatus());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ForgotPasswordFormData> = async (data) => {
    if (loading) {
      return;
    }

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
    if (!email.includes("@")) {
      return "";
    }

    const [localPart, domain] = email.split("@");
    if (!localPart || !domain) {
      return "";
    }

    const safeLocalPart =
      localPart.length <= 2
        ? `${localPart[0] || ""}*`
        : `${localPart.slice(0, 2)}${"*".repeat(Math.max(localPart.length - 2, 2))}`;
    return `${safeLocalPart}@${domain}`;
  }, [requestedEmail]);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-4xl mx-auto lg:grid lg:grid-cols-2 rounded-3xl shadow-2xl overflow-hidden bg-gray-800 border border-gray-700">
        {/* Left Side: Decorative */}
        <div className="relative hidden lg:block overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-600 to-blue-500"></div>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-lg border-r border-white/20"></div>
          <div className="relative z-10 flex flex-col justify-between h-full p-12">
            <div>
              <h2 className="text-4xl font-bold tracking-tighter text-white">
                Online Vetting System
              </h2>
              <p className="mt-4 text-lg text-gray-200">
                Secure password recovery for your account.
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
            <Mail className="h-16 w-16 text-blue-400" />
          </div>
          <h1 className="text-4xl font-bold text-center tracking-tighter">
            Forgot Password?
          </h1>
          {passwordResetEmailSent ? (
            <div className="text-center text-white py-8">
              <h3 className="text-2xl font-semibold">Check your inbox</h3>
              <p className="text-gray-400 mt-2">
                A password reset link has been sent to your email address.
                Please follow the link to reset your password.
              </p>
              {maskedRequestedEmail && (
                <p className="text-sm text-blue-300 mt-3">
                  Sent to: {maskedRequestedEmail}
                </p>
              )}
              <button
                type="button"
                onClick={handleSendAnotherLink}
                className="mt-4 inline-flex items-center px-4 py-2 rounded-md text-sm font-medium bg-gray-700 hover:bg-gray-600 transition-colors"
              >
                Send another link
              </button>
              <Link
                to="/login"
                className="mt-6 inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-transform duration-200 active:scale-95"
              >
                Back to Sign In
              </Link>
            </div>
          ) : (
            <>
              <p className="text-center text-gray-400 mt-2 mb-8">
                Enter your email and we&apos;ll send you a reset link.
              </p>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-gray-300 font-medium">
                    Email Address
                  </Label>
                  <Input
                    {...register("email")}
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    disabled={loading}
                    aria-invalid={Boolean(errors.email)}
                    aria-describedby={errors.email ? "forgot-password-email-error" : undefined}
                    className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${
                      errors.email ? "border-red-500" : ""
                    }`}
                  />
                  {errors.email && (
                    <p id="forgot-password-email-error" className="text-sm text-red-400 mt-1">
                      {errors.email.message}
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
                      Sending...
                    </span>
                  ) : (
                    "Send Reset Link"
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
            </>
          )}
        </div>
      </div>
    </div>
  );
};
