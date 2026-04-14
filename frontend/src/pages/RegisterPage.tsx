import React, { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, Lock } from "lucide-react";
import { toast } from "react-toastify";

import { RegisterForm } from "@/components/auth/RegisterForm";
import { authService, type OnboardingTokenValidationResponse } from "@/services/auth.service";

const getReasonMessage = (reason: string): string => {
  switch (reason) {
    case "missing_token":
      return "A valid onboarding invitation link is required for registration.";
    case "not_found":
      return "This onboarding token is invalid. Request a fresh invite link from your organization admin.";
    case "inactive":
      return "This onboarding token has been revoked. Request a fresh invite link.";
    case "expired":
      return "This onboarding token has expired. Request a fresh invite link.";
    case "max_uses_reached":
      return "This onboarding token has reached its usage limit. Request a fresh invite link.";
    case "subscription_inactive":
      return "Registration is unavailable because the organization subscription is inactive.";
    case "email_required":
      return "Your registration email is required for this onboarding token.";
    case "email_domain_not_allowed":
      return "Your email domain is not allowed for this onboarding token.";
    default:
      return "Unable to validate this onboarding token.";
  }
};

export const RegisterPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const onboardingToken = String(searchParams.get("onboarding_token") || "").trim();
  // org slug is embedded in the link by build_onboarding_link so the API interceptor
  // can send X-Organization-Slug for both token validation and registration.
  const orgSlug = String(searchParams.get("org") || "").trim();

  // Persist the org slug to sessionStorage before any API call fires so that
  // the Axios interceptor can attach X-Organization-Slug on the validate and
  // register requests (the user has no session yet at this point).
  useEffect(() => {
    if (orgSlug) {
      sessionStorage.setItem("organization_slug", orgSlug);
    }
  }, [orgSlug]);

  const [isVerifying, setIsVerifying] = useState(Boolean(onboardingToken));
  const [isTokenValid, setIsTokenValid] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [organizationName, setOrganizationName] = useState("");
  const [tokenExpiresAt, setTokenExpiresAt] = useState<string | null>(null);
  const [tokenRemainingUses, setTokenRemainingUses] = useState<number | null>(null);
  const [verificationNotice, setVerificationNotice] = useState<string | null>(null);
  const [verificationCycle, setVerificationCycle] = useState(0);

  const verifyOnboardingToken = useCallback(async (token: string) => {
    setIsVerifying(true);
    setVerificationError(null);
    setVerificationNotice(null);
    setIsTokenValid(false);
    setOrganizationName("");
    setTokenExpiresAt(null);
    setTokenRemainingUses(null);

    try {
      const result: OnboardingTokenValidationResponse = await authService.validateOnboardingToken({
        token,
      });

      if (!result.valid) {
        if (result.reason === "email_required") {
          setIsTokenValid(true);
          setOrganizationName(String(result.organization_name || "").trim());
          setTokenExpiresAt(result.expires_at || null);
          setTokenRemainingUses(
            typeof result.remaining_uses === "number" ? result.remaining_uses : null,
          );
          setVerificationNotice(
            "This invite enforces email-domain checks. Continue with registration using your work email.",
          );
          return;
        }

        const message = getReasonMessage(result.reason);
        setVerificationError(message);
        toast.error(message);
        return;
      }

      setIsTokenValid(true);
      setOrganizationName(String(result.organization_name || "").trim());
      setTokenExpiresAt(result.expires_at || null);
      setTokenRemainingUses(typeof result.remaining_uses === "number" ? result.remaining_uses : null);
    } catch (error: unknown) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Could not validate onboarding token right now. Please retry.";
      setVerificationError(message);
      toast.error(message);
    } finally {
      setIsVerifying(false);
    }
  }, []);

  useEffect(() => {
    if (!onboardingToken) {
      setIsVerifying(false);
      setIsTokenValid(false);
      setVerificationError("A valid onboarding invitation link is required for registration.");
      return;
    }

    void verifyOnboardingToken(onboardingToken);
  }, [onboardingToken, verificationCycle, verifyOnboardingToken]);

  const handleRetryVerification = () => {
    if (!onboardingToken || isVerifying) return;
    setVerificationCycle((prev) => prev + 1);
  };

  if (isVerifying) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-cyan-50 p-3 text-cyan-700">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Verifying Invitation</h1>
          <p className="mt-3 text-sm text-slate-700">Validating your organization onboarding token.</p>
        </div>
      </div>
    );
  }

  if (!onboardingToken || !isTokenValid) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-amber-50 p-3 text-amber-700">
            {verificationError ? <AlertTriangle className="h-6 w-6" /> : <Lock className="h-6 w-6" />}
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Onboarding Invite Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            {verificationError || "A valid organization onboarding link is required for registration."}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            {onboardingToken ? (
              <button
                type="button"
                onClick={handleRetryVerification}
                disabled={isVerifying}
                className="rounded-lg border border-cyan-600 px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-700 disabled:hover:bg-transparent"
              >
                Retry Validation
              </button>
            ) : null}
            <Link
              to="/login"
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Back to Login
            </Link>
            <Link
              to="/"
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Back Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mx-auto mt-6 w-full max-w-4xl px-4 sm:px-6 lg:px-0">
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <span>Onboarding invite validated{organizationName ? ` • ${organizationName}` : ""}</span>
          </div>
          <span>
            {tokenExpiresAt ? `Expires ${new Date(tokenExpiresAt).toLocaleString()}` : "Token active"}
            {tokenRemainingUses != null ? ` • ${tokenRemainingUses} uses left` : ""}
          </span>
        </div>
        {verificationNotice ? (
          <div className="mt-2 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-xs text-cyan-900">
            {verificationNotice}
          </div>
        ) : null}
      </div>
      <RegisterForm onboardingToken={onboardingToken} organizationName={organizationName} />
    </div>
  );
};

export default RegisterPage;
