export const PLATFORM_ADMIN_BASE_PATH = "/admin/platform";
export const ORG_ADMIN_BASE_PATH = "/admin/org";
export const WORKSPACE_BASE_PATH = "/workspace";
export const CANDIDATE_BASE_PATH = "/candidate";

export const getPlatformAdminPath = (segment = "dashboard"): string =>
  `${PLATFORM_ADMIN_BASE_PATH}/${segment}`;

export const getOrgAdminBasePath = (organizationId: string): string =>
  `${ORG_ADMIN_BASE_PATH}/${encodeURIComponent(String(organizationId || "").trim())}`;

export const getOrgAdminPath = (organizationId: string, segment = "dashboard"): string =>
  `${getOrgAdminBasePath(organizationId)}/${segment}`;

export const getWorkspacePath = (segment = "home"): string =>
  `${WORKSPACE_BASE_PATH}/${segment}`;

export const getCandidatePath = (segment = "home"): string =>
  `${CANDIDATE_BASE_PATH}/${segment}`;

export const getOrganizationSetupPath = (nextPath?: string): string => {
  if (!nextPath) {
    return "/organization/setup";
  }

  return `/organization/setup?next=${encodeURIComponent(nextPath)}`;
};
