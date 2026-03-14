import { describe, expect, it } from "vitest";

import { canManageOrganizationGovernance } from "./organizationGovernance";

describe("canManageOrganizationGovernance", () => {
  it("denies platform admin without memberships", () => {
    expect(
      canManageOrganizationGovernance({
        isAdmin: true,
        roles: [],
        memberships: [],
        activeOrganizationId: "org-1",
      }),
    ).toBe(false);
  });

  it("allows org-admin membership in active organization", () => {
    expect(
      canManageOrganizationGovernance({
        isAdmin: false,
        roles: [],
        memberships: [
          {
            organization_id: "org-1",
            membership_role: "registry_admin",
            is_active: true,
          },
        ],
        activeOrganizationId: "org-1",
      }),
    ).toBe(true);
  });

  it("denies plain internal capability-only access without governance membership", () => {
    expect(
      canManageOrganizationGovernance({
        isAdmin: false,
        roles: [],
        memberships: [
          {
            organization_id: "org-1",
            membership_role: "member",
            is_active: true,
          },
        ],
        activeOrganizationId: "org-1",
      }),
    ).toBe(false);
  });

  it("denies committee member access to org-admin governance workspace", () => {
    expect(
      canManageOrganizationGovernance({
        isAdmin: false,
        roles: ["committee_member"],
        memberships: [
          {
            organization_id: "org-1",
            membership_role: "committee_member",
            is_active: true,
          },
        ],
        activeOrganizationId: "org-1",
      }),
    ).toBe(false);
  });
});

