import React from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { VerificationFactorMode } from "@/hooks/useVerificationFactorInput";

type VerificationFactorFieldProps = {
  id: string;
  mode: VerificationFactorMode;
  value: string;
  onValueChange: (nextValue: string) => void;
  onToggleMode: () => void;
  disabled?: boolean;
  labelOtp?: string;
  labelBackup?: string;
  toggleToBackupText?: string;
  toggleToOtpText?: string;
  otpPlaceholder?: string;
  backupPlaceholder?: string;
  inputClassName?: string;
  wrapperClassName?: string;
};

export const VerificationFactorField: React.FC<VerificationFactorFieldProps> = ({
  id,
  mode,
  value,
  onValueChange,
  onToggleMode,
  disabled = false,
  labelOtp = "Authenticator OTP",
  labelBackup = "Backup Code",
  toggleToBackupText = "Use backup code instead",
  toggleToOtpText = "Use OTP instead",
  otpPlaceholder = "123456",
  backupPlaceholder = "ABCD-EFGH",
  inputClassName,
  wrapperClassName,
}) => {
  return (
    <div className={cn("space-y-2", wrapperClassName)}>
      <div className="flex items-center justify-between">
        <Label htmlFor={id} className="text-xs font-semibold uppercase tracking-wide text-slate-700">
          {mode === "otp" ? labelOtp : labelBackup}
        </Label>
        <button
          type="button"
          onClick={onToggleMode}
          className="text-xs font-semibold text-cyan-700 hover:text-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
        >
          {mode === "otp" ? toggleToBackupText : toggleToOtpText}
        </button>
      </div>
      <Input
        id={id}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        inputMode={mode === "otp" ? "numeric" : "text"}
        autoComplete={mode === "otp" ? "one-time-code" : "off"}
        placeholder={mode === "otp" ? otpPlaceholder : backupPlaceholder}
        className={inputClassName}
        disabled={disabled}
      />
    </div>
  );
};

export default VerificationFactorField;
