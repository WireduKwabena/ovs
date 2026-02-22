// src/store/authSlice.ts
import {
  createSlice,
  createAsyncThunk,
  type PayloadAction,
} from "@reduxjs/toolkit";
import { authService } from "../services/auth.service";
import {
  type User,
  type AdminUser,
  type AuthTokens,
  type LoginCredentials,
  type LoginResponse,
  type ApiError,
  type RegisterResponse,
  type RegisterData,
} from "../types";
import { store } from "@/app/store";

interface AuthState {
  user: User | AdminUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  userType: "applicant" | "hr_manager" | "admin" | null;
  loading: boolean;
  error: string | null;
  passwordResetEmailSent: boolean;
}

const initialState: AuthState = {
  user: null,
  tokens: null,
  isAuthenticated: false,
  userType: null,
  loading: false,
  error: null,
  passwordResetEmailSent: false,
};



// Async Thunks
export const login = createAsyncThunk<
  LoginResponse,
  LoginCredentials,
  { rejectValue: ApiError }
>(
  "/api/auth/login/",
  async (credentials: LoginCredentials, { rejectWithValue }) => {
    try {
      return await authService.login(credentials);
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data.message || { message: "Login failed" }
      );
    }
  }
);

export const register = createAsyncThunk<
  RegisterResponse,
  RegisterData,
  { rejectValue: ApiError }
>(
  "/auth/Register/",
  async (credentials: RegisterData, { rejectWithValue }) => {
    try {
      return await authService.register(credentials);
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data.message || { message: "Reegisteration failed" }
      );
    }
  }
);

export const logout = createAsyncThunk<
  void,
  void,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/logout/", async (_, { getState, rejectWithValue }) => {
  const state = getState();
  if (!state.auth.tokens?.refresh) {
    return rejectWithValue({ message: "No refresh token for logout" });
  }
  try {
    await authService.logout(state.auth.tokens.refresh); // Pass refreshToken from state
  } catch (error: any) {
    // Logout succeeds even if API fails (local clear)
    return rejectWithValue(
      error.response?.data || { message: "Logout API failed" }
    );
  }
});

export const fetchProfile = createAsyncThunk<
  User | AdminUser,
  void,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/profile/", async (_, { getState, rejectWithValue }) => {
  const state = getState();
  if (!state.auth.tokens?.access) {
    return rejectWithValue({ message: "No token" });
  }
  try {
    const profileResponse = await authService.getProfile();
    return profileResponse.user; // Extract 'user' from { user, user_type } to match thunk return type
  } catch (error: any) {
    return rejectWithValue(
      error.response?.data.message || { message: "Profile fetch failed" }
    );
  }
});

export const refreshToken = createAsyncThunk<
  AuthTokens,
  void,
  { rejectValue: ApiError; state: { auth: AuthState } }
>("/auth/token/refresh/", async (_, { getState, rejectWithValue }) => {
  const state = getState();
  if (!state.auth.tokens?.refresh) {
    return rejectWithValue({ message: "No refresh token" });
  }
  try {
    // Assumes authService.refreshToken expects the refresh token string
    return await authService.refreshToken(state.auth.tokens.refresh);
  } catch (error: any) {
    return rejectWithValue(
      error.response?.data || { message: "Token refresh failed" }
    );
  }
});

export const updateUserProfile = createAsyncThunk(
  "/auth/profile/update/",
  async (data: Partial<User | AdminUser>, { rejectWithValue }) => {
    try {
      const response = await authService.updateProfile(data);
      return response;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || "Failed to update profile"
      );
    }
  }
);
export const changePassword = createAsyncThunk<
  void,
  { old_password: string; new_password: string; new_password_confirm: string },
  { rejectValue: ApiError }
