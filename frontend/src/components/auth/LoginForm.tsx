import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import { Eye, EyeOff, LogIn, Mail, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";
import { useDispatch } from "react-redux";

import type { AppDispatch } from "@/app/store";
import {
  adminLogin,
  clearError,
  login as loginThunk,
  resolveTenant,
  type TenantResolutionResult,
} from "@/store/authSlice";
import { loginSchema } from "@/utils/validators";
import type { LoginCredentials } from "@/types";
import { Loader } from "@/components/common/Loader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/utils/apiError";
import { getDashboardPathForUser } from "@/utils/authRouting";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LoginStep = "email" | "password";

interface EmailFormValues {
  email: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const normalizeLoginNextPath = (value: string | null | undefined): string | null => {
  if (!value) return null;
  if (!value.startsWith("/") || value.startsWith("//")) return null;
  if (value.startsWith("/login")) return null;
  if (value.startsWith("/register")) return null;
  return value;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();

  const [step, setStep] = useState<LoginStep>("email");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [resolvedEmail, setResolvedEmail] = useState("");
  const [resolvedTenant, setResolvedTenant] = useState<TenantResolutionResult | null>(null);

  // Separate form instances for each step
  const emailForm = useForm<EmailFormValues>({
    defaultValues: { email: "" },
  });

  const passwordForm = useForm<LoginCredentials>({
    resolver: yupResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    dispatch(clearError());
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  // ── Step 1: Resolve tenant from email ─────────────────────────────────────

  const onEmailSubmit = async (data: EmailFormValues) => {
    if (loading) return;
    setLoading(true);

    try {
      const result = await dispatch(
        resolveTenant(data.email.trim())
      ).unwrap();

      setResolvedEmail(data.email.trim());
      setResolvedTenant(result);

      // Pre-fill email into the password step form
      passwordForm.setValue("email", data.email.trim());

      setStep("password");
    } catch (error: unknown) {
      toast.error(
        getApiErrorMessage(error, "No account found for this email address."),
        { toastId: "resolve-tenant-error" }
      );
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2: Authenticate ──────────────────────────────────────────────────

  const onPasswordSubmit = async (data: LoginCredentials) => {
    if (loading || !resolvedTenant) return;
    setLoading(true);

    try {
      const credentials = {
        email: resolvedEmail,
        password: data.password,
      };

      // Route to the correct login endpoint based on resolved tenant type
      const loginAction =
        resolvedTenant.login_type === "admin"
          ? adminLogin(credentials)   // → /auth/admin/login/ (public schema)
          : loginThunk(credentials);  // → /auth/login/ (tenant schema via X-Organization-Slug)

      const response = await dispatch(loginAction).unwrap();

      // 2FA challenge — backend returned a token, not full session
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

      const requestedPathFromState =
        (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      const requestedPathFromQuery = new URLSearchParams(location.search).get("next");
      const defaultPath = getDashboardPathForUser(response.user_type ?? null);
      const redirectPath =
        normalizeLoginNextPath(requestedPathFromState) ||
        normalizeLoginNextPath(requestedPathFromQuery) ||
        defaultPath;

      navigate(redirectPath, { replace: true });
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, "Login failed. Please try again."), {
        toastId: "login-form-error",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleBackToEmail = () => {
    setStep("email");
    setResolvedTenant(null);
    setResolvedEmail("");
    passwordForm.reset();
    dispatch(clearError());
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)] lg:grid lg:grid-cols-5">

        {/* ── Sidebar ── */}
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              CAVP Portal
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">
                Secure Organization Sign In
              </h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Access vetting campaigns, candidate pipelines, AI interview
                outcomes, and compliance audit trails.
              </p>
            </div>

            {/* Show organization name once resolved */}
            {resolvedTenant?.organization_name ? (
              <div className="rounded-2xl border border-cyan-400/30 bg-cyan-500/10 p-4 text-xs text-cyan-200">
                <p className="font-semibold uppercase tracking-wide text-cyan-300">
                  Signing into
                </p>
                <p className="mt-1 text-sm font-bold text-white">
                  {resolvedTenant.organization_name}
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
                Access is provisioned by platform operations. Need onboarding?
                Start from subscription plans.
              </div>
            )}
          </div>
        </aside>

        {/* ── Main form ── */}
        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-md">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
              Welcome back
            </p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-900">
              Sign in to continue
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              {step === "email"
                ? "Enter your work email to get started."
                : "Enter your password to complete sign in."}
            </p>

            {/* ── Step 1: Email ── */}
            {step === "email" && (
              <form
                onSubmit={emailForm.handleSubmit(onEmailSubmit)}
                className="mt-8 space-y-5"
              >
                <div className="space-y-2">
                  <Label
                    htmlFor="email"
                    className="text-sm font-semibold text-slate-700"
                  >
                    Work Email
                  </Label>
                  <Input
                    {...emailForm.register("email", {
                      required: "Email is required",
                      pattern: {
                        value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                        message: "Enter a valid email address",
                      },
                    })}
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="name@company.com"
                    disabled={loading}
                    className="h-12 rounded-xl border border-slate-700 bg-slate-50 px-4 text-sm transition focus-visible:border-cyan-600 focus-visible:ring-cyan-500"
                  />
                  {emailForm.formState.errors.email && (
                    <p className="text-xs font-medium text-red-600">
                      {emailForm.formState.errors.email.message}
                    </p>
                  )}
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
                      Looking up account...
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <Mail className="h-4 w-4" />
                      Continue
                    </span>
                  )}
                </Button>
              </form>
            )}

            {/* ── Step 2: Password ── */}
            {step === "password" && (
              <form
                onSubmit={passwordForm.handleSubmit(onPasswordSubmit)}
                className="mt-8 space-y-5"
              >
                {/* Show resolved email as read-only with back option */}
                <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div>
                    <p className="text-xs text-slate-500">Signing in as</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {resolvedEmail}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleBackToEmail}
                    className="text-xs font-semibold text-cyan-700 hover:underline"
                  >
                    Change
                  </button>
                </div>

                <div className="space-y-2">
                  <Label
                    htmlFor="password"
                    className="text-sm font-semibold text-slate-700"
                  >
                    Password
                  </Label>
                  <div className="relative">
                    <Input
                      {...passwordForm.register("password")}
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      placeholder="Enter your password"
                      disabled={loading}
                      aria-invalid={Boolean(passwordForm.formState.errors.password)}
                      className={`h-12 rounded-xl border px-4 pr-11 text-sm transition focus-visible:ring-cyan-500 ${
                        passwordForm.formState.errors.password
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
                      {showPassword ? (
                        <EyeOff className="h-5 w-5" />
                      ) : (
                        <Eye className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                  {passwordForm.formState.errors.password && (
                    <p className="text-xs font-medium text-red-600">
                      {passwordForm.formState.errors.password.message}
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
            )}

            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
              Need a new organization account?
              <Link
                to="/organization/get-started"
                className="ml-1 font-semibold text-cyan-700 hover:underline"
              >
                Start organization setup
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};