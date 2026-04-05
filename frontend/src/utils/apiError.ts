const NON_FIELD_KEYS = new Set(["non_field_errors", "__all__", "detail", "message", "error"]);
const META_KEYS = new Set([
  "status",
  "status_code",
  "code",
  "type",
  "title",
  "instance",
  "traceback",
  "errors",
]);

const normalizeMessage = (value: string): string => value.replace(/\s+/g, " ").trim();

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const collectMessages = (value: unknown, depth = 0): string[] => {
  if (value == null || depth > 4) {
    return [];
  }

  if (typeof value === "string") {
    const message = normalizeMessage(value);
    return message ? [message] : [];
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }

  if (value instanceof Error) {
    return value.message ? [normalizeMessage(value.message)] : [];
  }

  if (Array.isArray(value)) {
    return value.flatMap((entry) => collectMessages(entry, depth + 1));
  }

  const record = toRecord(value);
  if (!record) {
    return [];
  }

  for (const key of ["message", "detail", "error", "non_field_errors", "__all__"]) {
    if (key in record) {
      const prioritized = collectMessages(record[key], depth + 1);
      if (prioritized.length) {
        return prioritized;
      }
    }
  }

  if ("errors" in record) {
    const nestedErrors = collectMessages(record.errors, depth + 1);
    if (nestedErrors.length) {
      return nestedErrors;
    }
  }

  const fieldMessages: string[] = [];
  for (const [key, rawValue] of Object.entries(record)) {
    if (META_KEYS.has(key)) {
      continue;
    }

    const messages = collectMessages(rawValue, depth + 1);
    if (!messages.length) {
      continue;
    }

    if (NON_FIELD_KEYS.has(key)) {
      fieldMessages.push(messages[0]);
      continue;
    }

    const label = key.replace(/_/g, " ");
    fieldMessages.push(`${label}: ${messages[0]}`);
  }

  return fieldMessages;
};

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  const axiosLike = toRecord(error);
  const responseData = axiosLike?.response && toRecord(axiosLike.response)
    ? (toRecord(axiosLike.response) as Record<string, unknown>).data
    : null;

  const candidates: unknown[] = [];
  if (responseData != null) {
    candidates.push(responseData);
  }
  candidates.push(error);

  for (const candidate of candidates) {
    const messages = collectMessages(candidate);
    if (messages.length) {
      return messages[0];
    }
  }

  return fallback;
};

/**
 * Converts a caught value into a standard Error with a human-readable message
 * extracted from the Axios response payload (if present).
 * Use this as the single `toServiceError` helper across service files.
 */
export const toServiceError = (error: unknown, fallback: string): Error => {
  const message = getApiErrorMessage(error, fallback);
  if (error instanceof Error) {
    error.message = message;
    return error;
  }
  return new Error(message);
};
