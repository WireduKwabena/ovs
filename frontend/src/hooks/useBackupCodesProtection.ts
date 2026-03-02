import { useEffect, useMemo, useRef, useState } from "react";
import { useBeforeUnload, useBlocker } from "react-router-dom";

import type { BackupCodesAttentionState } from "@/components/security/BackupCodesAttentionBadge";

const DEFAULT_WARNING_MESSAGE =
  "Backup codes are still unacknowledged. Leave this page anyway? You may lose this one-time view.";

type UseBackupCodesProtectionOptions = {
  warningMessage?: string;
};

type UseBackupCodesProtectionResult = {
  issuedBackupCodes: string[] | null;
  backupCodesAcknowledged: boolean;
  backupCodesAttentionState: BackupCodesAttentionState;
  shouldGuardNavigation: boolean;
  revealBackupCodes: (codes: string[]) => void;
  clearBackupCodes: () => void;
  setBackupCodesAcknowledged: (value: boolean) => void;
  confirmLeaveIfNeeded: () => boolean;
};

export const useBackupCodesProtection = (
  options: UseBackupCodesProtectionOptions = {},
): UseBackupCodesProtectionResult => {
  const warningMessage = options.warningMessage || DEFAULT_WARNING_MESSAGE;
  const [issuedBackupCodes, setIssuedBackupCodes] = useState<string[] | null>(null);
  const [backupCodesAcknowledged, setBackupCodesAcknowledged] = useState(false);
  const isPromptingNavigationRef = useRef(false);

  const shouldGuardNavigation = Boolean(issuedBackupCodes?.length) && !backupCodesAcknowledged;
  const blocker = useBlocker(shouldGuardNavigation);

  const backupCodesAttentionState: BackupCodesAttentionState = useMemo(() => {
    if (!issuedBackupCodes?.length) {
      return null;
    }
    return backupCodesAcknowledged ? "acknowledged" : "pending";
  }, [issuedBackupCodes, backupCodesAcknowledged]);

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
    if (blocker.state !== "blocked" || isPromptingNavigationRef.current) {
      return;
    }

    isPromptingNavigationRef.current = true;
    const shouldLeave = window.confirm(warningMessage);
    if (shouldLeave) {
      blocker.proceed();
    } else {
      blocker.reset();
    }
    isPromptingNavigationRef.current = false;
  }, [blocker, warningMessage]);

  const revealBackupCodes = (codes: string[]) => {
    setIssuedBackupCodes(codes);
    setBackupCodesAcknowledged(false);
  };

  const clearBackupCodes = () => {
    setIssuedBackupCodes(null);
    setBackupCodesAcknowledged(false);
  };

  const confirmLeaveIfNeeded = () => {
    if (!shouldGuardNavigation) {
      return true;
    }
    return window.confirm(warningMessage);
  };

  return {
    issuedBackupCodes,
    backupCodesAcknowledged,
    backupCodesAttentionState,
    shouldGuardNavigation,
    revealBackupCodes,
    clearBackupCodes,
    setBackupCodesAcknowledged,
    confirmLeaveIfNeeded,
  };
};

export default useBackupCodesProtection;
