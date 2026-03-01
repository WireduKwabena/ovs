import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, KeyRound, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";

import type { TwoFactorStatusResponse } from "@/types";
import { authService } from "@/services/auth.service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProvisioningQrCard } from "@/components/security/ProvisioningQrCard";
import { EmergencyBackupCodesCard } from "@/components/security/EmergencyBackupCodesCard";

const SecurityPage: React.FC = () => {
  const [status, setStatus] = useState<TwoFactorStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const [enableOtp, setEnableOtp] = useState("");

  const [regenerateMode, setRegenerateMode] = useState<"otp" | "backup">("otp");
  const [regenerateFactor, setRegenerateFactor] = useState("");
  const [issuedBackupCodes, setIssuedBackupCodes] = useState<string[] | null>(null);

  const [busyAction, setBusyAction] = useState<"setup" | "enable" | "regenerate" | null>(null);

  const refreshStatus = async () => {
    setLoadingStatus(true);
    setStatusError(null);
    try {
      const response = await authService.getTwoFactorStatus();
      setStatus(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load security status.";
      setStatusError(message);
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, []);

  const formattedRegenerateBackupCode = useMemo(() => {
    const normalized = regenerateFactor.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
    if (normalized.length <= 4) {
      return normalized;
    }
    return `${normalized.slice(0, 4)}-${normalized.slice(4)}`;
  }, [regenerateFactor]);

  const handleSetup = async () => {
    setBusyAction("setup");
    try {
      const response = await authService.setupTwoFactor();
      setProvisioningUri(response.provisioning_uri);
      setIssuedBackupCodes(null);
      toast.success("Authenticator setup created. Scan the URI and verify with OTP.");
      await refreshStatus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to setup authenticator.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleEnable = async (event: React.FormEvent) => {
    event.preventDefault();
    const normalizedOtp = enableOtp.trim().replace(/\D/g, "").slice(0, 6);
    if (!/^\d{6}$/.test(normalizedOtp)) {
      toast.error("Enter a valid 6-digit OTP.");
      return;
    }

    setBusyAction("enable");
    try {
      await authService.enableTwoFactor(normalizedOtp);
      toast.success("2FA enabled successfully.");
      setEnableOtp("");
      setProvisioningUri(null);
      await refreshStatus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to enable 2FA.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleRegenerate = async (event: React.FormEvent) => {
    event.preventDefault();

    const normalizedOtp = regenerateFactor.trim().replace(/\D/g, "").slice(0, 6);
    const normalizedBackupCode = regenerateFactor.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();

    if (regenerateMode === "otp" && !/^\d{6}$/.test(normalizedOtp)) {
      toast.error("Enter a valid 6-digit OTP.");
      return;
    }

    if (regenerateMode === "backup" && normalizedBackupCode.length < 6) {
      toast.error("Enter a valid backup code.");
      return;
    }

    setBusyAction("regenerate");
    try {
      const response = await authService.regenerateBackupCodes(
        regenerateMode === "otp"
          ? { otp: normalizedOtp }
          : { backup_code: normalizedBackupCode.length > 4 ? `${normalizedBackupCode.slice(0, 4)}-${normalizedBackupCode.slice(4)}` : normalizedBackupCode },
      );
      setIssuedBackupCodes(response.backup_codes);
      setRegenerateFactor("");
      toast.success("Backup codes regenerated. Save them now.");
      await refreshStatus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to regenerate backup codes.");
    } finally {
      setBusyAction(null);
    }
  };

  if (loadingStatus) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-5xl items-center justify-center px-4">
        <div className="inline-flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading security status...
        </div>
      </div>
    );
  }

  if (statusError || !status) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-800">
          <p className="font-semibold">Unable to load security settings</p>
          <p className="mt-1 text-sm">{statusError || "Unknown error"}</p>
          <Button type="button" size="sm" className="mt-4" onClick={() => void refreshStatus()}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <ShieldCheck className="h-4 w-4" />
          Security
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Account Security</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manage authenticator setup, 2FA state, and backup recovery codes.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">2FA Required</p>
          <p className="mt-2 text-sm font-bold text-slate-900">{status.two_factor_required ? "Yes" : "No"}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">2FA Enabled</p>
          <p className="mt-2 text-sm font-bold text-slate-900">{status.is_two_factor_enabled ? "Enabled" : "Not enabled"}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Backup Codes</p>
          <p className="mt-2 text-sm font-bold text-slate-900">{status.backup_codes_remaining} remaining</p>
        </div>
      </div>

      {status.applicant_exempt ? (
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Applicants are exempt from account-level 2FA in this system.
        </div>
      ) : (
        <>
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Authenticator Setup</h2>
            <p className="mt-1 text-sm text-slate-600">
              Start setup to generate a provisioning URI for your authenticator app.
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                type="button"
                onClick={handleSetup}
                disabled={busyAction !== null}
                className="bg-cyan-700 text-white hover:bg-cyan-800"
              >
                {busyAction === "setup" ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </span>
                ) : (
                  "Generate Provisioning URI"
                )}
              </Button>
              <Button type="button" variant="outline" onClick={() => void refreshStatus()} disabled={busyAction !== null}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh Status
              </Button>
            </div>

            {provisioningUri ? (
              <div className="mt-4">
                <ProvisioningQrCard uri={provisioningUri} />
              </div>
            ) : null}

            {!status.is_two_factor_enabled ? (
              <form onSubmit={handleEnable} className="mt-5 space-y-3">
                <Label htmlFor="enable-otp" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Verify OTP to enable 2FA
                </Label>
                <Input
                  id="enable-otp"
                  value={enableOtp}
                  onChange={(event) => setEnableOtp(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  placeholder="123456"
                  className="max-w-xs"
                  disabled={busyAction !== null}
                />
                <Button type="submit" disabled={busyAction !== null} className="bg-slate-900 text-white hover:bg-slate-800">
                  {busyAction === "enable" ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Enabling...
                    </span>
                  ) : (
                    "Enable 2FA"
                  )}
                </Button>
              </form>
            ) : (
              <div className="mt-5 inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">
                <ShieldCheck className="h-4 w-4" />
                2FA is active for this account.
              </div>
            )}
          </div>

          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Backup Recovery Codes</h2>
            <p className="mt-1 text-sm text-slate-600">
              Regenerate backup codes using either your OTP or one existing backup code.
            </p>

            {!status.is_two_factor_enabled ? (
              <div className="mt-4 inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <AlertTriangle className="h-4 w-4" />
                Enable 2FA first to manage backup codes.
              </div>
            ) : (
              <form onSubmit={handleRegenerate} className="mt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <Label htmlFor="regenerate-factor" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                    {regenerateMode === "otp" ? "Authenticator OTP" : "Backup Code"}
                  </Label>
                  <button
                    type="button"
                    className="text-xs font-semibold text-cyan-700 hover:text-cyan-800"
                    onClick={() => {
                      setRegenerateMode((mode) => (mode === "otp" ? "backup" : "otp"));
                      setRegenerateFactor("");
                    }}
                    disabled={busyAction !== null}
                  >
                    {regenerateMode === "otp" ? "Use backup code instead" : "Use OTP instead"}
                  </button>
                </div>
                <Input
                  id="regenerate-factor"
                  value={regenerateMode === "otp" ? regenerateFactor : formattedRegenerateBackupCode}
                  onChange={(event) => {
                    if (regenerateMode === "otp") {
                      setRegenerateFactor(event.target.value.replace(/\D/g, "").slice(0, 6));
                    } else {
                      setRegenerateFactor(event.target.value.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(0, 12));
                    }
                  }}
                  placeholder={regenerateMode === "otp" ? "123456" : "ABCD-EFGH"}
                  className="max-w-xs"
                  disabled={busyAction !== null}
                />
                <Button type="submit" disabled={busyAction !== null} className="bg-cyan-700 text-white hover:bg-cyan-800">
                  {busyAction === "regenerate" ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Regenerating...
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <KeyRound className="h-4 w-4" />
                      Regenerate Backup Codes
                    </span>
                  )}
                </Button>
              </form>
            )}

            {issuedBackupCodes?.length ? (
              <div className="mt-4">
                <EmergencyBackupCodesCard codes={issuedBackupCodes} />
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
};

export default SecurityPage;
