import React from "react";
import { Download, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/helper";

interface ExportActionsProps {
  onCsv?: () => void;
  onJson?: () => void;
  onPdf?: () => void;
  csvLabel?: string;
  jsonLabel?: string;
  pdfLabel?: string;
  csvDisabled?: boolean;
  jsonDisabled?: boolean;
  pdfDisabled?: boolean;
  className?: string;
}

const ExportActions: React.FC<ExportActionsProps> = ({
  onCsv,
  onJson,
  onPdf,
  csvLabel = "Export CSV",
  jsonLabel = "Export JSON",
  pdfLabel = "Print / Save PDF",
  csvDisabled = false,
  jsonDisabled = false,
  pdfDisabled = false,
  className,
}) => {
  if (!onCsv && !onJson && !onPdf) {
    return null;
  }

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {onCsv ? (
        <Button type="button" variant="outline" onClick={onCsv} disabled={csvDisabled}>
          <Download className="mr-2 h-4 w-4" />
          {csvLabel}
        </Button>
      ) : null}
      {onJson ? (
        <Button type="button" variant="outline" onClick={onJson} disabled={jsonDisabled}>
          <Download className="mr-2 h-4 w-4" />
          {jsonLabel}
        </Button>
      ) : null}
      {onPdf ? (
        <Button type="button" variant="outline" onClick={onPdf} disabled={pdfDisabled}>
          <FileText className="mr-2 h-4 w-4" />
          {pdfLabel}
        </Button>
      ) : null}
    </div>
  );
};

export default ExportActions;
