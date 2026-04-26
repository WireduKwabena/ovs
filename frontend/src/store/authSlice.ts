import {
  createAsyncThunk,
  createSlice,
  type PayloadAction,
} from "@reduxjs/toolkit";

import { authService } from "../services/auth.service";

// Key used to persist the refresh token in sessionStorage so a page refresh
// doesn't immediately log the user out. sessionStorage is per-tab and cleared
// when the browser session ends, which is a reasonable security tradeoff.
export const REFRESH_TOKEN_SESSION_KEY = "auth_refresh_token";
import {
  type AdminUser,
  type ApiError,
  type AuthTokens,
  type CommitteeContext,
  type LoginAttemptResponse,
  type LoginCredentials,
  type LoginResponse,
  type OrganizationMembershipContext,
  type OrganizationSummary,
  type ProfileResponse,
  type RegisterData,
  type RegisterResponse,
  type TwoFactorChallengeResponse,
  type User,
} from "../types";
import { getApiErrorMessage } from "@/utils/apiError";

// ---------------------------------------------------------------------------
// Tenant resolution types
// ---------------------------------------------------------------------------

export interface TenantResolutionResult {
  login_type: "admin" | "member";
  schema?: string;
  organization_slug?: string;
  organization_name?: string;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

interface AuthState {
  user: User | AdminUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  userType: 'applicant' | 'internal' | 'org_admin' | 'platform_admin' | 'admin' | null;
  roles: string[];
  capabilities: string[];
  organizations: OrganizationSummary[];
  organizationMemberships: OrganizationMembershipContext[];
  committees: CommitteeContext[];
  activeOrganization: OrganizationSummary | null;
  activeOrganizationSource: string;
  invalidRequestedOrganizationId: string;
  loading: boolean;
  switchingActiveOrganization: boolean;
  error: string | null;
  passwordResetEmailSent: boolean;
  twoFactorRequired: boolean;
  twoFactorToken: string | null;
  twoFactorSetupRequired: boolean;
  twoFactorProvisioningUri: string | null;
  twoFactorExpiresInSeconds: number | null;
  twoFactorMessage: string | null;
  // Tenant context — set during login flow, cleared on logout
  organizationSlug: string | null;
  resolvedLoginType: "admin" | "member" | null;
  // True while silentRefresh is in-flight; prevents ProtectedRoute from
  // redirecting to /login before the page-refresh session restore completes.
  silentRefreshPending: boolean;
}

const initialState: AuthState = {
  user: null,
  tokens: null,
  isAuthenticated: false,
  userType: null,
  roles: [],
  capabilities: [],
  loading: false,
  switchingActiveOrganization: false,
  error: null,
  passwordResetEmailSent: false,
  twoFactorRequired: false,
  twoFactorToken: null,
  twoFactorSetupRequired: false,
  twoFactorProvisioningUri: null,
  twoFactorExpiresInSeconds: null,
  twoFactorMessage: null,
  organizations: [],
  organizationMemberships: [],
  committees: [],
  activeOrganization: null,
  activeOrganizationSource: "none",
  invalidRequestedOrganizationId: "",
  organizationSlug: null,
  resolvedLoginType: null,
  silentRefreshPending: false,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const resolveUserType = (
  payload: {
    user_type?: string;
    user: User | AdminUser;
    active_organization?: unknown;
    is_platform_admin?: boolean;
  }
): AuthState["userType"] => {
  const { user, user_type: payloadType, is_platform_admin } = payload;

  if (is_platform_admin === true || user.is_superuser === true) {
    return 'platform_admin';
  }

  const typeHint = payloadType || (user as { user_type?: string }).user_type;

  if (typeHint === 'admin' || typeHint === 'platform_admin') {
    return 'platform_admin';
  }

  if (typeHint === 'org_admin') {
    return 'org_admin';
  }

  return (typeHint as AuthState["userType"]) || null;
};

const isTwoFactorChallenge = (
  payload: LoginAttemptResponse,
): payload is TwoFactorChallengeResponse => {
  return !("tokens" in payload);
};

const clearTwoFactorState = (state: AuthState) => {
  state.twoFactorRequired = false;
  state.twoFactorToken = null;
  state.twoFactorSetupRequired = false;
  state.twoFactorProvisioningUri = null;
  state.twoFactorExpiresInSeconds = null;
  state.twoFactorMessage = null;
};

const clearSessionState = (state: AuthState) => {
  state.user = null;
  state.tokens = null;
  state.isAuthenticated = false;
  state.userType = null;
  state.roles = [];
  state.capabilities = [];
  state.organizations = [];
  state.organizationMemberships = [];
  state.committees = [];
  state.activeOrganization = null;
  state.activeOrganizationSource = "none";
  state.invalidRequestedOrganizationId = "";
  state.organizationSlug = null;
  state.resolvedLoginType = null;
  state.silentRefreshPending = false;
  clearTwoFactorState(state);
  sessionStorage.removeItem(REFRESH_TOKEN_SESSION_KEY);
};

const normalizeStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return Array.from(
    new Set(
      value
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  );
};

const normalizeOrganizationSummary = (value: unknown): OrganizationSummary | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  if (!id) return null;
  return {
    id,
    code: String(record.code ?? "").trim(),
    name: String(record.name ?? "").trim(),
    organization_type: String(record.organization_type ?? "").trim(),
  };
};

const normalizeOrganizationSummaryList = (value: unknown): OrganizationSummary[] => {
  if (!Array.isArray(value)) return [];
  const deduped = new Map<string, OrganizationSummary>();
  for (const item of value) {
    const normalized = normalizeOrganizationSummary(item);
    if (!normalized) continue;
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

const normalizeOrganizationMembership = (value: unknown): OrganizationMembershipContext | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  const organizationId = String(record.organization_id ?? "").trim();
  if (!id || !organizationId) return null;
  return {
    id,
    organization_id: organizationId,
    organization_code: String(record.organization_code ?? "").trim(),
    organization_name: String(record.organization_name ?? "").trim(),
    organization_type: String(record.organization_type ?? "").trim(),
    title: String(record.title ?? "").trim(),
    membership_role: String(record.membership_role ?? "").trim(),
    is_default: Boolean(record.is_default),
    is_active: Boolean(record.is_active),
    joined_at: record.joined_at == null ? null : String(record.joined_at),
    left_at: record.left_at == null ? null : String(record.left_at),
  };
};

const normalizeOrganizationMembershipList = (value: unknown): OrganizationMembershipContext[] => {
  if (!Array.isArray(value)) return [];
  const deduped = new Map<string, OrganizationMembershipContext>();
  for (const item of value) {
    const normalized = normalizeOrganizationMembership(item);
    if (!normalized) continue;
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

const normalizeCommitteeContext = (value: unknown): CommitteeContext | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  const committeeId = String(record.committee_id ?? "").trim();
  if (!id || !committeeId) return null;
  return {
    id,
    committee_id: committeeId,
    committee_code: String(record.committee_code ?? "").trim(),
    committee_name: String(record.committee_name ?? "").trim(),
    committee_type: String(record.committee_type ?? "").trim(),
    organization_id: String(record.organization_id ?? "").trim(),
    organization_code: String(record.organization_code ?? "").trim(),
    organization_name: String(record.organization_name ?? "").trim(),
    committee_role: String(record.committee_role ?? "").trim(),
    can_vote: Boolean(record.can_vote),
    joined_at: record.joined_at == null ? null : String(record.joined_at),
    left_at: record.left_at == null ? null : String(record.left_at),
  };
};

const normalizeCommitteeContextList = (value: unknown): CommitteeContext[] => {
  if (!Array.isArray(value)) return [];
  const deduped = new Map<string, CommitteeContext>();
  for (const item of value) {
    const normalized = normalizeCommitteeContext(item);
    if (!normalized) continue;
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

const EMPTY_ORG_CONTEXT = {
  organizations: [],
  organization_memberships: [],
  committees: [],
  active_organization: null,
  active_organization_source: "none",
  invalid_requested_organization_id: "",
} as const;

const persistOrganizationSlug = (slug: string | null): string | null => {
  const normalized = String(slug ?? "").trim();
  if (normalized) {
    sessionStorage.setItem("organization_slug", normalized);
    return normalized;
  }
  sessionStorage.removeItem("organization_slug");
  return null;
};

const shouldClearOrganizationSlug = (payload: {
  user?: User | AdminUser;
  user_type?: unknown;
}): boolean => {
  const userType =
    typeof payload.user_type === "string"
      ? payload.user_type
      : typeof (payload.user as { user_type?: unknown } | undefined)?.user_type === "string"
        ? String((payload.user as { user_type?: unknown }).user_type)
        : "";
  return (
    userType === "admin" ||
    userType === "platform_admin" ||
    Boolean(payload.user?.is_superuser)
  );
};

const syncOrganizationSlugFromPayload = (
  state: AuthState,
  payload: {
    user?: User | AdminUser;
    user_type?: unknown;
    organizations?: unknown;
    organization_memberships?: unknown;
    active_organization?: unknown;
  },
) => {
  if (shouldClearOrganizationSlug(payload)) {
    state.organizationSlug = persistOrganizationSlug(null);
    return;
  }

  const activeOrganization = normalizeOrganizationSummary(payload.active_organization);
  if (activeOrganization?.code) {
    state.organizationSlug = persistOrganizationSlug(activeOrganization.code);
    return;
  }

  const organizations = normalizeOrganizationSummaryList(payload.organizations);
  if (organizations.length === 1 && organizations[0]?.code) {
    state.organizationSlug = persistOrganizationSlug(organizations[0].code);
    return;
  }

  const membershipCodes = Array.from(
    new Set(
      normalizeOrganizationMembershipList(payload.organization_memberships)
        .map((membership) => membership.organization_code)
        .filter((code) => code.length > 0),
    ),
  );
  if (membershipCodes.length === 1) {
    state.organizationSlug = persistOrganizationSlug(membershipCodes[0]);
    return;
  }

  state.organizationSlug = persistOrganizationSlug(state.organizationSlug);
};

const applyOrganizationContext = (
  state: AuthState,
  payload: {
    organizations?: unknown;
    organization_memberships?: unknown;
    committees?: unknown;
    active_organization?: unknown;
    active_organization_source?: unknown;
    invalid_requested_organization_id?: unknown;
  },
) => {
  state.organizations = normalizeOrganizationSummaryList(payload.organizations);
  state.organizationMemberships = normalizeOrganizationMembershipList(payload.organization_memberships);
  state.committees = normalizeCommitteeContextList(payload.committees);
  state.activeOrganization = normalizeOrganizationSummary(payload.active_organization);
  state.activeOrganizationSource =
    typeof payload.active_organization_source === "string"
      ? payload.active_organization_source
      : "none";
  state.invalidRequestedOrganizationId =
    typeof payload.invalid_requested_organization_id === "string"
      ? payload.invalid_requested_organization_id
      : "";
};

const resolveRoles = (payload: {
  roles?: unknown;
  group_roles?: unknown;
  user?: User | AdminUser;
}): string[] => {
  const fromPayload = normalizeStringArray(payload.roles);
  if (fromPayload.length > 0) return fromPayload;
  const fromPayloadGroups = normalizeStringArray(payload.group_roles);
  if (fromPayloadGroups.length > 0) return fromPayloadGroups;
  const fromUserRoles = normalizeStringArray((payload.user as (User & { roles?: unknown }) | undefined)?.roles);
  if (fromUserRoles.length > 0) return fromUserRoles;
  return normalizeStringArray((payload.user as (User & { group_roles?: unknown }) | undefined)?.group_roles);
};

const resolveCapabilities = (payload: {
  capabilities?: unknown;
  user?: User | AdminUser;
}): string[] => {
  const fromPayload = normalizeStringArray(payload.capabilities);
  if (fromPayload.length > 0) return fromPayload;
  return normalizeStringArray((payload.user as (User & { capabilities?: unknown }) | undefined)?.capabilities);
};

// ---------------------------------------------------------------------------
// Thunks
// ---------------------------------------------------------------------------

/**
 * Resolve which tenant/schema an email belongs to.
 * Called before login to determine the correct endpoint and institution slug.
 */
export const resolveTenant = createAsyncThunk<
  TenantResolutionResult,
  string,
  { rejectValue: ApiError }
>("auth/resolveTenant", async (email, { rejectWithValue }) => {
  try {
    // Use fetch directly to avoid the api.ts interceptor injecting a slug
    // before we know which slug to use.
    const response = await fetch("/api/v1/auth/resolve-tenant/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.toLowerCase().trim() }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return rejectWithValue({
        message: data?.error || "No account found for this email address.",
      });
    }
    return (await response.json()) as TenantResolutionResult;
  } catch {
    return rejectWithValue({ message: "Unable to reach the server. Please try again." });
  }
});

/**
 * Login for org members and org admins (tenant schema).
 * Requires institutionSlug to be set in state first (via resolveTenant).
 */
export const login = createAsyncThunk<
  LoginAttemptResponse,
  LoginCredentials,
  { rejectValue: ApiError }
>("/api/auth/login/", async (credentials, { rejectWithValue }) => {
  try {
    return await authService.login(credentials);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Login failed") });
  }
});

/**
 * Login for platform/system admins (public schema).
 * Does NOT inject X-Organization-Slug — hits public schema directly.
 */
export const adminLogin = createAsyncThunk<
  LoginAttemptResponse,
  LoginCredentials,
  { rejectValue: ApiError }
>("auth/adminLogin", async (credentials, { rejectWithValue }) => {
  try {
    return await authService.adminLogin(credentials);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Login failed") });
  }
});

export const verifyTwoFactor = createAsyncThunk<
  LoginResponse,
  { token: string; otp?: string; backup_code?: string },
  { rejectValue: ApiError }
>("/auth/login/verify/", async (payload, { rejectWithValue }) => {
  try {
    return await authService.verifyTwoFactor(payload);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Two-factor verification failed") });
  }
});

export const adminVerifyTwoFactor = createAsyncThunk<
  LoginResponse,
  { token: string; otp?: string; backup_code?: string },
  { rejectValue: ApiError }
>("auth/adminVerifyTwoFactor", async (payload, { rejectWithValue }) => {
  try {
    return await authService.adminVerifyTwoFactor(payload);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Two-factor verification failed") });
  }
});

export const register = createAsyncThunk<
  RegisterResponse,
  RegisterData,
  { rejectValue: ApiError }
>("/auth/register/", async (credentials, { rejectWithValue }) => {
  try {
    return await authService.register(credentials);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Registration failed") });
  }
});

export const logout = createAsyncThunk<
  void,
  void,
  { state: { auth: AuthState } }
>("/auth/logout/", async (_, { getState, dispatch }) => {
  const refreshTokenValue = getState().auth.tokens?.refresh;
  if (refreshTokenValue) {
    try {
      await authService.logout(refreshTokenValue);
    } catch {
      // Best effort only; local session is still cleared.
    }
  }

  // Clear organization slug from sessionStorage on logout
  sessionStorage.removeItem("organization_slug");

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (dispatch as any)({ type: "store/reset" });

  try {
    const { persistor } = await import("@/app/store");
    await persistor.purge();
  } catch {
    // Non-fatal
  }
});

export const fetchProfile = createAsyncThunk<
  ProfileResponse,
  void,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/profile/", async (_, { getState, rejectWithValue }) => {
  if (!getState().auth.tokens?.access) {
    return rejectWithValue({ message: "No token" });
  }
  try {
    return await authService.getProfile();
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Profile fetch failed") });
  }
});

export const switchActiveOrganization = createAsyncThunk<
  ProfileResponse,
  string | null,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/profile/active-organization/", async (organizationId, { getState, rejectWithValue }) => {
  if (!getState().auth.tokens?.access) {
    return rejectWithValue({ message: "No token" });
  }
  try {
    await authService.setActiveOrganization({
      organization_id: organizationId,
      clear: !organizationId,
    });
    return await authService.getProfile(
      organizationId ? { activeOrganizationId: organizationId } : undefined,
    );
  } catch (error: unknown) {
    return rejectWithValue({
      message: getApiErrorMessage(error, "Failed to update active organization"),
    });
  }
});

