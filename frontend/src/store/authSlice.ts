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
  type LoginAttemptResponse,
  type LoginCredentials,
  type LoginResponse,
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
  userType: "applicant" | "hr_manager" | "admin" | null;
  roles: string[];
  capabilities: string[];
  loading: boolean;
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
  error: null,
  passwordResetEmailSent: false,
  twoFactorRequired: false,
  twoFactorToken: null,
  twoFactorSetupRequired: false,
  twoFactorProvisioningUri: null,
  twoFactorExpiresInSeconds: null,
  twoFactorMessage: null,
};

const resolveUserType = (
  payloadType: LoginResponse["user_type"] | undefined,
  user: User | AdminUser,
): AuthState["userType"] => {
  if (payloadType) {
    return payloadType;
  }
  const fallbackType = (user as User & { user_type?: AuthState["userType"] }).user_type;
  return fallbackType ?? null;
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
>("/auth/logout/", async (_, { getState }) => {
  const refreshTokenValue = getState().auth.tokens?.refresh;
  if (!refreshTokenValue) return;

  try {
    await authService.logout(refreshTokenValue);
  } catch {
    // Best effort only; local session is still cleared.
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
          state.userType = (action.payload.user_type as AuthState["userType"]) ?? null;
          return;
        }

        state.user = action.payload.user;
        state.tokens = action.payload.tokens;
        state.userType = resolveUserType(action.payload.user_type, action.payload.user);
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        clearTwoFactorState(state);
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Login failed";
      })

      .addCase(verifyTwoFactor.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(verifyTwoFactor.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.tokens = action.payload.tokens;
        state.userType = resolveUserType(action.payload.user_type, action.payload.user);
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        state.loading = false;
        clearTwoFactorState(state);
      })
      .addCase(verifyTwoFactor.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Two-factor verification failed";
      })

      .addCase(register.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(register.fulfilled, (state) => {
        clearSessionState(state);
        state.loading = false;
        state.error = null;
      })
      .addCase(register.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Registration failed";
      })

      .addCase(updateUserProfile.fulfilled, (state, action) => {
        state.user = action.payload as User | AdminUser;
      })

      .addCase(logout.fulfilled, (state) => {
        clearSessionState(state);
        state.error = null;
      })
      .addCase(logout.rejected, (state) => {
        clearSessionState(state);
        state.error = null;
      })

      .addCase(fetchProfile.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.userType = action.payload.user_type as AuthState["userType"];
        state.roles = resolveRoles(action.payload);
        state.capabilities = resolveCapabilities(action.payload);
        state.isAuthenticated = true;
        clearTwoFactorState(state);
      })
      .addCase(fetchProfile.rejected, (state, action) => {
        clearSessionState(state);
        state.error = (action.payload as ApiError)?.message || "Failed to fetch profile";
      })

      .addCase(refreshToken.fulfilled, (state, action) => {
        state.tokens = action.payload;
        state.isAuthenticated = true;
      })
      .addCase(refreshToken.rejected, (state, action) => {
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





