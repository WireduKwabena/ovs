const ORG_ADMIN_MEMBERSHIP_ROLES = new Set([
  "registry_admin",
  "org_admin",
  "organization_admin",
  "system_admin",
]);

const ORG_ADMIN_ROLES = new Set([
  "registry_admin",
  "org_admin",
  "organization_admin",
  "system_admin",
  "admin",
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
  roles?: string[];
  memberships: OrganizationMembershipLike[];
  activeOrganizationId: string | null;
}): boolean => {
  const resolvedRoles = Array.isArray(params.roles) ? params.roles : [];
  const resolvedMemberships = Array.isArray(params.memberships) ? params.memberships : [];
  const activeOrganizationId = String(params.activeOrganizationId || "").trim();
  const normalizedRoles = new Set(resolvedRoles.map((role) => normalizeMembershipRole(role)));
  const hasOrgAdminRoleClaim = Array.from(normalizedRoles).some((role) =>
    ORG_ADMIN_ROLES.has(role),
  );
  const activeMemberships = resolvedMemberships.filter((membership) => Boolean(membership?.is_active));

  if (params.isAdmin) {
    return true;
  }

  if (activeOrganizationId) {
    const hasAnyActiveMembershipInOrganization = activeMemberships.some(
      (membership) => String(membership.organization_id || "").trim() === activeOrganizationId,
    );
    if (!hasAnyActiveMembershipInOrganization) {
      return false;
    }

    const hasOrgAdminMembershipInOrganization = activeMemberships.some((membership) => {
      if (!membership?.is_active) {
        return false;
      }
      if (String(membership.organization_id || "").trim() !== activeOrganizationId) {
        return false;
      }
      return ORG_ADMIN_MEMBERSHIP_ROLES.has(normalizeMembershipRole(membership.membership_role));
    });

    if (hasOrgAdminMembershipInOrganization) {
      return true;
    }

    // Backward-safe fallback: explicit org-admin role claims still require active
    // membership in the target org; broad capability alone is not sufficient.
    return hasOrgAdminRoleClaim && hasAnyActiveMembershipInOrganization;
  }

  // Fallback for users who have org-admin membership but haven't selected active org yet.
  if (
    activeMemberships.some(
      (membership) =>
        ORG_ADMIN_MEMBERSHIP_ROLES.has(normalizeMembershipRole(membership.membership_role)),
    )
  ) {
    return true;
  }

  // Role fallback remains bounded by active membership to avoid overexposure.
  return (
    hasOrgAdminRoleClaim &&
    activeMemberships.some(
      (membership) =>
        Boolean(membership?.is_active) &&
        String(membership.organization_id || "").trim().length > 0,
    )
  );
};