export const refreshToken = createAsyncThunk<
  AuthTokens,
  void,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/token/refresh/", async (_, { getState, rejectWithValue }) => {
  const refreshTokenValue = getState().auth.tokens?.refresh;
  if (!refreshTokenValue) {
    return rejectWithValue({ message: "No refresh token" });
  }
  try {
    return await authService.refreshToken(refreshTokenValue);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Token refresh failed") });
  }
});

// Module-level deduplication flag.  React 18 StrictMode double-invokes effects,
// which would dispatch silentRefresh twice with the same refresh token.  With
// ROTATE_REFRESH_TOKENS=True that blacklists the token on the first call, causing
// the second call to get a 401 and wipe the freshly-restored session.
// Setting this flag synchronously (before the first await) means the condition()
// check on any concurrent dispatch sees it immediately and skips silently — no
// Redux actions are dispatched, so no clearSessionState side-effect occurs.
let _silentRefreshInFlight = false;

// Restores the session after a page refresh by reading the refresh token stored
// in sessionStorage (put there by every successful login / token-refresh call).
export const silentRefresh = createAsyncThunk<
  AuthTokens,
  void,
  { rejectValue: ApiError }
>("auth/silentRefresh", async (_, { rejectWithValue }) => {
  const storedRefresh = sessionStorage.getItem(REFRESH_TOKEN_SESSION_KEY);
  if (!storedRefresh) {
    return rejectWithValue({ message: "No stored refresh token" });
  }
  // Set the in-flight flag synchronously before the first await so any
  // concurrent dispatch (e.g. StrictMode's second effect invocation) is
  // blocked by the condition() check before it can start its own HTTP call.
  _silentRefreshInFlight = true;
  try {
    return await authService.refreshToken(storedRefresh);
  } catch (error: unknown) {
    sessionStorage.removeItem(REFRESH_TOKEN_SESSION_KEY);
    return rejectWithValue({ message: getApiErrorMessage(error, "Session expired") });
  } finally {
    _silentRefreshInFlight = false;
  }
}, {
  // When condition() returns false, RTK dispatches NO actions at all (no pending,
  // no rejected) — the duplicate call vanishes without any store side-effects.
  condition: () => !_silentRefreshInFlight,
});

