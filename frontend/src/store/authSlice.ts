import {
  createAsyncThunk,
  createSlice,
  type PayloadAction,
} from "@reduxjs/toolkit";

import { authService } from "../services/auth.service";
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
};

const resolveUserType = (
  payload: {
    user_type?: string;
    user: User | AdminUser;
    active_organization?: unknown;
    is_platform_admin?: boolean;
  }
): AuthState["userType"] => {
  const { user, user_type: payloadType, is_platform_admin } = payload;
  
  // 1. Explicit Platform Admin flag from backend (Governance actor summary) or Superuser
  if (is_platform_admin === true || user.is_superuser === true) {
    return 'platform_admin';
  }

  // 2. Resolve based on payload hint
  const typeHint = payloadType || (user as { user_type?: string }).user_type;

  // Normalize legacy "admin" alias to the canonical "platform_admin" value.
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
  clearTwoFactorState(state);
};

const normalizeStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
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
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  if (!id) {
    return null;
  }
  return {
    id,
    code: String(record.code ?? "").trim(),
    name: String(record.name ?? "").trim(),
    organization_type: String(record.organization_type ?? "").trim(),
  };
};

const normalizeOrganizationSummaryList = (value: unknown): OrganizationSummary[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const deduped = new Map<string, OrganizationSummary>();
  for (const item of value) {
    const normalized = normalizeOrganizationSummary(item);
    if (!normalized) {
      continue;
    }
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

const normalizeOrganizationMembership = (value: unknown): OrganizationMembershipContext | null => {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  const organizationId = String(record.organization_id ?? "").trim();
  if (!id || !organizationId) {
    return null;
  }
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
  if (!Array.isArray(value)) {
    return [];
  }
  const deduped = new Map<string, OrganizationMembershipContext>();
  for (const item of value) {
    const normalized = normalizeOrganizationMembership(item);
    if (!normalized) {
      continue;
    }
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

const normalizeCommitteeContext = (value: unknown): CommitteeContext | null => {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  const committeeId = String(record.committee_id ?? "").trim();
  if (!id || !committeeId) {
    return null;
  }
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
  if (!Array.isArray(value)) {
    return [];
  }
  const deduped = new Map<string, CommitteeContext>();
  for (const item of value) {
    const normalized = normalizeCommitteeContext(item);
    if (!normalized) {
      continue;
    }
    deduped.set(normalized.id, normalized);
  }
  return Array.from(deduped.values());
};

// Reusable empty org context — used when a session is established but the
// profile hasn't been fetched yet (i.e. immediately after login / 2FA verify).
const EMPTY_ORG_CONTEXT = {
  organizations: [],
  organization_memberships: [],
  committees: [],
  active_organization: null,
  active_organization_source: "none",
  invalid_requested_organization_id: "",
} as const;

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
  if (fromPayload.length > 0) {
    return fromPayload;
  }
  const fromPayloadGroups = normalizeStringArray(payload.group_roles);
  if (fromPayloadGroups.length > 0) {
    return fromPayloadGroups;
  }

  const fromUserRoles = normalizeStringArray((payload.user as (User & { roles?: unknown }) | undefined)?.roles);
  if (fromUserRoles.length > 0) {
    return fromUserRoles;
  }
  return normalizeStringArray((payload.user as (User & { group_roles?: unknown }) | undefined)?.group_roles);
};

const resolveCapabilities = (payload: {
  capabilities?: unknown;
  user?: User | AdminUser;
}): string[] => {
  const fromPayload = normalizeStringArray(payload.capabilities);
  if (fromPayload.length > 0) {
    return fromPayload;
  }
  return normalizeStringArray((payload.user as (User & { capabilities?: unknown }) | undefined)?.capabilities);
};

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

  // Wipe all non-auth slices so a subsequent login cannot see the previous
  // user's in-memory data (notifications, applications, rubrics, etc.).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (dispatch as any)({ type: "store/reset" });

  // Flush redux-persist storage so the next page load does not rehydrate
  // stale profile data or any tokens that may have been written before the
  // authStorageTransform was in place. Imported dynamically to avoid a
  // circular dependency (store → authSlice → store).
  try {
    const { persistor } = await import("@/app/store");
    await persistor.purge();
  } catch {
    // Non-fatal — in-memory session is already cleared above.
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
  { rejectValue: ApiError }
>("/auth/profile/active-organization/", async (organizationId, { rejectWithValue }) => {
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
  },
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.switchingActiveOrganization = false;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.loading = false;

        if (isTwoFactorChallenge(action.payload)) {
          clearSessionState(state);
          state.twoFactorRequired = true;
          state.twoFactorToken = action.payload.token;
          state.twoFactorSetupRequired = Boolean(action.payload.setup_required);
          state.twoFactorProvisioningUri = action.payload.provisioning_uri ?? null;
          state.twoFactorExpiresInSeconds = action.payload.expires_in_seconds ?? null;
          state.twoFactorMessage = action.payload.message;
          state.userType = resolveUserType({
            user_type: action.payload.user_type,
            // Only type hint is available during 2FA challenge — no full user object yet.
            user: { is_superuser: false, is_staff: false } as unknown as AdminUser,
          });
          return;
        }

        state.user = action.payload.user;
        state.tokens = action.payload.tokens;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        applyOrganizationContext(state, EMPTY_ORG_CONTEXT);
        clearTwoFactorState(state);
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Login failed";
      })

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
        applyOrganizationContext(state, EMPTY_ORG_CONTEXT);
        clearTwoFactorState(state);
      })
      .addCase(verifyTwoFactor.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        state.error = (action.payload as ApiError)?.message || "Two-factor verification failed";
      })

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

      .addCase(fetchProfile.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchProfile.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.userType = resolveUserType({
          user_type: action.payload.user_type,
          user: action.payload.user,
          active_organization: action.payload.active_organization,
        // `actor.is_platform_admin` is a future governance-summary field not yet in
        // the ProfileResponse type — omit until the backend ships it.
        is_platform_admin: undefined,
        });
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        applyOrganizationContext(state, action.payload);
        state.isAuthenticated = true;
        state.loading = false;
        clearTwoFactorState(state);
      })
      .addCase(fetchProfile.rejected, (state, action) => {
        state.loading = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Failed to fetch profile";
      })

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
        applyOrganizationContext(state, action.payload);
        state.isAuthenticated = true;
        state.switchingActiveOrganization = false;
      })
      .addCase(switchActiveOrganization.rejected, (state, action) => {
        state.switchingActiveOrganization = false;
        state.error = (action.payload as ApiError)?.message || "Failed to update active organization";
      })

      .addCase(refreshToken.fulfilled, (state, action) => {
        state.tokens = action.payload;
        state.isAuthenticated = true;
      })
      .addCase(refreshToken.rejected, (state, action) => {
        state.loading = false;
        state.switchingActiveOrganization = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Session expired";
      })

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

export const { clearError, clearTwoFactorChallenge, resetPasswordStatus, updateUser } = authSlice.actions;
export default authSlice.reducer;






