import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  CreditCard,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UsersRound,
  UserCog,
} from "lucide-react";
import { useDispatch } from "react-redux";
import { toast } from "react-toastify";

import type { AppDispatch } from "@/app/store";
import { useAuth } from "@/hooks/useAuth";
import { billingService, type BillingSubscriptionManageResponse } from "@/services/billing.service";
import { fetchProfile, updateUserProfile } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { OrganizationOnboardingTokenStateResponse } from "@/types";
import { getUserDisplayName } from "@/utils/userDisplay";

type PaymentMethodChoice = "card" | "bank_transfer" | "mobile_money";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;
  const payload = error as {
    response?: { data?: { detail?: string; error?: string; message?: string } };
    message?: string;
  };
  return (
    payload.response?.data?.detail ||
    payload.response?.data?.error ||
    payload.response?.data?.message ||
    payload.message ||
    fallback
  );
};

const formatDateTimeLabel = (value: string | null | undefined): string => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "N/A";
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const UserSettingsPage: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const {
    user,
    userType,
    canManageActiveOrganizationGovernance,
    organizations,
    activeOrganization,
    activeOrganizationId,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [organization, setOrganization] = useState("");
  const [department, setDepartment] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [nationality, setNationality] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [yearsOfExperience, setYearsOfExperience] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [bio, setBio] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [billingData, setBillingData] = useState<BillingSubscriptionManageResponse | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingActionLoading, setBillingActionLoading] = useState(false);
  const [sandboxPaymentMethod, setSandboxPaymentMethod] = useState<PaymentMethodChoice>("card");
  const [onboardingState, setOnboardingState] = useState<OrganizationOnboardingTokenStateResponse | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(false);

  const resolvedOrganizations = Array.isArray(organizations) ? organizations : [];
  const organizationFieldLocked = resolvedOrganizations.length > 0;
  const canViewBilling = userType !== "applicant";
  const canManageOrganizationBilling = canViewBilling && canManageActiveOrganizationGovernance;

  const canEditPhone = useMemo(
    () => Boolean(user && typeof user === "object" && "phone_number" in user),
    [user],
  );

  const accountName = useMemo(() => {
    return getUserDisplayName(user, "");
  }, [user]);

  const memberSince = useMemo(() => {
    if (!user?.created_at) return "Unknown";
    const parsed = new Date(user.created_at);
    if (Number.isNaN(parsed.getTime())) return "Unknown";
    return parsed.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }, [user]);

  const managedSubscription = billingData?.subscription ?? null;
  const activeOnboardingToken = onboardingState?.token ?? null;
  const isStripeManaged = managedSubscription?.provider === "stripe";
  const isSandboxManaged = managedSubscription?.provider === "sandbox";
  const isPaystackManaged = managedSubscription?.provider === "paystack";

  const fetchBillingManagement = useCallback(async () => {
    if (!canViewBilling) {
      setBillingData(null);
      return;
    }
    setBillingLoading(true);
    try {
      const response = await billingService.getSubscriptionManagement();
      setBillingData(response);
      const method = response.subscription?.payment_method?.type;
      if (method === "card" || method === "bank_transfer" || method === "mobile_money") {
        setSandboxPaymentMethod(method);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to load billing details."));
      setBillingData(null);
    } finally {
      setBillingLoading(false);
    }
  }, [canViewBilling]);

  const fetchOnboardingState = useCallback(async () => {
    if (!canManageOrganizationBilling || !activeOrganizationId) {
      setOnboardingState(null);
      return;
    }

    setOnboardingLoading(true);
    try {
      const response = await billingService.getOnboardingTokenState();
      setOnboardingState(response);
    } catch (error) {
      setOnboardingState(null);
      toast.error(getErrorMessage(error, "Failed to load organization onboarding status."));
    } finally {
      setOnboardingLoading(false);
    }
  }, [activeOrganizationId, canManageOrganizationBilling]);

  useEffect(() => {
    setEmail(user?.email || "");
    setFirstName(user?.first_name || "");
    setLastName(user?.last_name || "");
    if (organizationFieldLocked) {
      setOrganization(activeOrganization?.name || resolvedOrganizations[0]?.name || user?.organization || "");
    } else {
      setOrganization(user?.organization || "");
    }
    setDepartment(user?.department || "");
    if (canEditPhone && user && "phone_number" in user) {
      setPhoneNumber(user.phone_number || "");
    } else {
      setPhoneNumber("");
    }
    setDateOfBirth(user?.profile?.date_of_birth || "");
    setNationality(user?.profile?.nationality || "");
    setAddress(user?.profile?.address || "");
    setCity(user?.profile?.city || "");
    setCountry(user?.profile?.country || "");
    setPostalCode(user?.profile?.postal_code || "");
    setJobTitle(user?.profile?.current_job_title || "");
    setYearsOfExperience(
      user?.profile?.years_of_experience != null ? String(user.profile.years_of_experience) : "",
    );
    setLinkedinUrl(user?.profile?.linkedin_url || "");
    setBio(user?.profile?.bio || "");
  }, [activeOrganization?.name, canEditPhone, organizationFieldLocked, resolvedOrganizations, user]);

  useEffect(() => {
    void fetchBillingManagement();
  }, [activeOrganizationId, fetchBillingManagement, user?.email]);

  useEffect(() => {
    void fetchOnboardingState();
  }, [fetchOnboardingState]);

  const handleRefreshProfile = async () => {
    setRefreshing(true);
    try {
      await dispatch(fetchProfile()).unwrap();
      await fetchBillingManagement();
      await fetchOnboardingState();
      toast.success("Profile refreshed.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to refresh profile.";
      toast.error(message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleUpdatePaymentOption = async () => {
    if (!managedSubscription) return;

    if (managedSubscription.provider === "stripe") {
      setBillingActionLoading(true);
      try {
        const response = await billingService.createPaymentMethodUpdateSession();
        if (!response.url) {
          throw new Error("Billing portal URL was not returned.");
        }
        window.location.assign(response.url);
      } catch (error) {
        toast.error(getErrorMessage(error, "Unable to open payment update session."));
      } finally {
        setBillingActionLoading(false);
      }
      return;
    }

    if (managedSubscription.provider !== "sandbox") {
      toast.info("Direct payment option update is currently available only for sandbox subscriptions.");
      return;
    }

    setBillingActionLoading(true);
    try {
      const response = await billingService.updatePaymentMethod(sandboxPaymentMethod);
      setBillingData(response);
      toast.success("Payment option updated.");
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to update payment option."));
    } finally {
      setBillingActionLoading(false);
    }
  };

  const handleRemovePaymentOption = async () => {
    if (!managedSubscription) return;
    const confirmed = window.confirm(
      "This schedules unsubscription at the end of your active billing period. Continue?",
    );
    if (!confirmed) return;

    setBillingActionLoading(true);
    try {
      const response = await billingService.scheduleSubscriptionCancellation();
      setBillingData(response);
      toast.success(response.message || "Cancellation scheduled for end of period.");
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to schedule cancellation."));
    } finally {
      setBillingActionLoading(false);
    }
  };

  const handleRetryPayment = async () => {
    setBillingActionLoading(true);
    try {
      const response = await billingService.retrySubscription();
      if (response.checkout_url) {
        window.location.assign(response.checkout_url);
        return;
      }
      toast.success(response.message || "Payment retry started.");
      await fetchBillingManagement();
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to retry payment."));
    } finally {
      setBillingActionLoading(false);
    }
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      toast.error("Email is required.");
      return;
    }

    const normalizedYears = yearsOfExperience.trim();
    if (normalizedYears) {
      const parsedYears = Number(normalizedYears);
      if (!Number.isFinite(parsedYears) || parsedYears < 0) {
        toast.error("Years of experience must be a non-negative number.");
        return;
      }
    }

    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        email: normalizedEmail,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        organization: (organizationFieldLocked ? activeOrganization?.name || organization : organization).trim(),
        department: department.trim(),
        date_of_birth: dateOfBirth || null,
        nationality: nationality.trim(),
        address: address.trim(),
        city: city.trim(),
        country: country.trim(),
        postal_code: postalCode.trim(),
        current_job_title: jobTitle.trim(),
        years_of_experience: normalizedYears ? Number(normalizedYears) : null,
        linkedin_url: linkedinUrl.trim(),
        bio: bio.trim(),
      };
      if (canEditPhone) {
        payload.phone_number = phoneNumber.trim();
      }
      await dispatch(updateUserProfile(payload)).unwrap();
      await dispatch(fetchProfile()).unwrap();
      toast.success("Settings updated successfully.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to update settings.";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return (
      <div className="mx-auto flex min-h-[55vh] max-w-5xl items-center justify-center px-4">
        <div className="inline-flex items-center gap-2 text-sm text-slate-700">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading account settings...
        </div>
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <UserCog className="h-4 w-4" />
          Profile & Settings
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Account Settings</h1>
        <p className="mt-1 text-sm text-slate-700">
          Manage your identity details and security controls.
        </p>
      </header>

      <section className="mt-5 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Display Name</p>
          <p className="mt-2 text-sm font-bold text-slate-900">{accountName}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Account Type</p>
          <p className="mt-2 text-sm font-bold capitalize text-slate-900">{userType || "unknown"}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Member Since</p>
          <p className="mt-2 text-sm font-bold text-slate-900">{memberSince}</p>
        </div>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-5">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <h2 className="text-lg font-bold text-slate-900">Profile Details</h2>
          <p className="mt-1 text-sm text-slate-700">Update the information used by your organization account.</p>

          <form className="mt-5 space-y-4" onSubmit={handleSave}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="settings-first-name" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  First Name
                </Label>
                <Input
                  id="settings-first-name"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                  placeholder="First name"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-last-name" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Last Name
                </Label>
                <Input
                  id="settings-last-name"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                  placeholder="Last name"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="settings-email" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Email
                </Label>
                <Input
                  id="settings-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="name@company.com"
                  disabled={saving}
                />
              </div>

              {canEditPhone ? (
                <div className="space-y-2">
                  <Label htmlFor="settings-phone" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    Phone Number
                  </Label>
                  <Input
                    id="settings-phone"
                    type="tel"
                    value={phoneNumber}
                    onChange={(event) => setPhoneNumber(event.target.value)}
                    placeholder="+233..."
                    disabled={saving}
                  />
                </div>
              ) : null}

              <div className="space-y-2">
                <Label htmlFor="settings-dob" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Date of Birth
                </Label>
                <Input
                  id="settings-dob"
                  type="date"
                  value={dateOfBirth}
                  onChange={(event) => setDateOfBirth(event.target.value)}
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-organization" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Organization
                </Label>
                <Input
                  id="settings-organization"
                  value={organization}
                  onChange={(event) => setOrganization(event.target.value)}
                  placeholder={organizationFieldLocked ? "Managed by active organization context" : "Organization"}
                  disabled={saving || organizationFieldLocked}
                />
                {organizationFieldLocked ? (
                  <p className="text-[11px] text-slate-700">
                    Organization name is derived from your active organization membership.
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-department" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Department
                </Label>
                <Input
                  id="settings-department"
                  value={department}
                  onChange={(event) => setDepartment(event.target.value)}
                  placeholder="Department"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-nationality" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Nationality
                </Label>
                <Input
                  id="settings-nationality"
                  value={nationality}
                  onChange={(event) => setNationality(event.target.value)}
                  placeholder="Nationality"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-city" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  City
                </Label>
                <Input
                  id="settings-city"
                  value={city}
                  onChange={(event) => setCity(event.target.value)}
                  placeholder="City"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-country" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Country
                </Label>
                <Input
                  id="settings-country"
                  value={country}
                  onChange={(event) => setCountry(event.target.value)}
                  placeholder="Country"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-postal-code" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Postal Code
                </Label>
                <Input
                  id="settings-postal-code"
                  value={postalCode}
                  onChange={(event) => setPostalCode(event.target.value)}
                  placeholder="Postal code"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-job-title" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Current Job Title
                </Label>
                <Input
                  id="settings-job-title"
                  value={jobTitle}
                  onChange={(event) => setJobTitle(event.target.value)}
                  placeholder="Job title"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="settings-experience" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Years of Experience
                </Label>
                <Input
                  id="settings-experience"
                  type="number"
                  min={0}
                  value={yearsOfExperience}
                  onChange={(event) => setYearsOfExperience(event.target.value)}
                  placeholder="e.g. 5"
                  disabled={saving}
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="settings-linkedin" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  LinkedIn URL
                </Label>
                <Input
                  id="settings-linkedin"
                  type="url"
                  value={linkedinUrl}
                  onChange={(event) => setLinkedinUrl(event.target.value)}
                  placeholder="https://www.linkedin.com/in/..."
                  disabled={saving}
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="settings-address" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Address
                </Label>
                <textarea
                  id="settings-address"
                  value={address}
                  onChange={(event) => setAddress(event.target.value)}
                  placeholder="Street address"
                  disabled={saving}
                  className="min-h-20 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="settings-bio" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Bio
                </Label>
                <textarea
                  id="settings-bio"
                  value={bio}
                  onChange={(event) => setBio(event.target.value)}
                  placeholder="Short professional summary"
                  disabled={saving}
                  maxLength={500}
                  className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <Button type="submit" disabled={saving} className="bg-cyan-700 text-white hover:bg-cyan-800">
                {saving ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </span>
                ) : (
                  "Save Changes"
                )}
              </Button>
              <Button type="button" variant="outline" disabled={refreshing || saving} onClick={() => void handleRefreshProfile()}>
                {refreshing ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Refreshing...
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <RefreshCw className="h-4 w-4" />
                    Refresh Profile
                  </span>
                )}
              </Button>
            </div>
          </form>
        </article>

        <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="text-lg font-bold text-slate-900">Security Controls</h2>
          <p className="mt-1 text-sm text-slate-700">
            Access account protection actions and credential updates.
          </p>

          <div className="mt-4 space-y-3">
            {userType !== "applicant" ? (
              <Link
                to="/security"
                className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-cyan-300 hover:bg-cyan-50"
              >
                <ShieldCheck className="mt-0.5 h-5 w-5 text-cyan-700" />
                <span>
                  <span className="block text-sm font-semibold text-slate-900">Two-Factor Security</span>
                  <span className="block text-xs text-slate-700">Manage authenticator and backup codes.</span>
                </span>
              </Link>
            ) : null}

            <Link
              to="/change-password"
              className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-cyan-300 hover:bg-cyan-50"
            >
              <CheckCircle2 className="mt-0.5 h-5 w-5 text-cyan-700" />
              <span>
                <span className="block text-sm font-semibold text-slate-900">Change Password</span>
                <span className="block text-xs text-slate-700">Rotate your account password securely.</span>
              </span>
            </Link>
          </div>

          {canViewBilling ? (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-900">Organization Subscription</h3>
                <CreditCard className="h-4 w-4 text-cyan-700" />
              </div>
              <p className="mt-2 text-[11px] text-slate-700">
                Active organization scope: {activeOrganization?.name || "Default"}
              </p>

              {billingLoading ? (
                <p className="mt-3 text-xs text-slate-700">Loading billing details...</p>
              ) : !managedSubscription ? (
                <div className="mt-3 space-y-3">
                  <p className="text-xs text-slate-700">
                    {billingData?.message || "No active subscription found for this workspace."}
                  </p>
                  {canManageOrganizationBilling ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      onClick={() =>
                        navigate(
                          activeOrganizationId
                            ? "/organization/dashboard"
                            : "/organization/setup?next=/organization/dashboard",
                        )
                      }
                    >
                      Open Organization Billing
                    </Button>
                  ) : (
                    <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                      Subscription management is restricted to organization admins.
                    </p>
                  )}
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-800">
                    <p>
                      <span className="font-semibold">Plan:</span> {managedSubscription.plan_name} (
                      {managedSubscription.billing_cycle})
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Subscription organization:</span>{" "}
                      {managedSubscription.organization_name || managedSubscription.organization_id || "Scoped by active organization"}
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Status:</span> {managedSubscription.status} /{" "}
                      {managedSubscription.payment_status}
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Payment method:</span>{" "}
                      {managedSubscription.payment_method?.display || "Not available"}
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Current period end:</span>{" "}
                      {formatDateTimeLabel(managedSubscription.current_period_end)}
                    </p>
                    {managedSubscription.cancel_at_period_end ? (
                      <p className="mt-1 text-amber-700">
                        Cancellation scheduled for{" "}
                        {formatDateTimeLabel(managedSubscription.cancellation_effective_at)}. Access remains active until then.
                      </p>
                    ) : null}
                  </div>

                  {isSandboxManaged ? (
                    <div className="space-y-2">
                      <Label
                        htmlFor="settings-payment-method"
                        className="text-[11px] font-semibold uppercase tracking-wide text-slate-700"
                      >
                        Change Payment Option
                      </Label>
                      <select
                        id="settings-payment-method"
                        value={sandboxPaymentMethod}
                        onChange={(event) => setSandboxPaymentMethod(event.target.value as PaymentMethodChoice)}
                        disabled={billingActionLoading}
                        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-cyan-400"
                      >
                        <option value="card">Card</option>
                        <option value="bank_transfer">Bank transfer</option>
                        <option value="mobile_money">Mobile money</option>
                      </select>
                    </div>
                  ) : null}

                  {isPaystackManaged ? (
                    <p className="text-[11px] text-slate-700">
                      Paystack payment method updates are handled during checkout retry flow.
                    </p>
                  ) : null}

                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={
                        billingActionLoading ||
                        !managedSubscription.can_update_payment_method ||
                        !canManageOrganizationBilling
                      }
                      onClick={() => void handleUpdatePaymentOption()}
                    >
                      {billingActionLoading
                        ? "Please wait..."
                        : isStripeManaged
                        ? "Update Payment Method"
                        : isSandboxManaged
                        ? "Save Payment Option"
                        : "Update Payment Option"}
                    </Button>

                    <Button
                      type="button"
                      variant="destructive"
                      disabled={
                        billingActionLoading ||
                        !managedSubscription.can_delete_payment_method ||
                        !canManageOrganizationBilling
                      }
                      onClick={() => void handleRemovePaymentOption()}
                    >
                      <Trash2 className="h-4 w-4" />
                      Unsubscribe
                    </Button>

                    {managedSubscription.retry_available ? (
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={billingActionLoading}
                        onClick={() => void handleRetryPayment()}
                      >
                        Retry Payment
                      </Button>
                    ) : null}
                  </div>

                  <p className="text-[11px] text-slate-700">
                    Unsubscribing does not terminate access immediately. Service remains active through the current billing period.
                  </p>
                  {!canManageOrganizationBilling ? (
                    <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                      Organization billing changes are limited to organization admins.
                    </p>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}

          {canManageOrganizationBilling ? (
            <div
              id="organization-onboarding-invite"
              className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-900">Organization Governance Workspace</h3>
                <UsersRound className="h-4 w-4 text-cyan-700" />
              </div>
              <p className="mt-2 text-[11px] text-slate-700">
                Organization billing, onboarding, and governance administration is managed in dedicated organization pages.
              </p>

              {!activeOrganizationId ? (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Select an active organization in the navbar before opening organization governance workspace.
                </div>
              ) : onboardingLoading ? (
                <p className="mt-3 text-xs text-slate-700">Loading onboarding status...</p>
              ) : (
                <div className="mt-3 space-y-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-800">
                    <p>
                      <span className="font-semibold">Organization:</span>{" "}
                      {onboardingState?.organization_name || activeOrganization?.name || "N/A"}
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Subscription active:</span>{" "}
                      {onboardingState?.subscription_active ? "Yes" : "No"}
                    </p>
                    <p className="mt-1">
                      <span className="font-semibold">Active invite link:</span>{" "}
                      {onboardingState?.has_active_token ? "Yes" : "No"}
                    </p>
                    {activeOnboardingToken ? (
                      <>
                        <p className="mt-1">
                          <span className="font-semibold">Token preview:</span>{" "}
                          {activeOnboardingToken.token_preview || "N/A"}
                        </p>
                        <p className="mt-1">
                          <span className="font-semibold">Usage:</span>{" "}
                          {activeOnboardingToken.uses}
                          {activeOnboardingToken.max_uses != null ? ` / ${activeOnboardingToken.max_uses}` : ""}
                          {activeOnboardingToken.remaining_uses != null
                            ? ` (remaining ${activeOnboardingToken.remaining_uses})`
                            : ""}
                        </p>
                        <p className="mt-1">
                          <span className="font-semibold">Expires:</span>{" "}
                          {formatDateTimeLabel(activeOnboardingToken.expires_at)}
                        </p>
                      </>
                    ) : null}
                    {typeof onboardingState?.organization_seat_remaining === "number" ? (
                      <p className="mt-1">
                        <span className="font-semibold">Remaining seats:</span>{" "}
                        {onboardingState.organization_seat_remaining}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => navigate("/organization/dashboard")}
                    >
                      Open Organization Dashboard
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => navigate("/organization/onboarding")}
                    >
                      Open Organization Onboarding Workspace
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={onboardingLoading}
                      onClick={() => void fetchOnboardingState()}
                    >
                      Refresh Invite State
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </aside>
      </section>
    </main>
  );
};

export default UserSettingsPage;

