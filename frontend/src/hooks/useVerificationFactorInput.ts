import { useMemo, useState } from "react";

export type VerificationFactorMode = "otp" | "backup";

type VerificationErrorMessages = {
  otp?: string;
  backup?: string;
};

type UseVerificationFactorInputOptions = {
  initialMode?: VerificationFactorMode;
  otpLength?: number;
  backupMinLength?: number;
  backupMaxLength?: number;
};

type UseVerificationFactorInputResult = {
  mode: VerificationFactorMode;
  displayValue: string;
  otpValue: string;
  backupCanonical: string;
  backupCodeForApi: string;
  setFromInput: (nextInput: string) => void;
  toggleModeReset: () => void;
  clear: () => void;
  getValidationError: (messages?: VerificationErrorMessages) => string | null;
  getPayload: () => { otp: string } | { backup_code: string };
};

const formatBackupCode = (value: string): string => {
  if (value.length <= 4) {
    return value;
  }
  return `${value.slice(0, 4)}-${value.slice(4)}`;
};

export const useVerificationFactorInput = (
  options: UseVerificationFactorInputOptions = {},
): UseVerificationFactorInputResult => {
  const otpLength = options.otpLength ?? 6;
  const backupMinLength = options.backupMinLength ?? 6;
  const backupMaxLength = options.backupMaxLength ?? 12;
  const [mode, setMode] = useState<VerificationFactorMode>(options.initialMode ?? "otp");
  const [canonicalValue, setCanonicalValue] = useState("");

  const otpValue = useMemo(
    () => canonicalValue.replace(/\D/g, "").slice(0, otpLength),
    [canonicalValue, otpLength],
  );
  const backupCanonical = useMemo(
    () => canonicalValue.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(0, backupMaxLength),
    [canonicalValue, backupMaxLength],
  );
  const backupCodeForApi = useMemo(
    () => formatBackupCode(backupCanonical),
    [backupCanonical],
  );
  const displayValue = mode === "otp" ? otpValue : backupCodeForApi;

  const setFromInput = (nextInput: string) => {
    if (mode === "otp") {
      setCanonicalValue(nextInput.replace(/\D/g, "").slice(0, otpLength));
      return;
    }
    setCanonicalValue(nextInput.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(0, backupMaxLength));
  };

  const toggleModeReset = () => {
    setMode((current) => (current === "otp" ? "backup" : "otp"));
    setCanonicalValue("");
  };
  const clear = () => {
    setCanonicalValue("");
  };

  const getValidationError = (messages?: VerificationErrorMessages) => {
    if (mode === "otp" && !new RegExp(`^\\d{${otpLength}}$`).test(otpValue)) {
      return messages?.otp || "Enter a valid OTP code.";
    }

    if (mode === "backup" && backupCanonical.length < backupMinLength) {
      return messages?.backup || "Enter a valid backup code.";
    }

    return null;
  };

  const getPayload = () => {
    if (mode === "otp") {
      return { otp: otpValue };
    }
    return { backup_code: backupCodeForApi };
  };

  return {
    mode,
    displayValue,
    otpValue,
    backupCanonical,
    backupCodeForApi,
    setFromInput,
    toggleModeReset,
    clear,
    getValidationError,
    getPayload,
  };
};

export default useVerificationFactorInput;
