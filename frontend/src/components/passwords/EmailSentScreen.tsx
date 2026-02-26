// src/components/passwords/EmailSentScreen.tsx
import React, { useMemo, useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/common/Loader";
import { MailCheck, ArrowLeft } from "lucide-react";
import { authService } from "@/services/auth.service";

export const EmailSentScreen: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const location = useLocation();
  const email = location.state?.email || "";
  const hasEmail = Boolean(email.trim());

  const maskedEmail = useMemo(() => {
    if (!hasEmail || !email.includes("@")) return "";
    const [localPart, domain] = email.split("@");
    if (!localPart || !domain) return "";
    const safeLocalPart =
      localPart.length <= 2
        ? `${localPart[0] || ""}*`
        : `${localPart.slice(0, 2)}${"*".repeat(Math.max(localPart.length - 2, 2))}`;
    return `${safeLocalPart}@${domain}`;
  }, [email, hasEmail]);

  const handleResend = async () => {
    if (!hasEmail) {
      toast.error("No email address found. Please go back and try again.");
      return;
    }
    if (loading) return;
    setLoading(true);
    try {
      await authService.requestPasswordReset(email);
      toast.success(
        "A new password reset link has been sent to your email address.",
      );
    } catch (error) {
      const err = error as Error;
      toast.error(
        err.message || "An unexpected error occurred. Please try again.",
        {
          toastId: "email-sent-resend-error",
        },
      );
    } finally {
      setLoading(false);
    }
  };

  if (!hasEmail) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-3xl border border-gray-100 bg-white shadow-2xl p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className="bg-amber-50 rounded-2xl p-4">
              <MailCheck className="mx-auto h-10 w-10 text-amber-500" />
            </div>
          </div>
          <h1 className="mt-2 text-2xl font-extrabold text-gray-900">
            Email context missing
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            This page was opened without an email context. Request another
            password reset link to continue.
          </p>
          <div className="mt-6 flex flex-col gap-3">
            <Link
              to="/forgot-password"
              className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-all hover:scale-[1.02]"
            >
              Request reset link
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
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-green-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse delay-1000 pointer-events-none" />

      <div className="relative w-full max-w-lg mx-auto rounded-3xl shadow-2xl overflow-hidden bg-white border border-gray-100">
        <div className="p-8 md:p-12 text-center">
          {/* Success icon */}
          <div className="flex justify-center mb-6">
            <div className="bg-green-50 rounded-full p-5 ring-8 ring-green-50">
              <MailCheck className="h-12 w-12 text-green-500" />
            </div>
          </div>

          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
            Check Your Email
          </h1>
          <p className="text-gray-500 mt-4">
            We&apos;ve sent a password reset link to{" "}
            <span className="font-semibold text-indigo-600">{maskedEmail}</span>
            .
          </p>
          <p className="text-gray-400 mt-2 text-sm">
            Please follow the instructions in the email to reset your password.
            If you don&apos;t see it, check your spam folder.
          </p>

          <div className="mt-8 space-y-3">
            <Button
              onClick={handleResend}
              size="lg"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-base rounded-xl py-3 transition-all duration-200 hover:scale-[1.02] active:scale-95 shadow-md hover:shadow-indigo-200"
              disabled={loading}
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader size="sm" color="white" />
                  Resending...
                </span>
              ) : (
                "Resend Email"
              )}
            </Button>

            <Link
              to="/login"
              className="inline-flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
