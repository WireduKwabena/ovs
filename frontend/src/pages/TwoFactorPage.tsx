import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useBeforeUnload, useBlocker, useLocation, useNavigate } from "react-router-dom";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";
import { useDispatch, useSelector } from "react-redux";

import type { AppDispatch, RootState } from "@/app/store";
import { clearError, clearTwoFactorChallenge, verifyTwoFactor } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProvisioningQrCard } from "@/components/security/ProvisioningQrCard";
import { EmergencyBackupCodesCard } from "@/components/security/EmergencyBackupCodesCard";

export const TwoFactorPage: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const location = useLocation();

  const {
    twoFactorRequired,
    twoFactorToken,
    twoFactorSetupRequired,
    twoFactorProvisioningUri,
    twoFactorExpiresInSeconds,
    twoFactorMessage,
    loading,
    error,
  } = useSelector((state: RootState) => state.auth);

  const [factorMode, setFactorMode] = useState<"otp" | "backup">("otp");
  const [factorValue, setFactorValue] = useState("");
  const [issuedBackupCodes, setIssuedBackupCodes] = useState<string[] | null>(null);
  const [backupCodesAcknowledged, setBackupCodesAcknowledged] = useState(false);
  const [redirectAfterBackupCodes, setRedirectAfterBackupCodes] = useState<string | null>(null);
  const isPromptingNavigationRef = useRef(false);

  const requestedPath = useMemo(
    () => (location.state as { from?: { pathname?: string } } | null)?.from?.pathname,
    [location.state],
  );
  const shouldGuardNavigation = Boolean(issuedBackupCodes?.length) && !backupCodesAcknowledged;
  const navigationWarningMessage =
    "Backup codes are still unacknowledged. Leave this page anyway? You may lose this one-time view.";
  const blocker = useBlocker(shouldGuardNavigation);

  useBeforeUnload(
    useMemo(
      () => (event: BeforeUnloadEvent) => {
        if (!shouldGuardNavigation) {
          return;
        }

        event.preventDefault();
        event.returnValue = "";
      },
      [shouldGuardNavigation],
    ),
  );

  useEffect(() => {
    if (!twoFactorRequired || !twoFactorToken) {
      navigate("/login", { replace: true });
    }
  }, [navigate, twoFactorRequired, twoFactorToken]);

  useEffect(() => {
    if (!error) {
      return;
    }

    toast.error(error, { toastId: `two-factor-${error}` });

    if (/expired|already used/i.test(error)) {
      dispatch(clearTwoFactorChallenge());
      navigate("/login", { replace: true });
    }
  }, [dispatch, error, navigate]);

  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  useEffect(() => {
    if (blocker.state !== "blocked" || isPromptingNavigationRef.current) {
      return;
    }

    isPromptingNavigationRef.current = true;
    const shouldLeave = window.confirm(navigationWarningMessage);
    if (shouldLeave) {
      blocker.proceed();
    } else {
      blocker.reset();
    }
    isPromptingNavigationRef.current = false;
  }, [blocker, navigationWarningMessage]);

  const handleVerify = async (event: React.FormEvent) => {
    event.preventDefault();

    const rawValue = factorValue.trim();
    const normalizedOtp = rawValue.replace(/\D/g, "").slice(0, 6);
    const normalizedBackupCode = rawValue.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();

    if (factorMode === "otp" && !/^\d{6}$/.test(normalizedOtp)) {
      toast.error("Enter the 6-digit authenticator code.");
      return;
    }

    if (factorMode === "backup" && normalizedBackupCode.length < 6) {
      toast.error("Enter a valid backup code.");
      return;
    }

    if (!twoFactorToken || loading) {
      return;
    }

    try {
      const payload =
        factorMode === "otp"
          ? { token: twoFactorToken, otp: normalizedOtp }
          : {
              token: twoFactorToken,
              backup_code:
                normalizedBackupCode.length > 4
                  ? `${normalizedBackupCode.slice(0, 4)}-${normalizedBackupCode.slice(4)}`
                  : normalizedBackupCode,
            };

      const response = await dispatch(verifyTwoFactor(payload)).unwrap();

      toast.success("2FA verification successful.");

      const defaultPath = response.user_type === "admin" ? "/admin/dashboard" : "/dashboard";
      const redirectPath = requestedPath && requestedPath !== "/" ? requestedPath : defaultPath;

      if (response.backup_codes?.length) {
        setIssuedBackupCodes(response.backup_codes);
        setBackupCodesAcknowledged(false);
        setRedirectAfterBackupCodes(redirectPath);
        return;
      }

      navigate(redirectPath, { replace: true });
    } catch {
      // handled by slice + toast effect
    }
  };

  const handleBackToLogin = () => {
    if (shouldGuardNavigation && !window.confirm(navigationWarningMessage)) {
      return;
    }
    dispatch(clearTwoFactorChallenge());
    navigate("/login", { replace: true });
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)]">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <ShieldCheck className="h-4 w-4" />
          Two-Factor Authentication
        </div>

        <h1 className="text-3xl font-black tracking-tight text-slate-900">Verify Your Login</h1>
        <p className="mt-2 text-sm text-slate-600">
          {twoFactorMessage || "Enter the 6-digit code from your authenticator app."}
        </p>
        {twoFactorExpiresInSeconds ? (
          <p className="mt-1 text-xs text-slate-500">
            This challenge expires in about {Math.max(1, Math.floor(twoFactorExpiresInSeconds / 60))} minute(s).
          </p>
        ) : null}

        {twoFactorSetupRequired && (
          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
            <p className="font-semibold">Authenticator setup required</p>
            <p className="mt-1">
              Scan the provisioning URI below in your authenticator app, then enter the generated code.
            </p>
            {twoFactorProvisioningUri ? (
              <div className="mt-2">
                <ProvisioningQrCard
                  uri={twoFactorProvisioningUri}
                  title="Scan Before Verifying"
                  description="Scan this QR code in your authenticator app, then enter the OTP below."
                />
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-amber-800">
                Provisioning URI is unavailable. Contact support if this persists.
              </p>
            )}
          </div>
        )}

        <form onSubmit={handleVerify} className="mt-6 space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="factor" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                {factorMode === "otp" ? "One-Time Password (OTP)" : "Backup Code"}
              </Label>
              <button
                type="button"
                onClick={() => {
                  setFactorMode((mode) => (mode === "otp" ? "backup" : "otp"));
                  setFactorValue("");
                }}
                className="text-xs font-semibold text-cyan-700 hover:text-cyan-800"
              >
                {factorMode === "otp" ? "Use backup code instead" : "Use authenticator code"}
              </button>
            </div>
            <Input
              id="factor"
              value={factorValue}
              onChange={(event) => {
                const incoming = event.target.value;
                if (factorMode === "otp") {
                  setFactorValue(incoming.replace(/\D/g, "").slice(0, 6));
                  return;
                }

                const normalized = incoming.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(0, 12);
                if (normalized.length <= 4) {
                  setFactorValue(normalized);
                  return;
                }
                setFactorValue(`${normalized.slice(0, 4)}-${normalized.slice(4)}`);
              }}
              inputMode={factorMode === "otp" ? "numeric" : "text"}
              autoComplete={factorMode === "otp" ? "one-time-code" : "off"}
              placeholder={factorMode === "otp" ? "123456" : "ABCD-EFGH"}
              className="h-12 rounded-xl border border-slate-300 bg-slate-50 px-4 text-center text-lg tracking-[0.3em]"
              disabled={loading}
            />
          </div>

          {issuedBackupCodes?.length ? (
            <div className="space-y-3">
              <EmergencyBackupCodesCard
                codes={issuedBackupCodes}
                requireConfirmation
                acknowledged={backupCodesAcknowledged}
                onAcknowledgedChange={setBackupCodesAcknowledged}
              />
              <Button
                type="button"
                size="sm"
                disabled={!backupCodesAcknowledged}
                className="bg-cyan-700 text-white hover:bg-cyan-800 disabled:opacity-50"
                onClick={() => {
                  navigate(redirectAfterBackupCodes || "/dashboard", { replace: true });
                }}
              >
                I saved them, continue
              </Button>
            </div>
          ) : null}

          <Button
            type="submit"
            size="lg"
            disabled={loading || Boolean(issuedBackupCodes?.length)}
            className="h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white transition hover:bg-cyan-800"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Verifying...
              </span>
            ) : (
              <span className="inline-flex items-center gap-2">
                <KeyRound className="h-4 w-4" />
                Verify and Continue
              </span>
            )}
          </Button>
        </form>

        <div className="mt-4 flex items-center justify-between text-xs">
          <button
            type="button"
            onClick={handleBackToLogin}
            className="font-semibold text-slate-600 hover:text-slate-900"
          >
            Back to Login
          </button>

          <Link to="/forgot-password" className="font-semibold text-cyan-700 hover:text-cyan-800">
            Forgot password?
          </Link>
        </div>
      </div>
    </div>
  );
};

export default TwoFactorPage;
