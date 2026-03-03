import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Loader2, RefreshCw, ShieldCheck, UserCog } from "lucide-react";
import { useDispatch } from "react-redux";
import { toast } from "react-toastify";

import type { AppDispatch } from "@/app/store";
import { useAuth } from "@/hooks/useAuth";
import { fetchProfile, updateUserProfile } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getUserDisplayName } from "@/utils/userDisplay";

const UserSettingsPage: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { user, userType } = useAuth();

  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

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

  useEffect(() => {
    setEmail(user?.email || "");
    if (canEditPhone && user && "phone_number" in user) {
      setPhoneNumber(user.phone_number || "");
    } else {
      setPhoneNumber("");
    }
  }, [canEditPhone, user]);

  const handleRefreshProfile = async () => {
    setRefreshing(true);
    try {
      await dispatch(fetchProfile()).unwrap();
      toast.success("Profile refreshed.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to refresh profile.";
      toast.error(message);
    } finally {
      setRefreshing(false);
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

    setSaving(true);
    try {
      const payload: Record<string, string> = { email: normalizedEmail };
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
            <div className="space-y-2">
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
        </aside>
      </section>
    </main>
  );
};

export default UserSettingsPage;