export const updateUserProfile = createAsyncThunk(
  "/auth/profile/update/",
  async (data: Record<string, unknown>, { rejectWithValue }) => {
    try {
      return await authService.updateProfile(data);
    } catch (error: unknown) {
      return rejectWithValue(getApiErrorMessage(error, "Failed to update profile"));
    }
  },
);

export const changePassword = createAsyncThunk<
  void,
  { old_password: string; new_password: string; new_password_confirm: string },
  { rejectValue: ApiError }
>("/auth/change-password/", async (data, { rejectWithValue }) => {
  try {
    await authService.changePassword(data);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Password change failed") });
  }
});

export const resetPassword = createAsyncThunk<
  void,
  { token: string; new_password1: string; new_password2: string },
  { rejectValue: ApiError }
>("/auth/password-reset-confirm/", async (data, { rejectWithValue }) => {
  try {
    await authService.resetPassword(data.token, {
      new_password: data.new_password1,
      new_password_confirm: data.new_password2,
    });
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Password reset failed") });
  }
});

export const requestPasswordReset = createAsyncThunk<
  void,
  { email: string },
  { rejectValue: ApiError }
>("/auth/password-reset/", async (data, { rejectWithValue }) => {
  try {
    await authService.requestPasswordReset(data.email);
  } catch (error: unknown) {
    return rejectWithValue({ message: getApiErrorMessage(error, "Password reset request failed") });
  }
});

