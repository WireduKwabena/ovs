// Shared auth utility functions used by useAuth.ts and ProtectedRoute.tsx.
// Centralising here avoids duplicating the merge logic in both consumers.

type UserWithRoles = {
  roles?: string[];
  group_roles?: string[];
  capabilities?: string[];
} | null;

/**
 * Merge roles from the Redux store slice (top-level `roles` field) and the
 * `user` object's `roles` / `group_roles` fields, deduplicating the result.
 */
export const mergeRolesFromStore = (
  roles: unknown,
  user: UserWithRoles,
): string[] =>
  Array.from(
    new Set([
      ...(Array.isArray(roles) ? roles : []),
      ...(user?.roles ?? []),
      ...(user?.group_roles ?? []),
    ]),
  );

/**
 * Merge capabilities from the Redux store slice (top-level `capabilities`
 * field) and the `user` object's `capabilities` field, deduplicating the result.
 */
export const mergeCapabilitiesFromStore = (
  capabilities: unknown,
  user: UserWithRoles,
): string[] =>
  Array.from(
    new Set([
      ...(Array.isArray(capabilities) ? capabilities : []),
      ...(user?.capabilities ?? []),
    ]),
  );
