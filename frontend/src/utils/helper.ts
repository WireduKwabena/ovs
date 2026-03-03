// src/utils/helpers.ts (Updated - Add getScoreBg Export)
import { format, formatDistanceToNow } from 'date-fns';
import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), 'MMM dd, yyyy');
}

export function formatDateTime(date: string | Date): string {
  return format(new Date(date), 'MMM dd, yyyy HH:mm');
}

export function formatRelativeTime(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

export function getScoreColor(score: number): string {
  if (score >= 85) return 'text-green-600';
  if (score >= 70) return 'text-amber-700';
  return 'text-red-600';
}

export function getScoreBg(score: number): string {  // New export - matches component need
  if (score >= 85) return 'bg-green-50';
  if (score >= 70) return 'bg-amber-50';
  return 'bg-red-50';
}

export function getProgressBarColor(score: number): string {
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-amber-600';
  return 'bg-red-500';
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function downloadFile(url: string, filename: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.target = '_blank';  // For CORS/S3
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function downloadTextFile(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export async function copyTextToClipboard(content: string): Promise<void> {
  await navigator.clipboard.writeText(content);
}

export function printCurrentPage(targetWindow: Window = window): void {
  targetWindow.print();
}

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export function printBackupCodes(codes: string[], generatedIso: string = new Date().toISOString()): void {
  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=900,height=700");
  if (!printWindow) {
    throw new Error("Unable to open print window.");
  }

  const escapedCodes = codes.map((code) => `<li>${escapeHtml(code)}</li>`).join("");
  const escapedGeneratedAt = escapeHtml(generatedIso);

  printWindow.document.write(`
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>OVS Backup Recovery Codes</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 24px; color: #111827; }
          h1 { margin: 0 0 8px; font-size: 20px; }
          p { margin: 0 0 12px; color: #374151; }
          .warn { margin: 12px 0 16px; padding: 10px 12px; border: 1px solid #f59e0b; background: #fffbeb; border-radius: 8px; }
          ul { columns: 2; -webkit-columns: 2; -moz-columns: 2; gap: 20px; list-style: none; padding: 0; }
          li { font-family: "Courier New", monospace; border: 1px solid #d1d5db; padding: 6px 8px; border-radius: 6px; margin-bottom: 8px; }
        </style>
      </head>
      <body>
        <h1>OVS Backup Recovery Codes</h1>
        <p>Generated: ${escapedGeneratedAt}</p>
        <div class="warn">Store these codes securely. Each code can be used only once.</div>
        <ul>${escapedCodes}</ul>
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
}
