import React, { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, MailCheck } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Loader } from "@/components/common/Loader";
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

    const maskedLocal =
      localPart.length <= 2
        ? `${localPart[0] || ""}*`
        : `${localPart.slice(0, 2)}${"*".repeat(Math.max(localPart.length - 2, 2))}`;

    return `${maskedLocal}@${domain}`;
  }, [email, hasEmail]);

  const handleResend = async () => {
    if (!hasEmail) {
      toast.error("No email address found. Request another reset link.");
      return;
    }
    if (loading) return;

    setLoading(true);
    try {
      await authService.requestPasswordReset(email);
      toast.success("A new reset link has been sent.");
    } catch (error) {
      const err = error as Error;
      toast.error(err.message || "Failed to resend email. Try again.", {
        toastId: "email-sent-resend-error",
      });
    } finally {
      setLoading(false);
    }
  };

  if (!hasEmail) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
        <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-[0_24px_60px_-40px_rgba(15,23,42,0.8)]">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-amber-50 p-4 text-amber-700">
            <MailCheck className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-black text-slate-900">Email context missing</h1>
          <p className="mt-3 text-sm text-slate-700">
            This page needs an email context. Request another password reset link.
          </p>
          <div className="mt-6 space-y-3">
            <Link
              to="/forgot-password"
              className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-cyan-700 px-4 text-sm font-semibold text-white transition hover:bg-cyan-800"
            >
              Request reset link
            </Link>
            <Link
              to="/login"
              className="inline-flex h-11 w-full items-center justify-center rounded-xl border border-slate-700 px-4 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-[0_24px_70px_-40px_rgba(15,23,42,0.8)] sm:p-10">
        <div className="mx-auto mb-5 inline-flex rounded-full bg-emerald-50 p-4 text-emerald-700 ring-8 ring-emerald-100/70">
          <MailCheck className="h-10 w-10" />
        </div>

        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Password actions</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900">Check your inbox</h1>
        <p className="mt-4 text-sm text-slate-700">
          We sent a reset link to <span className="font-bold text-slate-900">{maskedEmail}</span>. If you do not see it,
          check spam.
        </p>

        <div className="mt-8 space-y-3">
          <Button
            onClick={handleResend}
            size="lg"
            className="h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white transition hover:bg-cyan-800"
            disabled={loading}
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <Loader size="sm" color="white" />
                Resending...
              </span>
            ) : (
              "Resend email"
            )}
          </Button>

          <Link
            to="/login"
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-700 px-4 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
};

