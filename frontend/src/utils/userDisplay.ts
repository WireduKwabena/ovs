import type { AdminUser, User } from "@/types";

type KnownUser = User | AdminUser | null | undefined;

const hasNonEmptyValue = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;

export const getUserDisplayName = (user: KnownUser, fallback = "User"): string => {
  if (!user) return fallback;

  if ("first_name" in user && "last_name" in user) {
    const first = hasNonEmptyValue(user.first_name) ? user.first_name.trim() : "";
    const last = hasNonEmptyValue(user.last_name) ? user.last_name.trim() : "";
    const combined = `${first} ${last}`.trim();
    if (combined.length > 0) {
      return combined;
    }
  }

  if ("full_name" in user && hasNonEmptyValue(user.full_name)) {
    return user.full_name.trim();
  }

  if ("email" in user && hasNonEmptyValue(user.email)) {
    return user.email.trim();
  }

  return fallback;
};

export const getUserInitial = (user: KnownUser, fallback = "U"): string => {
  const normalizedFallback = hasNonEmptyValue(fallback) ? fallback[0].toUpperCase() : "U";
  const displayName = getUserDisplayName(user, normalizedFallback);
  return displayName.charAt(0).toUpperCase() || normalizedFallback;
};
