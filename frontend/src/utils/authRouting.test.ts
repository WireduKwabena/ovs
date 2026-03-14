import { describe, expect, it } from "vitest";

import {
  getDashboardPathForUser,
  hasActiveTwoFactorChallenge,
  resolveProtectedRouteRedirect,
  resolveUnauthenticatedRouteRedirect,
} from "./authRouting";

describe("authRouting", () => {
  describe("getDashboardPathForUser", () => {
    it("returns the platform dashboard path for admins", () => {
      expect(getDashboardPathForUser("admin")).toBe("/admin/platform/dashboard");
    });

    it("returns the shared dashboard resolver path for internal non-admin roles", () => {
      expect(getDashboardPathForUser("internal")).toBe("/dashboard");
      expect(getDashboardPathForUser(null)).toBe("/dashboard");
    });

    it("returns candidate home path for applicant users", () => {
      expect(getDashboardPathForUser("applicant")).toBe("/candidate/home");
    });
  });

  describe("hasActiveTwoFactorChallenge", () => {
    it("is true only when challenge is required and token is present", () => {
      expect(hasActiveTwoFactorChallenge(true, "token")).toBe(true);
      expect(hasActiveTwoFactorChallenge(true, "")).toBe(false);
      expect(hasActiveTwoFactorChallenge(false, "token")).toBe(false);
      expect(hasActiveTwoFactorChallenge(false, null)).toBe(false);
    });
  });

  describe("resolveProtectedRouteRedirect", () => {
    it("redirects to 2FA when challenge is active", () => {
      expect(
        resolveProtectedRouteRedirect({
          isAuthenticated: false,
          twoFactorRequired: true,
          twoFactorToken: "challenge",
        }),
      ).toBe("/login/2fa");
    });

    it("redirects to login when not authenticated and no 2FA challenge", () => {
      expect(
        resolveProtectedRouteRedirect({
          isAuthenticated: false,
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBe("/login");
    });

    it("allows protected route when authenticated and no challenge", () => {
      expect(
        resolveProtectedRouteRedirect({
          isAuthenticated: true,
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBeNull();
    });
  });

  describe("resolveUnauthenticatedRouteRedirect", () => {
    it("redirects active 2FA challenge to /login/2fa when not allowed", () => {
      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: false,
          userType: null,
          allowTwoFactorChallenge: false,
          twoFactorRequired: true,
          twoFactorToken: "challenge",
        }),
      ).toBe("/login/2fa");
    });

    it("does not redirect active 2FA challenge when explicitly allowed", () => {
      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: false,
          userType: null,
          allowTwoFactorChallenge: true,
          twoFactorRequired: true,
          twoFactorToken: "challenge",
        }),
      ).toBeNull();
    });

    it("redirects authenticated users to role dashboard", () => {
      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: true,
          userType: "admin",
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBe("/admin/platform/dashboard");

      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: true,
          userType: "internal",
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBe("/dashboard");

      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: true,
          userType: "applicant",
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBe("/candidate/home");
      });

    it("allows unauthenticated requests without 2FA challenge", () => {
      expect(
        resolveUnauthenticatedRouteRedirect({
          isAuthenticated: false,
          userType: null,
          twoFactorRequired: false,
          twoFactorToken: null,
        }),
      ).toBeNull();
    });
  });
});

