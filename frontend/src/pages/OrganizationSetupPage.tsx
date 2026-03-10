import React, { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Building2, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { governanceService } from "@/services/governance.service";
import { useAuth } from "@/hooks/useAuth";

const normalizeReturnPath = (value: string | null | undefined, fallback: string): string => {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.startsWith("/billing/")) return fallback;
  return value;
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const candidate = error as {
    response?: { data?: { detail?: string; message?: string; error?: string } };
  };
  const responseData = candidate.response?.data;
  return responseData?.detail || responseData?.message || responseData?.error || fallback;
};

const OrganizationSetupPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { userType, activeOrganizationId, activeOrganization, refreshProfile } = useAuth();

  const [organizationName, setOrganizationName] = useState("");
  const [organizationCode, setOrganizationCode] = useState("");
  const [organizationType, setOrganizationType] = useState("agency");
  const [submitting, setSubmitting] = useState(false);

  const onboardingPath = "/organization/onboarding";
  const returnTo = normalizeReturnPath(searchParams.get("next"), "/subscribe");
  const nextPath = useMemo(() => {
    if (returnTo === "/subscribe") {
      return `/subscribe?returnTo=${encodeURIComponent(onboardingPath)}`;
    }
    return returnTo;
  }, [returnTo]);

  if (userType === "applicant") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Setup Unavailable</h1>
          <p className="mt-3 text-sm text-slate-700">
            Applicant accounts cannot provision organizations or manage organization billing.
          </p>
          <div className="mt-6 flex justify-center">
            <Button type="button" onClick={() => navigate("/dashboard")}>
              Back to Dashboard
            </Button>
          </div>
        </section>
      </main>
    );
  }

  const handleCreateOrganization = async () => {
    const name = organizationName.trim();
    const code = organizationCode.trim();
    if (!name) {
      toast.error("Organization name is required.");
      return;
    }
    if (submitting) return;

    setSubmitting(true);
    try {
      await governanceService.bootstrapOrganization({
        name,
        code: code || undefined,
        organization_type: organizationType,
      });
      toast.success("Organization created. You can now continue to subscription checkout.");
      refreshProfile();
      navigate(nextPath, { replace: true });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Unable to create organization setup."));
    } finally {
      setSubmitting(false);
    }
  };

  if (activeOrganizationId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-emerald-200 bg-white p-8 shadow-sm text-center">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-emerald-100 p-3 text-emerald-700">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-black text-slate-900">Organization Context Ready</h1>
          <p className="mt-3 text-sm text-slate-700">
            Active organization: <span className="font-semibold">{activeOrganization?.name || "Selected"}</span>.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Button type="button" onClick={() => navigate(nextPath)}>
              Continue to Subscription
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/organization/onboarding")}>
              Open Onboarding Management
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-xl bg-cyan-100 p-2 text-cyan-700">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-slate-900">Organization Setup</h1>
            <p className="text-sm text-slate-700">
              Create your organization context first, then continue to subscription checkout.
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2 space-y-1.5">
            <Label htmlFor="organization-name">Organization Name</Label>
            <Input
              id="organization-name"
              value={organizationName}
              onChange={(event) => setOrganizationName(event.target.value)}
              placeholder="Public Service Commission"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="organization-code">Organization Code (Optional)</Label>
            <Input
              id="organization-code"
              value={organizationCode}
              onChange={(event) => setOrganizationCode(event.target.value)}
              placeholder="public-service-commission"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="organization-type">Organization Type</Label>
            <select
              id="organization-type"
              value={organizationType}
              onChange={(event) => setOrganizationType(event.target.value)}
              disabled={submitting}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
            >
              <option value="agency">Agency</option>
              <option value="ministry">Ministry</option>
              <option value="committee_secretariat">Committee Secretariat</option>
              <option value="executive_office">Executive Office</option>
              <option value="audit">Audit Institution</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button type="button" onClick={() => void handleCreateOrganization()} disabled={submitting}>
            {submitting ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating...
              </span>
            ) : (
              "Create Organization and Continue"
            )}
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate("/dashboard")} disabled={submitting}>
            Cancel
          </Button>
        </div>
      </section>
    </main>
  );
};

export default OrganizationSetupPage;
