export type AuthUserType = "applicant" | "hr_manager" | "admin" | null | undefined;

export const getDashboardPathForUser = (userType: AuthUserType): string => {
  if (userType === "admin") {
    return "/admin/dashboard";
  }
  if (userType === "applicant") {
    return "/candidate/access";
  }
  return "/dashboard";
};

export const hasActiveTwoFactorChallenge = (
  twoFactorRequired: boolean,
  twoFactorToken: string | null | undefined,
): boolean => {
  return Boolean(twoFactorRequired && twoFactorToken);
};

export const resolveProtectedRouteRedirect = (params: {
  isAuthenticated: boolean;
  twoFactorRequired: boolean;
  twoFactorToken: string | null | undefined;
}): string | null => {
  const { isAuthenticated, twoFactorRequired, twoFactorToken } = params;

  if (hasActiveTwoFactorChallenge(twoFactorRequired, twoFactorToken)) {
    return "/login/2fa";
  }

  if (!isAuthenticated) {
    return "/login";
  }

  return null;
};

export const resolveUnauthenticatedRouteRedirect = (params: {
  isAuthenticated: boolean;
  userType: AuthUserType;
  allowTwoFactorChallenge?: boolean;
  twoFactorRequired: boolean;
  twoFactorToken: string | null | undefined;
}): string | null => {
  const {
    isAuthenticated,
    userType,
    allowTwoFactorChallenge = false,
    twoFactorRequired,
    twoFactorToken,
  } = params;

  if (
    !allowTwoFactorChallenge &&
    hasActiveTwoFactorChallenge(twoFactorRequired, twoFactorToken)
  ) {
    return "/login/2fa";
  }

  if (isAuthenticated) {
    return getDashboardPathForUser(userType);
  }

  return null;
};
