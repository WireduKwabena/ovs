import React from "react";
import { AlertTriangle, Copy, Download, Printer } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { copyTextToClipboard, downloadTextFile, printBackupCodes } from "@/utils/helper";

type EmergencyBackupCodesCardProps = {
  codes: string[];
  title?: string;
  requireConfirmation?: boolean;
  acknowledged?: boolean;
  onAcknowledgedChange?: (value: boolean) => void;
};

export const EmergencyBackupCodesCard: React.FC<EmergencyBackupCodesCardProps> = ({
  codes,
  title = "Emergency Backup Codes",
  requireConfirmation = false,
  acknowledged = false,
  onAcknowledgedChange,
}) => {
  const generatedIso = new Date().toISOString();

  const downloadCodes = () => {
    const timestamp = generatedIso.replace(/[:]/g, "-").slice(0, 19);
    const content = [
      "CAVP Backup Recovery Codes",
      `Generated: ${generatedIso}`,
      "",
      "Store these securely. Each code can be used only once.",
      "",
      ...codes,
      "",
    ].join("\n");

    downloadTextFile(content, `cavp-backup-codes-${timestamp}.txt`);
    toast.success("Backup codes downloaded.");
  };

  const copyCodes = async () => {
    try {
      await copyTextToClipboard(codes.join("\n"));
      toast.success("Backup codes copied.");
    } catch {
      toast.error("Failed to copy backup codes.");
    }
  };

  const printCodes = () => {
    try {
      printBackupCodes(codes, generatedIso);
      toast.success("Print dialog opened.");
    } catch {
      toast.error("Failed to open print dialog.");
    }
  };

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1">
            This is the only time these codes are shown. Save them in a secure password manager or offline vault.
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-800">
        {codes.map((code) => (
          <div key={code} className="rounded border border-amber-200 bg-white px-2 py-1">
            {code}
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={copyCodes}>
          <Copy className="mr-2 h-4 w-4" />
          Copy all
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={downloadCodes}>
          <Download className="mr-2 h-4 w-4" />
          Download .txt
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={printCodes}>
          <Printer className="mr-2 h-4 w-4" />
          Print
        </Button>
      </div>

      {requireConfirmation ? (
        <label className="mt-3 inline-flex items-start gap-2 text-[11px] text-amber-950">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-amber-400 text-cyan-700 focus:ring-cyan-600"
            checked={acknowledged}
            onChange={(event) => onAcknowledgedChange?.(event.target.checked)}
          />
          <span>I saved these backup codes securely and understand each code can be used once.</span>
        </label>
      ) : null}
    </div>
  );
};

export default EmergencyBackupCodesCard;
