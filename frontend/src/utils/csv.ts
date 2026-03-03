export type CsvCell = string | number | boolean | null | undefined | Date;
export type CsvRow = CsvCell[];

const normalizeCsvCell = (value: CsvCell): string => {
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value ?? "");
};

const escapeCsvCell = (value: CsvCell): string => {
  const text = normalizeCsvCell(value).replace(/"/g, "\"\"");
  return `"${text}"`;
};

export const toCsvString = (header: CsvRow, rows: CsvRow[]): string => {
  return [header, ...rows].map((row) => row.map(escapeCsvCell).join(",")).join("\n");
};

export const toCsvBlob = (header: CsvRow, rows: CsvRow[]): Blob => {
  return new Blob([toCsvString(header, rows)], { type: "text/csv;charset=utf-8;" });
};

export const downloadBlobFile = (blob: Blob, filename: string): void => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

export const downloadCsvFile = (header: CsvRow, rows: CsvRow[], filename: string): void => {
  downloadBlobFile(toCsvBlob(header, rows), filename);
};

export const isoDateStamp = (date: Date = new Date()): string => date.toISOString().slice(0, 10);
