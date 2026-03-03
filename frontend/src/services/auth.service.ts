import api from "./api";
import type {
  AdminUser,
  ApiError,
  AuthTokens,
  LoginAttemptResponse,
  LoginResponse,
  RegisterResponse,
  TwoFactorBackupCodesResponse,
  TwoFactorSetupResponse,
  TwoFactorStatusResponse,
  User,
} from "@/types";

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  organization: string;
  department: string;
  subscription_reference?: string;
}

export interface TwoFactorVerifyPayload {
  token: string;
  otp?: string;
  backup_code?: string;
}

export interface ProfileResponse {
  user: User | AdminUser;
  user_type: "applicant" | "hr_manager" | "admin";
}

const toApiError = (error: any, fallback: string): Error => {
  const payload = error?.response?.data as ApiError & {
    detail?: string;
    error?: string;
  };

  return new Error(payload?.message || payload?.detail || payload?.error || fallback);
};

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginAttemptResponse> {
    try {
      const response = await api.post<LoginAttemptResponse>("/auth/login/", credentials);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Login failed");
    }
  },

  async verifyTwoFactor(data: TwoFactorVerifyPayload): Promise<LoginResponse> {
    try {
      const response = await api.post<LoginResponse>("/auth/login/verify/", data);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Two-factor verification failed");
    }
  },

  async adminLogin(credentials: LoginCredentials): Promise<LoginAttemptResponse> {
    try {
      const response = await api.post<LoginAttemptResponse>("/auth/admin/login/", credentials);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Admin login failed");
    }
  },

  async adminVerifyTwoFactor(data: TwoFactorVerifyPayload): Promise<LoginResponse> {
    try {
      const response = await api.post<LoginResponse>("/auth/admin/login/verify/", data);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Admin two-factor verification failed");
    }
  },

  async register(data: RegisterData): Promise<RegisterResponse> {
    try {
      const response = await api.post<RegisterResponse>("/auth/register/", data);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Registration failed");
    }
  },

  async logout(refreshToken: string): Promise<void> {
    try {
      await api.post("/auth/logout/", { refresh: refreshToken });
    } catch {
      // best effort only
    }
  },

  async getProfile(): Promise<ProfileResponse> {
    try {
      const response = await api.get<ProfileResponse>("/auth/profile/");
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Profile fetch failed");
    }
  },

  async updateProfile(data: Partial<User | AdminUser>): Promise<User | AdminUser> {
    try {
      const response = await api.put<User | AdminUser>("/auth/profile/update/", data);
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Update failed");
    }
  },

  async changePassword(data: {
    old_password: string;
    new_password: string;
    new_password_confirm: string;
  }): Promise<void> {
    try {
      await api.post("/auth/change-password/", data);
    } catch (error: any) {
      throw toApiError(error, "Password change failed");
    }
  },

  async resetPassword(
    token: string,
    data: { new_password: string; new_password_confirm: string },
  ): Promise<void> {
    try {
      await api.post("/auth/password-reset-confirm/", { ...data, token });
    } catch (error: any) {
      throw toApiError(error, "Password reset failed");
    }
  },

  async requestPasswordReset(email: string): Promise<void> {
    try {
      await api.post("/auth/password-reset/", { email });
    } catch (error: any) {
      throw toApiError(error, "Reset request failed");
    }
  },

  async refreshToken(refreshToken: string): Promise<AuthTokens> {
    try {
      const response = await api.post<AuthTokens>("/auth/token/refresh/", {
        refresh: refreshToken,
      });
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Refresh failed");
    }
  },

  async getTwoFactorStatus(): Promise<TwoFactorStatusResponse> {
    try {
      const response = await api.get<TwoFactorStatusResponse>("/auth/2fa/status/");
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Failed to fetch security status");
    }
  },

  async setupTwoFactor(): Promise<TwoFactorSetupResponse> {
    try {
      const response = await api.get<TwoFactorSetupResponse>("/auth/admin/2fa/setup/");
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Failed to start 2FA setup");
    }
  },

  async enableTwoFactor(otp: string): Promise<{ message: string }> {
    try {
      const response = await api.post<{ message: string }>("/auth/admin/2fa/enable/", { otp });
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Failed to enable 2FA");
    }
  },

  async regenerateBackupCodes(data: { otp?: string; backup_code?: string }): Promise<TwoFactorBackupCodesResponse> {
    try {
      const response = await api.post<TwoFactorBackupCodesResponse>(
        "/auth/2fa/backup-codes/regenerate/",
        data,
      );
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Failed to regenerate backup codes");
    }
  },
};

