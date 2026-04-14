import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Building2, Loader2, ShieldCheck, UserPlus } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  authService,
  type OrganizationAdminBootstrapData,
} from "@/services/auth.service";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

const normalizeReturnPath = (value: string | null | undefined, fallback: string): string => {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.startsWith("/billing/")) return fallback;
  if (value.startsWith("/login")) return fallback;
  return value;
};

const OrganizationAdminSignupPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [submitting, setSubmitting] = useState(false);
  const nextPath = useMemo(
    () => normalizeReturnPath(searchParams.get("next"), "/subscribe"),
    [searchParams],
  );
  const [form, setForm] = useState<OrganizationAdminBootstrapData>({
    email: "",
    password: "",
    password_confirm: "",
    first_name: "",
    last_name: "",
    phone_number: "",
    department: "",
    organization_name: "",
    organization_code: "",
    organization_type: "agency",
  });

  const updateField = <K extends keyof OrganizationAdminBootstrapData>(
    key: K,
    value: OrganizationAdminBootstrapData[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const requiredFields: Array<[keyof OrganizationAdminBootstrapData, string]> = [
      ["first_name", "First name is required."],
      ["last_name", "Last name is required."],
      ["email", "Work email is required."],
      ["password", "Password is required."],
      ["password_confirm", "Password confirmation is required."],
      ["organization_name", "Organization name is required."],
    ];
    for (const [key, message] of requiredFields) {
      if (!String(form[key] || "").trim()) {
        toast.error(message);
        return;
      }
    }

    if (form.password !== form.password_confirm) {
      toast.error("Password fields must match.");
      return;
    }

    setSubmitting(true);
    try {
      await authService.registerOrganizationAdmin({
        ...form,
        email: form.email.trim().toLowerCase(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone_number: form.phone_number.trim(),
        department: String(form.department || "").trim(),
        organization_name: form.organization_name.trim(),
        organization_code: String(form.organization_code || "").trim() || undefined,
      });
      toast.success("Organization account created. Sign in to continue setup.");
      navigate(`/login?next=${encodeURIComponent(nextPath)}`, {
        replace: true,
        state: {
          from: { pathname: nextPath },
        },
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Unable to create organization account."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-10">
      <div className="pointer-events-none absolute -left-20 top-6 h-72 w-72 rounded-full bg-cyan-200/45 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-80 w-80 rounded-full bg-amber-200/40 blur-3xl" />

      <section className="relative w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.75)] lg:grid lg:grid-cols-5">
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              Organization bootstrap
            </div>
            <div>
              <h1 className="text-3xl font-black leading-tight">Create Your Organization Admin Account</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Set up your organization and first administrator. Team members must still join using onboarding links.
              </p>
            </div>
            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              This flow creates one organization and one default registry admin membership.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-xl bg-cyan-50 p-2 text-cyan-700">
              <UserPlus className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-2xl font-black tracking-tight text-slate-900">Organization Account Setup</h2>
              <p className="text-sm text-slate-700">
                After setup, sign in and continue to your next step.
              </p>
            </div>
          </div>
          <div className="mb-5 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-xs text-cyan-900">
            Next step after sign-in: <span className="font-semibold">{nextPath}</span>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  value={form.first_name}
                  onChange={(event) => updateField("first_name", event.target.value)}
                  disabled={submitting}
                  placeholder="Ada"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  value={form.last_name}
                  onChange={(event) => updateField("last_name", event.target.value)}
                  disabled={submitting}
                  placeholder="Mensah"
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="email">Work Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(event) => updateField("email", event.target.value)}
                  disabled={submitting}
                  placeholder="registry.admin@agency.gov"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="phone_number">Phone Number</Label>
                <Input
                  id="phone_number"
                  value={form.phone_number}
                  onChange={(event) => updateField("phone_number", event.target.value)}
                  disabled={submitting}
                  placeholder="+12345678901"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="department">Department</Label>
                <Input
                  id="department"
                  value={form.department}
                  onChange={(event) => updateField("department", event.target.value)}
                  disabled={submitting}
                  placeholder="Registry"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={form.password}
                  onChange={(event) => updateField("password", event.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password_confirm">Confirm Password</Label>
                <Input
                  id="password_confirm"
                  type="password"
                  value={form.password_confirm}
                  onChange={(event) => updateField("password_confirm", event.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="organization_name">Organization Name</Label>
                <Input
                  id="organization_name"
                  value={form.organization_name}
                  onChange={(event) => updateField("organization_name", event.target.value)}
                  disabled={submitting}
                  placeholder="Public Service Commission"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="organization_code">Organization Code (Optional)</Label>
                <Input
                  id="organization_code"
                  value={form.organization_code}
                  onChange={(event) => updateField("organization_code", event.target.value)}
                  disabled={submitting}
                  placeholder="public-service-commission"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="organization_type">Organization Type</Label>
                <select
                  id="organization_type"
                  value={form.organization_type}
                  onChange={(event) => updateField("organization_type", event.target.value)}
                  disabled={submitting}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
                >
                  <option value="agency">Agency</option>
                  <option value="ministry">Ministry</option>
                  <option value="committee_secretariat">Committee Secretariat</option>
                  <option value="executive_office">Executive Office</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <Button
              type="submit"
              className="mt-2 h-11 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white hover:bg-cyan-800"
              disabled={submitting}
            >
              {submitting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating organization account...
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Create Organization Account
                </span>
              )}
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-slate-700">
            Already have an account?
            <Link to="/login" className="ml-1 font-semibold text-cyan-700 hover:underline">
              Sign in
            </Link>
          </p>
        </section>
      </section>
    </main>
  );
};

export default OrganizationAdminSignupPage;
