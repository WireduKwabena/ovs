export type QueryUpdateValue = string | null | undefined;

interface ApplyQueryUpdatesOptions {
  keepPage?: boolean;
  pageParam?: string;
  resetPageTo?: string;
  removableValues?: string[];
}

const DEFAULT_REMOVABLE_VALUES = ["", "all"];

export const normalizeQueryValue = (value: string | null | undefined): string => (value || "").trim();

export const applyQueryUpdates = (
  current: URLSearchParams,
  updates: Record<string, QueryUpdateValue>,
  options: ApplyQueryUpdatesOptions = {},
): URLSearchParams => {
  const {
    keepPage = true,
    pageParam = "page",
    resetPageTo = "1",
    removableValues = DEFAULT_REMOVABLE_VALUES,
  } = options;

  const nextParams = new URLSearchParams(current);
  const removableSet = new Set(removableValues);

  Object.entries(updates).forEach(([key, value]) => {
    if (value === null || value === undefined || removableSet.has(value)) {
      nextParams.delete(key);
      return;
    }
    nextParams.set(key, value);
  });

  if (!keepPage && !Object.prototype.hasOwnProperty.call(updates, pageParam)) {
    nextParams.set(pageParam, resetPageTo);
  }

  return nextParams;
};
