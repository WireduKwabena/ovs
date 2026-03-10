const ORG_ADMIN_MEMBERSHIP_ROLES = new Set([
  "registry_admin",
  "org_admin",
  "organization_admin",
  "system_admin",
]);

export type OrganizationMembershipLike = {
  organization_id?: string | null;
  membership_role?: string | null;
  is_active?: boolean | null;
};

const normalizeMembershipRole = (value: string | null | undefined): string =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");

export const canManageOrganizationGovernance = (params: {
  isAdmin: boolean;
  capabilities: string[];
  memberships: OrganizationMembershipLike[];
  activeOrganizationId: string | null;
}): boolean => {
  const resolvedCapabilities = Array.isArray(params.capabilities) ? params.capabilities : [];
  const resolvedMemberships = Array.isArray(params.memberships) ? params.memberships : [];
  const activeOrganizationId = String(params.activeOrganizationId || "").trim();

  if (params.isAdmin) {
    return true;
  }

  if (resolvedCapabilities.includes("gams.registry.manage")) {
    return true;
  }

  if (activeOrganizationId) {
    return resolvedMemberships.some((membership) => {
      if (!membership?.is_active) {
        return false;
      }
      if (String(membership.organization_id || "").trim() !== activeOrganizationId) {
        return false;
      }
      return ORG_ADMIN_MEMBERSHIP_ROLES.has(normalizeMembershipRole(membership.membership_role));
    });
  }

  // Fallback for users who have org-admin membership but haven't selected active org yet.
  return resolvedMemberships.some(
    (membership) =>
      Boolean(membership?.is_active) &&
      ORG_ADMIN_MEMBERSHIP_ROLES.has(normalizeMembershipRole(membership.membership_role)),
  );
};