// ---------------------------------------------------------------------------
// Shared login fulfillment handler (used by both login and adminLogin)
// ---------------------------------------------------------------------------

const applyLoginFulfilled = (state: AuthState, payload: LoginAttemptResponse) => {
  state.loading = false;

  if (isTwoFactorChallenge(payload)) {
    clearSessionState(state);
    // Re-apply slug after clearSessionState wipes it
    state.organizationSlug = sessionStorage.getItem("organization_slug");
    state.resolvedLoginType = sessionStorage.getItem("resolved_login_type") as "admin" | "member" | null;
    state.twoFactorRequired = true;
    state.twoFactorToken = payload.token;
    state.twoFactorSetupRequired = Boolean(payload.setup_required);
    state.twoFactorProvisioningUri = payload.provisioning_uri ?? null;
    state.twoFactorExpiresInSeconds = payload.expires_in_seconds ?? null;
    state.twoFactorMessage = payload.message;
    state.userType = resolveUserType({
      user_type: payload.user_type,
      user: { is_superuser: false, is_staff: false } as unknown as AdminUser,
    });
    return;
  }

  state.user = payload.user;
  state.tokens = payload.tokens;
  state.userType = resolveUserType({
    user_type: payload.user_type,
    user: payload.user,
  });
  state.roles = resolveRoles(payload);
  state.capabilities = resolveCapabilities(payload);
  state.isAuthenticated = true;
  syncOrganizationSlugFromPayload(state, payload);
  applyOrganizationContext(state, EMPTY_ORG_CONTEXT);
  clearTwoFactorState(state);
  if (payload.tokens?.refresh) {
    sessionStorage.setItem(REFRESH_TOKEN_SESSION_KEY, payload.tokens.refresh);
  }
};

