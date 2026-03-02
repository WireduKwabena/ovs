import React from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

export type BackupCodesAttentionState = "pending" | "acknowledged" | null;

type BackupCodesAttentionBadgeProps = {
  state: BackupCodesAttentionState;
};

export const BackupCodesAttentionBadge: React.FC<BackupCodesAttentionBadgeProps> = ({ state }) => {
  if (state === "pending") {
    return (
      <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900">
        <AlertTriangle className="h-3.5 w-3.5" />
        Backup codes shown and not acknowledged yet
      </div>
    );
  }

  if (state === "acknowledged") {
    return (
      <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Backup codes acknowledged
      </div>
    );
  }

  return null;
};

export default BackupCodesAttentionBadge;