>("/auth/change-password/", async (data, { rejectWithValue }) => {
  try {
    await authService.changePassword(data);
  } catch (error: any) {
    return rejectWithValue(
      error.response?.data.message || { message: "Password change failed" }
    );
  }
});
export const resetPassword = createAsyncThunk<
  void,
  { token: string; new_password1: string; new_password2: string },
  { rejectValue: ApiError }
>("/auth/password-reset/confirm/", async (data, { rejectWithValue }) => {
  try {
    await authService.resetPassword(data.token, {
      new_password1: data.new_password1,
      new_password2: data.new_password2,
    });
  } catch (error: any) {
    return rejectWithValue(
      error.response?.data.message || { message: "Password reset failed" }
    );
  }
});

export const requestPasswordReset = createAsyncThunk<
  void,
  { email: string, },
  { rejectValue: ApiError }
>("/auth/password-reset/", async (data, { rejectWithValue }) => {
  try {
    await authService.requestPasswordReset(data.email);
  } catch (error: any) {
    return rejectWithValue(
      error.response?.data.message || { message: "Password reset request failed" }
    );
  }
});


const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    clearError: (state) => {
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
      .addCase(
        login.fulfilled,
        (state, action: PayloadAction<LoginResponse>) => {
          state.user = action.payload.user;
          state.tokens = action.payload.tokens;
          state.isAuthenticated = true;
          state.userType = action.payload.user_type ?? null;
          state.loading = false;
        }
      )
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.error = (action.payload as ApiError)?.message || "Login failed";
        state.isAuthenticated = false;
      });

    // Register
    builder.addCase(register.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(register.fulfilled, (state, action) => {
      state.loading = false;
      state.user = action.payload.user;
      state.tokens = action.payload.tokens;
      state.userType = action.payload.user_type ?? "hr_manager";
      state.isAuthenticated = true;
      state.error = null;
    });
    builder.addCase(register.rejected, (state, action) => {
      state.loading = false;
      state.error =
        (action.payload as ApiError)?.message || "Registration failed";
    });

    // Update Profile
    builder.addCase(updateUserProfile.fulfilled, (state, action) => {
      state.user = action.payload;
    });
    // Logout
    builder
      .addCase(logout.fulfilled, (state) => {
        state.user = null;
        state.tokens = null;
        state.isAuthenticated = false;
        state.userType = null;
        // Clear localStorage if needed (persist handles most)
        localStorage.clear();
      })
      .addCase(
        fetchProfile.fulfilled,
        (state, action: PayloadAction<User | AdminUser>) => {
          state.user = action.payload;
        }
      )
      .addCase(
        refreshToken.fulfilled,
        (state, action: PayloadAction<AuthTokens>) => {
          state.tokens = action.payload;
        }
      )
      .addCase(refreshToken.rejected, (state, action) => {
        // Auto-logout on refresh fail
        state.isAuthenticated = false;
        state.tokens = null;
        localStorage.clear();
        state.error =
          (action.payload as ApiError)?.message || "Session expired";
      });

      // Password Management
    builder
    .addCase(changePassword.pending, (state) => {
      state.loading = true;
      state.error = null;
    })
    .addCase(changePassword.fulfilled, (state) => {
      state.loading = false;
    })
    .addCase(changePassword.rejected, (state, action) => {
      state.loading = false;
      state.error = (action.payload as ApiError)?.message || 'Password change failed';
    });

  builder
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
      state.error = (action.payload as ApiError)?.message || 'Request failed';
      state.passwordResetEmailSent = false;
    })

  builder
    .addCase(resetPassword.pending, (state) => {
      state.loading = true;
      state.error = null;
    })
    .addCase(resetPassword.fulfilled, (state) => {
      state.loading = false;
    })
    .addCase(resetPassword.rejected, (state, action) => {
      state.loading = false;
      state.error = (action.payload as ApiError)?.message || 'Password reset failed';
    });
  },
});

export const { clearError, updateUser, resetPasswordStatus } = authSlice.actions;
export default authSlice.reducer;
export type AppDispatch = typeof store.dispatch;
