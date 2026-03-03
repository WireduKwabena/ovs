import { downloadBlobFile } from "@/utils/csv";

export const toJsonString = (data: unknown, spacing: number = 2): string =>
  `${JSON.stringify(data, null, spacing)}\n`;

export const toJsonBlob = (data: unknown, spacing: number = 2): Blob =>
  new Blob([toJsonString(data, spacing)], { type: "application/json;charset=utf-8;" });

export const downloadJsonFile = (data: unknown, filename: string, spacing: number = 2): void => {
  downloadBlobFile(toJsonBlob(data, spacing), filename);
};
