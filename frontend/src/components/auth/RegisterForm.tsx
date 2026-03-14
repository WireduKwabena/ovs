import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import { toast } from "react-toastify";
import { useDispatch } from "react-redux";
import { Eye, EyeOff, ShieldCheck, UserPlus } from "lucide-react";

import type { AppDispatch } from "@/app/store";
import { clearError, register as registerThunk } from "@/store/authSlice";
import { registerSchema } from "@/utils/validators";
import type { RegisterData } from "@/types";
import { Loader } from "@/components/common/Loader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface RegisterFormProps {
  onboardingToken: string;
  organizationName?: string;
}

type RegisterFormValues = Omit<RegisterData, "onboarding_token" | "organization">;

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const normalizedError = error as {
    message?: string;
    response?: { data?: { message?: string; detail?: string; error?: string; reason?: string } };
  };

  const onboardingReason = String(normalizedError.response?.data?.reason || "").trim().toLowerCase();
  if (onboardingReason === "not_found") {
    return "This onboarding link is invalid. Request a fresh invite from your organization admin.";
  }
  if (onboardingReason === "inactive") {
    return "This onboarding link has been revoked. Request a fresh invite.";
  }
  if (onboardingReason === "expired") {
    return "This onboarding link has expired. Request a fresh invite.";
  }
  if (onboardingReason === "max_uses_reached") {
    return "This onboarding link has reached its usage limit. Request a fresh invite.";
  }
  if (onboardingReason === "subscription_inactive") {
    return "Registration is unavailable because this organization subscription is inactive.";
  }
  if (onboardingReason === "email_domain_not_allowed") {
    return "Your email domain is not allowed for this onboarding invite.";
  }

  return (
    normalizedError.response?.data?.error ||
    normalizedError.response?.data?.message ||
    normalizedError.response?.data?.detail ||
    normalizedError.message ||
    fallback
  );
};

export const RegisterForm: React.FC<RegisterFormProps> = ({
  onboardingToken,
  organizationName,
}) => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();

  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: yupResolver(registerSchema),
    defaultValues: {
      department: "",
    },
  });

  useEffect(() => {
    dispatch(clearError());
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<RegisterFormValues> = async (data) => {
    if (loading) return;
    if (!onboardingToken) {
      toast.error("A valid onboarding token is required to register.");
      return;
    }

    setLoading(true);

    try {
      await dispatch(
        registerThunk({
          ...data,
          first_name: data.first_name.trim(),
          last_name: data.last_name.trim(),
          email: data.email.trim(),
          phone_number: data.phone_number.trim(),
          department: (data.department || "").trim(),
          password: data.password,
          password_confirm: data.password_confirm,
          onboarding_token: onboardingToken,
        }),
      ).unwrap();

      toast.success("Registration successful. Please sign in.");
      dispatch(clearError());
      navigate("/login", { replace: true });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Registration failed. Please review your details."), {
        toastId: "register-form-error",
      });
    } finally {
      setLoading(false);
    }
  };

  const inputClass = (hasError: boolean) =>
    `h-11 rounded-xl border px-3 text-sm transition focus-visible:ring-cyan-500 ${
      hasError
        ? "border-red-400 bg-red-50"
        : "border-slate-700 bg-slate-50 focus-visible:border-cyan-600"
    }`;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-6xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)] lg:grid lg:grid-cols-5">
        <aside className="relative overflow-hidden bg-linear-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              CAVP Organization Setup
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">Provision Your Firm Workspace</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Complete registration with your organization onboarding invite and activate your operations workspace.
              </p>
            </div>

            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              This step is available only with a valid onboarding invitation link.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-2xl">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-cyan-50 p-2 text-cyan-700">
                <UserPlus className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Firm registration</p>
                <h2 className="text-2xl font-black tracking-tight text-slate-900">Create organization member account</h2>
                {organizationName ? (
                  <p className="mt-1 text-xs font-semibold text-slate-700">Organization: {organizationName}</p>
                ) : null}
              </div>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="first_name" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    First Name
                  </Label>
                  <Input
                    {...register("first_name")}
                    id="first_name"
                    autoComplete="given-name"
                    placeholder="John"
                    disabled={loading}
                    aria-invalid={Boolean(errors.first_name)}
                    className={inputClass(Boolean(errors.first_name))}
                  />
                  {errors.first_name && <p className="text-xs font-medium text-red-600">{errors.first_name.message}</p>}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="last_name" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Last Name
                  </Label>
                  <Input
                    {...register("last_name")}
                    id="last_name"
                    autoComplete="family-name"
                    placeholder="Doe"
                    disabled={loading}
                    aria-invalid={Boolean(errors.last_name)}
                    className={inputClass(Boolean(errors.last_name))}
                  />
                  {errors.last_name && <p className="text-xs font-medium text-red-600">{errors.last_name.message}</p>}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
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
                    className={inputClass(Boolean(errors.email))}
                  />
                  {errors.email && <p className="text-xs font-medium text-red-600">{errors.email.message}</p>}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="phone_number" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Phone Number
                  </Label>
                  <Input
                    {...register("phone_number")}
                    id="phone_number"
                    type="tel"
                    autoComplete="tel"
                    placeholder="+1 (555) 123-4567"
                    disabled={loading}
                    aria-invalid={Boolean(errors.phone_number)}
                    className={inputClass(Boolean(errors.phone_number))}
                  />
                  {errors.phone_number && <p className="text-xs font-medium text-red-600">{errors.phone_number.message}</p>}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="department" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Department
                  </Label>
                  <Input
                    {...register("department")}
                    id="department"
                    placeholder="Human Resources"
                    disabled={loading}
                    className={inputClass(false)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Password
                  </Label>
                  <div className="relative">
                    <Input
                      {...register("password")}
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="Create password"
                      disabled={loading}
                      aria-invalid={Boolean(errors.password)}
                      className={`${inputClass(Boolean(errors.password))} pr-11`}
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
                  {errors.password && <p className="text-xs font-medium text-red-600">{errors.password.message}</p>}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password_confirm" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Confirm Password
                  </Label>
                  <div className="relative">
                    <Input
                      {...register("password_confirm")}
                      id="password_confirm"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="Re-enter password"
                      disabled={loading}
                      aria-invalid={Boolean(errors.password_confirm)}
                      className={`${inputClass(Boolean(errors.password_confirm))} pr-11`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      disabled={loading}
                      className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-700 transition hover:text-slate-900 disabled:cursor-not-allowed"
                      aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    >
                      {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                  {errors.password_confirm && <p className="text-xs font-medium text-red-600">{errors.password_confirm.message}</p>}
                </div>
              </div>

              <Button
                type="submit"
                size="lg"
                className="mt-2 h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white shadow-md transition hover:bg-cyan-800"
                disabled={loading}
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader size="sm" color="white" />
                    Creating account...
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <UserPlus className="h-4 w-4" />
                    Create Account
                  </span>
                )}
              </Button>
            </form>

            <p className="mt-4 text-center text-xs text-slate-700">
              Already provisioned?
              <Link to="/login" className="ml-1 font-semibold text-cyan-700 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};


