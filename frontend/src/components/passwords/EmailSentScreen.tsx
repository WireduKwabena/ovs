// src/components/passwords/EmailSentScreen.tsx
import React, { useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/common/Loader";
import { MailCheck } from "lucide-react";
import { authService } from "@/services/auth.service";

export const EmailSentScreen: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const location = useLocation();
  const email = location.state?.email || "";

  const handleResend = async () => {
    if (!email) {
      toast.error("No email address found. Please go back and try again.");
      return;
    }
    setLoading(true);
    try {
      await authService.requestPasswordReset(email);
      toast.success(
        "A new password reset link has been sent to your email address."
      );
    } catch (error) {
      const err = error as Error;
      toast.error(
        err.message || "An unexpected error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto rounded-3xl shadow-2xl overflow-hidden border border-gray-700 bg-gray-800/50 backdrop-blur-sm">
        <div className="p-8 md:p-12 text-center">
          <div className="flex justify-center mb-6">
            <MailCheck className="h-16 w-16 text-green-400" />
          </div>
          <h1 className="text-4xl font-bold tracking-tighter">
            Check Your Email
          </h1>
          <p className="text-gray-300 mt-4">
            We've sent a password reset link to{" "}
            <span className="font-semibold text-blue-400">{email}</span>.
          </p>
          <p className="text-gray-400 mt-2">
            Please follow the instructions in the email to reset your password.
          </p>

          <div className="mt-8">
            <Button
              onClick={handleResend}
              size="lg"
              className="w-full max-w-xs mx-auto bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg rounded-lg py-3 transition-transform duration-200 active:scale-95"
              disabled={loading}
            >
              {loading ? <Loader size="sm" /> : "Resend Email"}
            </Button>
          </div>

          <div className="text-center text-sm text-gray-400 mt-8">
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
