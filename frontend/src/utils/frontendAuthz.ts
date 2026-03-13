export const GOVERNMENT_WORKFLOW_CAPABILITIES = [
  "gams.registry.manage",
  "gams.appointment.stage",
  "gams.appointment.decide",
  "gams.appointment.publish",
  "gams.appointment.view_internal",
] as const;

export const APPOINTMENT_ROUTE_CAPABILITIES = [...GOVERNMENT_WORKFLOW_CAPABILITIES] as const;

export const REGISTRY_ROUTE_CAPABILITIES = ["gams.registry.manage"] as const;

// Campaign lifecycle management follows registry authority, not generic stage actors.
export const CAMPAIGN_MANAGE_CAPABILITIES = ["gams.registry.manage"] as const;

export const RUBRIC_MANAGE_CAPABILITIES = [
  "gams.registry.manage",
] as const;

export const INTERNAL_WORKFLOW_ROUTE_CAPABILITIES = [
  "gams.registry.manage",
  "gams.appointment.stage",
  "gams.appointment.decide",
  "gams.appointment.publish",
  "gams.appointment.view_internal",
] as const;

export const APPOINTMENT_WORKFLOW_ROLES = [
  "registry_admin",
  "vetting_officer",
  "committee_member",
  "committee_chair",
  "appointing_authority",
  "publication_officer",
  "auditor",
] as const;

export const STAGE_ACTOR_ROLES = [
  "vetting_officer",
  "committee_member",
  "committee_chair",
  "appointing_authority",
  "registry_admin",
] as const;

export const FINAL_DECISION_ROLES = ["appointing_authority"] as const;

export const PUBLICATION_ROLES = ["publication_officer", "appointing_authority"] as const;

export const STAGE_HISTORY_ROLES = ["committee_member", "committee_chair"] as const;

// Legacy fallback is restricted to true platform admins only.
// ``internal`` remains a legacy identity marker but no longer grants
// capability fallback for governance-sensitive UI access.
export const LEGACY_CAPABILITY_STALE_FALLBACK_USER_TYPES = ["admin"] as const;

type UserType = "applicant" | "internal" | "admin" | null | undefined;

export const hasAnyCapability = (capabilities: readonly string[], required: readonly string[]): boolean => {
  if (!Array.isArray(capabilities) || capabilities.length === 0) {
    return false;
  }
  return required.some((capability) => capabilities.includes(capability));
};

export const hasAnyRole = (roles: readonly string[], required: readonly string[]): boolean => {
  if (!Array.isArray(roles) || roles.length === 0) {
    return false;
  }
  return required.some((role) => roles.includes(role));
};

export const shouldUseLegacyCapabilityFallback = (params: {
  userType: UserType;
  capabilities: readonly string[];
}): boolean => {
  if (params.userType !== "admin") {
    return false;
  }
  return !Array.isArray(params.capabilities) || params.capabilities.length === 0;
};

