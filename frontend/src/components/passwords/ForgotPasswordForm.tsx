import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";
import { Mail, ShieldCheck } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";
import { type AppDispatch, type RootState } from "@/app/store";
import {
  clearError,
  requestPasswordReset,
  resetPasswordStatus,
} from "@/store/authSlice";

const schema = yup.object({
  email: yup.string().email("Enter a valid email address").required("Email is required"),
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
    if (error) {
      toast.error(error, { toastId: `forgot-password-${error}` });
    }
  }, [error]);

  useEffect(() => {
    return () => {
      dispatch(resetPasswordStatus());
      dispatch(clearError());
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

    const maskedLocal =
      localPart.length <= 2
        ? `${localPart[0] || ""}*`
        : `${localPart.slice(0, 2)}${"*".repeat(Math.max(localPart.length - 2, 2))}`;

    return `${maskedLocal}@${domain}`;
  }, [requestedEmail]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)] lg:grid lg:grid-cols-5">
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              Account Recovery
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">Reset Access Credentials</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                We will send a secure password reset link to your registered organization email.
              </p>
            </div>

            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              Reset links are short-lived and single-use for security.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-md">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-cyan-50 p-2 text-cyan-700">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Password actions</p>
                <h2 className="text-2xl font-black tracking-tight text-slate-900">Forgot password</h2>
              </div>
            </div>

            {passwordResetEmailSent ? (
              <div className="mt-7 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <h3 className="text-lg font-bold text-emerald-900">Reset link sent</h3>
                <p className="mt-2 text-sm text-emerald-800">
                  Check your inbox for the password reset email.
                </p>
                {maskedRequestedEmail && (
                  <p className="mt-2 text-sm font-semibold text-emerald-900">Sent to: {maskedRequestedEmail}</p>
                )}
                <div className="mt-5 flex flex-col gap-3">
                  <button
                    type="button"
                    onClick={handleSendAnotherLink}
                    className="h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    Send another link
                  </button>
                  <Link
                    to="/login"
                    className="inline-flex h-11 items-center justify-center rounded-xl bg-cyan-700 px-4 text-sm font-semibold text-white transition hover:bg-cyan-800"
                  >
                    Back to sign in
                  </Link>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Work Email
                  </Label>
                  <Input
                    {...register("email")}
                    id="email"
                    type="email"
                    placeholder="name@company.com"
                    disabled={loading}
                    aria-invalid={Boolean(errors.email)}
                    className={`h-12 rounded-xl border px-4 text-sm transition focus-visible:ring-cyan-500 ${
                      errors.email
                        ? "border-red-400 bg-red-50"
                        : "border-slate-300 bg-slate-50 focus-visible:border-cyan-600"
                    }`}
                  />
                  {errors.email && <p className="text-xs font-medium text-red-600">{errors.email.message}</p>}
                </div>

                <Button
                  type="submit"
                  size="lg"
                  className="h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white shadow-md transition hover:bg-cyan-800"
                  disabled={loading}
                >
                  {loading ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader size="sm" color="white" />
                      Sending link...
                    </span>
                  ) : (
                    "Send reset link"
                  )}
                </Button>

                <p className="text-center text-xs text-slate-600">
                  Remembered your password?
                  <Link to="/login" className="ml-1 font-semibold text-cyan-700 hover:underline">
                    Back to sign in
                  </Link>
                </p>
              </form>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};