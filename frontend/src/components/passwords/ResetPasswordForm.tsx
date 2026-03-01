import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Eye, EyeOff, KeyRound, ShieldCheck } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";

import { type AppDispatch, type RootState } from "@/app/store";
import { clearError, resetPassword } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";

const schema = yup.object({
  new_password1: yup.string().min(8, "Password must be at least 8 characters").required("Password is required"),
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
    if (loading || !hasToken || !token) return;

    try {
      await dispatch(resetPassword({ token, ...data })).unwrap();
      toast.success("Password reset successful. Please sign in.");
      dispatch(clearError());
      navigate("/login", { replace: true });
    } catch {
      // Toast handled by auth error observer.
    }
  };

  const inputClass = (hasError: boolean) =>
    `h-12 rounded-xl border px-4 pr-11 text-sm transition focus-visible:ring-cyan-500 ${
      hasError
        ? "border-red-400 bg-red-50"
        : "border-slate-300 bg-slate-50 focus-visible:border-cyan-600"
    }`;

  if (!hasToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
        <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-[0_24px_60px_-40px_rgba(15,23,42,0.8)]">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-amber-50 p-4 text-amber-700">
            <KeyRound className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-black text-slate-900">Invalid reset link</h1>
          <p className="mt-3 text-sm text-slate-600">This link is malformed or missing a reset token.</p>
          <div className="mt-6 space-y-3">
            <Link
              to="/forgot-password"
              className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-cyan-700 px-4 text-sm font-semibold text-white transition hover:bg-cyan-800"
            >
              Request a new link
            </Link>
            <Link
              to="/login"
              className="inline-flex h-11 w-full items-center justify-center rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
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

      <div className="relative w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)] lg:grid lg:grid-cols-5">
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              Password Update
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">Set Your New Password</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Choose a strong, unique password to protect your firm account and candidate data access.
              </p>
            </div>

            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              Use at least 8 characters with a strong combination.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-md">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Password actions</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-900">Reset password</h2>
            <p className="mt-2 text-sm text-slate-600">Enter and confirm your new password below.</p>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="new_password1" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  New Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("new_password1")}
                    id="new_password1"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Create a new password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.new_password1)}
                    className={inputClass(Boolean(errors.new_password1))}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700 disabled:cursor-not-allowed"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                {errors.new_password1 && <p className="text-xs font-medium text-red-600">{errors.new_password1.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="new_password2" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Confirm Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("new_password2")}
                    id="new_password2"
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Re-enter new password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.new_password2)}
                    className={inputClass(Boolean(errors.new_password2))}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700 disabled:cursor-not-allowed"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                {errors.new_password2 && <p className="text-xs font-medium text-red-600">{errors.new_password2.message}</p>}
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
                    Updating password...
                  </span>
                ) : (
                  "Reset password"
                )}
              </Button>

              <p className="text-center text-xs text-slate-600">
                Remember your password?
                <Link to="/login" className="ml-1 font-semibold text-cyan-700 hover:underline">
                  Back to sign in
                </Link>
              </p>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};