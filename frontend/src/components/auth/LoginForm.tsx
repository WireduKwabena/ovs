import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import { Eye, EyeOff, LogIn, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";
import { useDispatch } from "react-redux";

import type { AppDispatch } from "@/app/store";
import { clearError, login as loginThunk } from "@/store/authSlice";
import { loginSchema } from "@/utils/validators";
import type { LoginCredentials } from "@/types";
import { Loader } from "@/components/common/Loader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/utils/apiError";
import { getDashboardPathForUser } from "@/utils/authRouting";

export const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginCredentials>({
    resolver: yupResolver(loginSchema),
  });

  useEffect(() => {
    dispatch(clearError());
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit = async (data: LoginCredentials) => {
    if (loading) return;

    setLoading(true);
    try {
      const response = await dispatch(
        loginThunk({ email: data.email.trim(), password: data.password }),
      ).unwrap();

      if ("token" in response && !("tokens" in response)) {
        toast.info(response.message || "Two-factor verification required.");
        navigate("/login/2fa", {
          replace: true,
          state: {
            from: (location.state as { from?: { pathname?: string } } | null)?.from,
          },
        });
        return;
      }

      toast.success("Login successful");

      const requestedPath =
        (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      const defaultPath = getDashboardPathForUser(response.user_type ?? null);
      const redirectPath = requestedPath && requestedPath !== "/" ? requestedPath : defaultPath;

      navigate(redirectPath, { replace: true });
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, "Login failed. Please try again."), {
        toastId: "login-form-error",
      });
    } finally {
      setLoading(false);
    }
  };

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
              CAVP Portal
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">Secure Organization Sign In</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Access vetting campaigns, candidate pipelines, AI interview outcomes, and compliance audit trails.
              </p>
            </div>

            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              Access is provisioned by platform operations. Need onboarding? Start from subscription plans.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-md">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Welcome back</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-900">Sign in to continue</h2>
            <p className="mt-2 text-sm text-slate-700">Use your organization account credentials.</p>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-semibold text-slate-700">
                  Work Email
                </Label>
                <Input
                  {...register("email")}
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@company.com"
                  disabled={loading}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? "login-email-error" : undefined}
                  className={`h-12 rounded-xl border px-4 text-sm transition focus-visible:ring-cyan-500 ${
                    errors.email
                      ? "border-red-400 bg-red-50"
                      : "border-slate-700 bg-slate-50 focus-visible:border-cyan-600"
                  }`}
                />
                {errors.email && (
                  <p id="login-email-error" className="text-xs font-medium text-red-600">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-semibold text-slate-700">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("password")}
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.password)}
                    aria-describedby={errors.password ? "login-password-error" : undefined}
                    className={`h-12 rounded-xl border px-4 pr-11 text-sm transition focus-visible:ring-cyan-500 ${
                      errors.password
                        ? "border-red-400 bg-red-50"
                        : "border-slate-700 bg-slate-50 focus-visible:border-cyan-600"
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-700 transition hover:text-slate-900 disabled:cursor-not-allowed"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                {errors.password && (
                  <p id="login-password-error" className="text-xs font-medium text-red-600">
                    {errors.password.message}
                  </p>
                )}
                <div className="text-right">
                  <Link
                    to="/forgot-password"
                    className="text-xs font-semibold text-cyan-700 transition hover:text-cyan-800 hover:underline"
                  >
                    Forgot your password?
                  </Link>
                </div>
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
                    Signing in...
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <LogIn className="h-4 w-4" />
                    Sign In
                  </span>
                )}
              </Button>
            </form>

            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
              Need a new organization account? Review plans and subscription setup first.
              <Link to="/subscribe" className="ml-1 font-semibold text-cyan-700 hover:underline">
                View plans
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};



