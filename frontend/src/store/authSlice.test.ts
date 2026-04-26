import { beforeEach, describe, expect, it } from "vitest";

import type { LoginResponse, ProfileResponse, User } from "@/types";

import reducer, {
  adminLogin,
  fetchProfile,
  setOrganizationSlug,
  switchActiveOrganization,
} from "./authSlice";

const buildUser = (overrides: Partial<User> = {}): User => ({
  id: "user-1",
  email: "operator@example.com",
  first_name: "Operator",
  last_name: "User",
  full_name: "Operator User",
  phone_number: "+1234567890",
  profile_picture_url: "",
  avatar_url: "",
  date_of_birth: "1990-01-01",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const buildProfileResponse = (
  overrides: Partial<ProfileResponse> = {},
): ProfileResponse => ({
  user: buildUser(),
  user_type: "internal",
  roles: [],
  capabilities: [],
  organizations: [],
  organization_memberships: [],
  committees: [],
  active_organization: null,
  active_organization_source: "none",
  invalid_requested_organization_id: "",
  ...overrides,
});

describe("authSlice organization slug synchronization", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("syncs the tenant slug to the active organization after switching organizations", () => {
    const initialState = reducer(undefined, { type: "@@INIT" });
    const stateWithSlug = reducer(initialState, setOrganizationSlug("org-one"));

    const nextState = reducer(
      stateWithSlug,
      switchActiveOrganization.fulfilled(
        buildProfileResponse({
          organizations: [
            {
              id: "org-1",
              code: "org-one",
              name: "Organization One",
              organization_type: "agency",
            },
            {
              id: "org-2",
              code: "org-two",
              name: "Organization Two",
              organization_type: "agency",
            },
          ],
          active_organization: {
            id: "org-2",
            code: "org-two",
            name: "Organization Two",
            organization_type: "agency",
          },
          active_organization_source: "session",
        }),
        "request-1",
        "org-2",
      ),
    );

    expect(nextState.organizationSlug).toBe("org-two");
    expect(nextState.activeOrganization?.id).toBe("org-2");
    expect(sessionStorage.getItem("organization_slug")).toBe("org-two");
  });

  it("derives the tenant slug from a single available organization during profile hydration", () => {
    const initialState = reducer(undefined, { type: "@@INIT" });
    const stateWithSlug = reducer(initialState, setOrganizationSlug("stale-org"));

    const nextState = reducer(
      stateWithSlug,
      fetchProfile.fulfilled(
        buildProfileResponse({
          organizations: [
            {
              id: "org-1",
              code: "org-one",
              name: "Organization One",
              organization_type: "agency",
            },
          ],
          active_organization: null,
        }),
        "request-2",
        undefined,
      ),
    );

    expect(nextState.organizationSlug).toBe("org-one");
    expect(sessionStorage.getItem("organization_slug")).toBe("org-one");
  });

  it("clears tenant slug state when a platform admin session is established", () => {
    const initialState = reducer(undefined, { type: "@@INIT" });
    const stateWithSlug = reducer(initialState, setOrganizationSlug("member-org"));

    const nextState = reducer(
      stateWithSlug,
      adminLogin.fulfilled(
        {
          user: buildUser({
            email: "admin@example.com",
            full_name: "Platform Admin",
            first_name: "Platform",
            last_name: "Admin",
            is_staff: true,
            is_superuser: true,
            user_type: "platform_admin",
          }),
          tokens: {
            access: "access-token",
            refresh: "refresh-token",
          },
          user_type: "platform_admin",
        } satisfies LoginResponse,
        "request-3",
        {
          email: "admin@example.com",
          password: "password",
        },
      ),
    );

    expect(nextState.organizationSlug).toBeNull();
    expect(sessionStorage.getItem("organization_slug")).toBeNull();
  });
});
