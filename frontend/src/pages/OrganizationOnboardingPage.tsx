import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, Loader2, Mail, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import {
  billingService,
  type BillingSubscriptionManageResponse,
} from "@/services/billing.service";
import { useAuth } from "@/hooks/useAuth";
import type {
  OrganizationOnboardingTokenGenerateResponse,
  OrganizationOnboardingTokenStateResponse,
} from "@/types";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const candidate = error as {
    response?: { data?: { detail?: string; message?: string; error?: string; code?: string } };
  };
  const data = candidate.response?.data;
  if (data?.code === "RECENT_AUTH_REQUIRED") {
    return "Recent authentication verification is required before managing onboarding links.";
  }
  return data?.detail || data?.message || data?.error || fallback;
};

const OrganizationOnboardingPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    userType,
    activeOrganization,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const [stateLoading, setStateLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [onboardingState, setOnboardingState] = useState<OrganizationOnboardingTokenStateResponse | null>(null);
  const [billingSummary, setBillingSummary] = useState<BillingSubscriptionManageResponse | null>(null);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  const [issuedLink, setIssuedLink] = useState<string | null>(null);
  const [maxUses, setMaxUses] = useState("25");
  const [expiresInHours, setExpiresInHours] = useState("72");
  const [allowedDomain, setAllowedDomain] = useState("");
  const [inviteEmails, setInviteEmails] = useState<string[]>([]);
  const [inviteEmailDraft, setInviteEmailDraft] = useState("");
  const [sendingInvite, setSendingInvite] = useState(false);

  const canManage = userType !== "applicant" && canManageActiveOrganizationGovernance;
  const tokenState = onboardingState?.token ?? null;
  const hasActiveSubscription = Boolean(onboardingState?.subscription_active);

  const isMissingContext = !activeOrganizationId;
  const copyIssuedInvite = async () => {
    const inviteLink = issuedLink;
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      toast.success("Onboarding link copied.");
    } catch {
      toast.error("Unable to copy onboarding link.");
    }
  };

  const fetchState = async () => {
    if (!canManage || !activeOrganizationId) return;
    setStateLoading(true);
    try {
      const [tokenResponse, billingResponse] = await Promise.all([
        billingService.getOnboardingTokenState(),
        billingService.getSubscriptionManagement(),
      ]);
      setOnboardingState(tokenResponse);
      setBillingSummary(billingResponse);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to load organization onboarding state."));
    } finally {
      setStateLoading(false);
    }
  };

  useEffect(() => {
    void fetchState();
    // active org + authz context changes should refresh onboarding state
  }, [activeOrganizationId, canManage]);

  const handleGenerate = async () => {
    if (!canManage || !activeOrganizationId) return;
    setActionLoading(true);
    try {
      const payload = {
        rotate: true,
        max_uses: Number.isFinite(Number(maxUses)) && Number(maxUses) > 0 ? Number(maxUses) : undefined,
        expires_in_hours:
          Number.isFinite(Number(expiresInHours)) && Number(expiresInHours) > 0
            ? Number(expiresInHours)
            : undefined,
        allowed_email_domain: allowedDomain.trim() || undefined,
      };
      const response: OrganizationOnboardingTokenGenerateResponse =
        await billingService.generateOnboardingToken(payload);
      setIssuedToken(response.token || null);
      setIssuedLink(response.onboarding_link || null);
      toast.success("Onboarding invite generated.");
      await fetchState();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to generate onboarding invite."));
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!canManage || !activeOrganizationId) return;
    setActionLoading(true);
    try {
      await billingService.revokeOnboardingToken({ reason: "manual_revocation" });
      setIssuedToken(null);
      setIssuedLink(null);
      toast.success("Active onboarding invite revoked.");
      await fetchState();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to revoke onboarding invite."));
    } finally {
      setActionLoading(false);
    }
  };

  const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

  const commitEmailDraft = () => {
    const email = inviteEmailDraft.trim().replace(/,+$/, "");
    if (!email) return;
    if (!isValidEmail(email)) {
      toast.error(`"${email}" is not a valid email address.`);
      return;
    }
    if (inviteEmails.includes(email)) {
      setInviteEmailDraft("");
      return;
    }
    if (inviteEmails.length >= 20) {
      toast.error("You can send to at most 20 recipients at once.");
      return;
    }
    setInviteEmails((prev) => [...prev, email]);
    setInviteEmailDraft("");
  };

  const handleEmailDraftKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === "," || e.key === "Tab") {
      e.preventDefault();
      commitEmailDraft();
    } else if (e.key === "Backspace" && inviteEmailDraft === "" && inviteEmails.length > 0) {
      setInviteEmails((prev) => prev.slice(0, -1));
    }
  };

  const removeInviteEmail = (email: string) => {
    setInviteEmails((prev) => prev.filter((e) => e !== email));
  };

  const handleSendInvite = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage || !activeOrganizationId) return;

    // Commit any in-progress draft before submitting
    const draft = inviteEmailDraft.trim().replace(/,+$/, "");
    let emailsToSend = inviteEmails;
    if (draft) {
      if (!isValidEmail(draft)) {
        toast.error(`"${draft}" is not a valid email address.`);
        return;
      }
      if (!emailsToSend.includes(draft)) {
        emailsToSend = [...emailsToSend, draft];
      }
    }
    if (emailsToSend.length === 0) {
      toast.error("Add at least one recipient email address.");
      return;
    }

    setSendingInvite(true);
    try {
      const payload = {
        recipient_emails: emailsToSend,
        rotate: true,
        max_uses: Number.isFinite(Number(maxUses)) && Number(maxUses) > 0 ? Number(maxUses) : undefined,
        expires_in_hours:
          Number.isFinite(Number(expiresInHours)) && Number(expiresInHours) > 0
            ? Number(expiresInHours)
            : undefined,
        allowed_email_domain: allowedDomain.trim() || undefined,
      };
      const result = await billingService.sendOnboardingInvite(payload);
      const sentCount = result.sent.length;
      const failedCount = result.failed.length;
      if (failedCount === 0) {
        toast.success(`Invite${sentCount > 1 ? "s" : ""} sent to ${sentCount} recipient${sentCount > 1 ? "s" : ""}.`);
      } else {
        toast.warning(
          `Sent to ${sentCount}, failed for ${failedCount}: ${result.failed.join(", ")}`,
        );
      }
      setInviteEmails([]);
      setInviteEmailDraft("");
      await fetchState();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Failed to send onboarding invites."));
    } finally {
      setSendingInvite(false);
    }
  };

  const seatSummary = useMemo(() => {
    const remaining = onboardingState?.organization_seat_remaining;
    const used = onboardingState?.organization_seat_used;
    const limit = onboardingState?.organization_seat_limit;
    if (remaining == null && used == null && limit == null) {
      return "Seat usage is not available for this subscription.";
    }
    return `Seats: ${used ?? 0}/${limit ?? "∞"} used, ${remaining ?? "∞"} remaining`;
  }, [
    onboardingState?.organization_seat_limit,
    onboardingState?.organization_seat_remaining,
    onboardingState?.organization_seat_used,
  ]);

  if (isMissingContext) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Active Organization Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Set up or select an active organization before managing onboarding links.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Button type="button" onClick={() => navigate("/organization/setup")}>
              Organization Setup
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/organization/dashboard")}>
              Organization Dashboard
            </Button>
          </div>
        </section>
      </main>
    );
  }

  if (!canManage) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Admin Access Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Onboarding token management is restricted to organization admins.
          </p>
          <div className="mt-6">
            <Button type="button" onClick={() => navigate("/workspace")}>
              Back to Workspace
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto w-full max-w-5xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              Organization Onboarding
            </div>
            <h1 className="mt-3 text-2xl font-black text-slate-900">Manage Member Invite Link</h1>
            <p className="mt-2 text-sm text-slate-700">
              Organization: <span className="font-semibold">{activeOrganization?.name || "N/A"}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Subscription Status
            </p>
            <p className={`text-sm font-bold ${hasActiveSubscription ? "text-emerald-700" : "text-amber-700"}`}>
              {hasActiveSubscription ? "Active" : "Inactive"}
            </p>
            <p className="mt-1 text-xs text-slate-700">{seatSummary}</p>
          </div>
        </div>

        {!hasActiveSubscription ? (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Active organization subscription is required before issuing onboarding invites.
            <div className="mt-3">
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  navigate(`/subscribe?returnTo=${encodeURIComponent("/organization/onboarding")}`)
                }
              >
                Go to Subscription Plans
              </Button>
            </div>
          </div>
        ) : null}

        {stateLoading ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading onboarding state...
            </span>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Current Token</p>
              <p className="mt-2 text-sm text-slate-700">
                {tokenState ? (
                  <>
                    Preview: <span className="font-mono font-semibold">{tokenState.token_preview}</span>
                  </>
                ) : (
                  "No active onboarding token."
                )}
              </p>
              {tokenState ? (
                <p className="mt-1 text-xs text-slate-700">
                  Remaining uses: {tokenState.remaining_uses ?? "Unlimited"} | Expires:{" "}
                  {tokenState.expires_at ? new Date(tokenState.expires_at).toLocaleString() : "No expiry"}
                </p>
              ) : null}
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Billing Plan</p>
              <p className="mt-2 text-sm text-slate-700">
                {billingSummary?.subscription
                  ? `${billingSummary.subscription.plan_name} (${billingSummary.subscription.billing_cycle})`
                  : "No active billing subscription details."}
              </p>
            </div>
          </div>
        )}

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <label htmlFor="onboarding-max-uses" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Max Uses
            </label>
            <input
              id="onboarding-max-uses"
              type="number"
              min={1}
              value={maxUses}
              onChange={(event) => setMaxUses(event.target.value)}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
              disabled={actionLoading}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="onboarding-expiry" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Expires In (Hours)
            </label>
            <input
              id="onboarding-expiry"
              type="number"
              min={1}
              value={expiresInHours}
              onChange={(event) => setExpiresInHours(event.target.value)}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
              disabled={actionLoading}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="onboarding-domain" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Allowed Email Domain
            </label>
            <input
              id="onboarding-domain"
              type="text"
              placeholder="gov.example"
              value={allowedDomain}
              onChange={(event) => setAllowedDomain(event.target.value)}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900"
              disabled={actionLoading}
            />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button type="button" onClick={() => void handleGenerate()} disabled={actionLoading || !hasActiveSubscription}>
            {actionLoading ? "Processing..." : "Generate / Rotate Invite"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleRevoke()}
            disabled={actionLoading || !tokenState}
          >
            Revoke Active Invite
          </Button>
          <Button type="button" variant="outline" onClick={() => void fetchState()} disabled={stateLoading || actionLoading}>
            Refresh State
          </Button>
        </div>

        {issuedToken || issuedLink ? (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-semibold text-emerald-900">New onboarding invite generated.</p>
            {issuedLink ? (
              <p className="mt-2 break-all text-xs text-emerald-800">{issuedLink}</p>
            ) : null}
            {issuedToken ? (
              <p className="mt-2 break-all font-mono text-xs text-emerald-900">{issuedToken}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {issuedLink ? (
                <Button type="button" size="sm" variant="outline" onClick={() => void copyIssuedInvite()}>
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  Copy Invite Link
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Mail className="h-4 w-4 text-slate-600" />
            <p className="text-sm font-semibold text-slate-900">Send Invite by Email</p>
          </div>
          <p className="mb-4 text-xs text-slate-600">
            Generate a new invite link and send it to one or more people. Type an address and press{" "}
            <kbd className="rounded border border-slate-300 bg-white px-1 py-0.5 font-mono text-[10px]">
              Enter
            </kbd>{" "}
            or{" "}
            <kbd className="rounded border border-slate-300 bg-white px-1 py-0.5 font-mono text-[10px]">
              ,
            </kbd>{" "}
            to add it. Up to 20 recipients. Uses the same token settings above.
          </p>
          <form onSubmit={(e) => void handleSendInvite(e)} className="space-y-3">
            <div className="space-y-1.5">
              <label
                htmlFor="invite-email-input"
                className="text-xs font-semibold uppercase tracking-wide text-slate-700"
              >
                Recipients
              </label>
              {/* Tag input container */}
              <div
                className={[
                  "flex min-h-[2.5rem] flex-wrap gap-1.5 rounded-md border bg-white px-2 py-1.5 text-sm transition focus-within:ring-2 focus-within:ring-primary/20",
                  sendingInvite || !hasActiveSubscription
                    ? "cursor-not-allowed opacity-60 border-slate-200"
                    : "border-slate-300 focus-within:border-primary/50",
                ].join(" ")}
                onClick={() => document.getElementById("invite-email-input")?.focus()}
              >
                {inviteEmails.map((email) => (
                  <span
                    key={email}
                    className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
                  >
                    {email}
                    <button
                      type="button"
                      aria-label={`Remove ${email}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        removeInviteEmail(email);
                      }}
                      className="ml-0.5 rounded hover:text-destructive focus:outline-none"
                      disabled={sendingInvite}
                    >
                      ×
                    </button>
                  </span>
                ))}
                <input
                  id="invite-email-input"
                  type="text"
                  inputMode="email"
                  placeholder={inviteEmails.length === 0 ? "colleague@example.com" : "Add another…"}
                  value={inviteEmailDraft}
                  onChange={(e) => setInviteEmailDraft(e.target.value)}
                  onKeyDown={handleEmailDraftKeyDown}
                  onBlur={commitEmailDraft}
                  className="min-w-[180px] flex-1 bg-transparent py-0.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed"
                  disabled={sendingInvite || !hasActiveSubscription || inviteEmails.length >= 20}
                />
              </div>
              {inviteEmails.length > 0 ? (
                <p className="text-xs text-slate-500">
                  {inviteEmails.length} recipient{inviteEmails.length > 1 ? "s" : ""} added
                  {inviteEmails.length < 20 ? ` · ${20 - inviteEmails.length} remaining` : " · limit reached"}
                </p>
              ) : null}
            </div>
            <Button
              type="submit"
              disabled={
                sendingInvite ||
                !hasActiveSubscription ||
                (inviteEmails.length === 0 && !inviteEmailDraft.trim())
              }
            >
              {sendingInvite ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  Sending…
                </>
              ) : (
                <>
                  <Mail className="mr-1.5 h-3.5 w-3.5" />
                  Send Invite{inviteEmails.length > 1 ? "s" : ""}
                </>
              )}
            </Button>
          </form>
        </div>

        <div className="mt-6">
          <Button type="button" variant="outline" onClick={() => navigate("/organization/dashboard")}>
            Open Organization Dashboard
          </Button>
        </div>
      </section>
    </main>
  );
};

export default OrganizationOnboardingPage;