// ---------------------------------------------------------------------------
// Slice
// ---------------------------------------------------------------------------

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearTwoFactorChallenge: (state) => {
      clearTwoFactorState(state);
      state.error = null;
    },
    resetPasswordStatus: (state) => {
      state.passwordResetEmailSent = false;
      state.error = null;
    },
    updateUser: (state, action: PayloadAction<Partial<User | AdminUser>>) => {
      if (state.user) {
        Object.assign(state.user, action.payload);
      }
    },
    // Called by LoginForm after resolveTenant succeeds, before login is dispatched
    setOrganizationSlug: (state, action: PayloadAction<string | null>) => {
      state.organizationSlug = persistOrganizationSlug(action.payload);
    },
    setResolvedLoginType: (state, action: PayloadAction<"admin" | "member" | null>) => {
      state.resolvedLoginType = action.payload;
      if (action.payload) {
        sessionStorage.setItem("resolved_login_type", action.payload);
      } else {
        sessionStorage.removeItem("resolved_login_type");
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // ── resolveTenant ────────────────────────────────────────────────────
      .addCase(resolveTenant.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(resolveTenant.fulfilled, (state, action) => {
        state.loading = false;
        state.resolvedLoginType = action.payload.login_type;
        state.organizationSlug = persistOrganizationSlug(action.payload.organization_slug ?? null);
        sessionStorage.setItem("resolved_login_type", action.payload.login_type);
      })
      .addCase(resolveTenant.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Account not found";
      })

      // ── login (tenant members) ───────────────────────────────────────────
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        applyLoginFulfilled(state, action.payload);
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Login failed";
      })

      // ── adminLogin (platform admins) ─────────────────────────────────────
      .addCase(adminLogin.pending, (state) => {
        state.loading = true;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(adminLogin.fulfilled, (state, action) => {
        applyLoginFulfilled(state, action.payload);
      })
      .addCase(adminLogin.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Login failed";
      })

      // ── verifyTwoFactor ──────────────────────────────────────────────────
      .addCase(verifyTwoFactor.pending, (state) => {
        state.loading = true;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(verifyTwoFactor.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.tokens = action.payload.tokens;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        state.loading = false;
        syncOrganizationSlugFromPayload(state, action.payload);
        applyOrganizationContext(state, EMPTY_ORG_CONTEXT);
        clearTwoFactorState(state);
        if (action.payload.tokens?.refresh) {
          sessionStorage.setItem(REFRESH_TOKEN_SESSION_KEY, action.payload.tokens.refresh);
        }
      })
      .addCase(verifyTwoFactor.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = (action.payload as ApiError)?.message || "Two-factor verification failed";
      })

      // ── adminVerifyTwoFactor ─────────────────────────────────────────────
      .addCase(adminVerifyTwoFactor.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(adminVerifyTwoFactor.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.tokens = action.payload.tokens;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        state.loading = false;
        syncOrganizationSlugFromPayload(state, action.payload);
        applyOrganizationContext(state, EMPTY_ORG_CONTEXT);
        clearTwoFactorState(state);
        if (action.payload.tokens?.refresh) {
          sessionStorage.setItem(REFRESH_TOKEN_SESSION_KEY, action.payload.tokens.refresh);
        }
      })
      .addCase(adminVerifyTwoFactor.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Two-factor verification failed";
      })

      // ── register ─────────────────────────────────────────────────────────
      .addCase(register.pending, (state) => {
        state.loading = true;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(register.fulfilled, (state) => {
        clearSessionState(state);
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(register.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = (action.payload as ApiError)?.message || "Registration failed";
      })

      .addCase(updateUserProfile.fulfilled, (state, action) => {
        state.user = action.payload as User | AdminUser;
      })

      // ── logout ────────────────────────────────────────────────────────────
      .addCase(logout.fulfilled, (state) => {
        clearSessionState(state);
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(logout.rejected, (state) => {
        clearSessionState(state);
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = null;
      })

      // ── fetchProfile ──────────────────────────────────────────────────────
      .addCase(fetchProfile.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchProfile.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
          active_organization: action.payload.active_organization,
          is_platform_admin: undefined,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        syncOrganizationSlugFromPayload(state, action.payload);
        applyOrganizationContext(state, action.payload);
        state.isAuthenticated = true;
        state.loading = false;
        // Clear silentRefreshPending here — if a page-refresh restore was in
        // progress (silentRefresh succeeded but left this flag true so that
        // OrganizationScopedRoute stayed blocked), the full sequence is now
        // done and the route guard can proceed with correct activeOrganization.
        state.silentRefreshPending = false;
        clearTwoFactorState(state);
      })
      .addCase(fetchProfile.rejected, (state, action) => {
        state.loading = false;
        // Also clear silentRefreshPending so the app doesn't get stuck in a
        // loading state if the profile fetch fails after silentRefresh succeeded.
        state.silentRefreshPending = false;
        // Do NOT clear the session here. Genuine 401 failures are already
        // handled by the api.ts response interceptor, which dispatches logout()
        // after a failed token refresh. Clearing the session on other failures
        // (500, network errors, schema issues) would permanently log the user
        // out even though their tokens are still valid.
        state.error = (action.payload as ApiError)?.message || "Failed to fetch profile";
      })

      // ── switchActiveOrganization ──────────────────────────────────────────
      .addCase(switchActiveOrganization.pending, (state) => {
        state.switchingActiveOrganization = true;
        state.error = null;
      })
      .addCase(switchActiveOrganization.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
          active_organization: action.payload.active_organization,
          is_platform_admin: undefined,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        syncOrganizationSlugFromPayload(state, action.payload);
        applyOrganizationContext(state, action.payload);
        state.isAuthenticated = true;
        state.switchingActiveOrganization = false;
      })
      .addCase(switchActiveOrganization.rejected, (state, action) => {
        state.switchingActiveOrganization = false;
        state.error = (action.payload as ApiError)?.message || "Failed to update active organization";
      })

      // ── refreshToken ──────────────────────────────────────────────────────
      .addCase(refreshToken.fulfilled, (state, action) => {
        state.tokens = action.payload;
        state.isAuthenticated = true;
        if (action.payload.refresh) {
          sessionStorage.setItem(REFRESH_TOKEN_SESSION_KEY, action.payload.refresh);
        }
      })
      .addCase(refreshToken.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Session expired";
      })

      // ── silentRefresh (page-reload session restore) ────────────────────
      .addCase(silentRefresh.pending, (state) => {
        state.silentRefreshPending = true;
      })
      .addCase(silentRefresh.fulfilled, (state, action) => {
        state.tokens = action.payload;
        state.isAuthenticated = true;
        // Do NOT clear silentRefreshPending here. AppBootstrap immediately
        // dispatches fetchProfile() after silentRefresh succeeds, and we want
        // OrganizationScopedRoute to stay blocked (via its silentRefreshPending
        // guard) until activeOrganization is updated from the server.
        // silentRefreshPending is cleared by fetchProfile.fulfilled / rejected.
        if (action.payload.refresh) {
          sessionStorage.setItem(REFRESH_TOKEN_SESSION_KEY, action.payload.refresh);
        }
      })
      .addCase(silentRefresh.rejected, (state) => {
        clearSessionState(state); // also sets silentRefreshPending = false
      })

      // ── changePassword ────────────────────────────────────────────────────
      .addCase(changePassword.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(changePassword.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(changePassword.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Password change failed";
      })

      // ── requestPasswordReset ──────────────────────────────────────────────
      .addCase(requestPasswordReset.pending, (state) => {
        state.loading = true;
        state.error = null;
        state.passwordResetEmailSent = false;
      })
      .addCase(requestPasswordReset.fulfilled, (state) => {
        state.loading = false;
        state.passwordResetEmailSent = true;
      })
      .addCase(requestPasswordReset.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Request failed";
        state.passwordResetEmailSent = false;
      })

      // ── resetPassword ─────────────────────────────────────────────────────
      .addCase(resetPassword.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(resetPassword.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(resetPassword.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Password reset failed";
      });
  },
});

export const {
  clearError,
  clearTwoFactorChallenge,
  resetPasswordStatus,
  updateUser,
  setOrganizationSlug,
  setResolvedLoginType,
} = authSlice.actions;

export default authSlice.reducer;
