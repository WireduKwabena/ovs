import React from "react";
import { Copy, QrCode } from "lucide-react";
import { toast } from "react-toastify";
import { QRCodeSVG } from "qrcode.react";

type ProvisioningQrCardProps = {
  uri: string;
  title?: string;
  description?: string;
  showRawUri?: boolean;
};

export const ProvisioningQrCard: React.FC<ProvisioningQrCardProps> = ({
  uri,
  title = "Scan with Authenticator",
  description = "Open your authenticator app and scan this QR code.",
  showRawUri = true,
}) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(uri);
      toast.success("Provisioning URI copied.");
    } catch {
      toast.error("Failed to copy provisioning URI.");
    }
  };

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-slate-800">
      <div className="flex items-center gap-2 text-amber-900">
        <QrCode className="h-4 w-4" />
        <p className="font-semibold">{title}</p>
      </div>
      <p className="mt-1 text-[11px] text-amber-900">{description}</p>

      <div className="mt-3 flex flex-col items-center gap-3 rounded-lg border border-amber-200 bg-white p-3 sm:flex-row sm:items-start">
        <div className="rounded-md border border-slate-200 bg-white p-2">
          <QRCodeSVG value={uri} size={140} includeMargin />
        </div>

        {showRawUri ? (
          <div className="w-full">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-700">Provisioning URI</p>
            <div className="mt-1 max-h-28 overflow-auto break-all rounded border border-slate-200 bg-slate-50 px-2 py-2 font-mono text-[10px] text-slate-700">
              {uri}
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className="mt-2 inline-flex items-center gap-2 rounded-md border border-slate-700 bg-white px-2 py-1 text-[11px] font-semibold text-slate-900 hover:bg-slate-100"
            >
              <Copy className="h-3.5 w-3.5" />
              Copy URI
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default ProvisioningQrCard;
