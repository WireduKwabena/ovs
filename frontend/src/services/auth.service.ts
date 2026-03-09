import api from "./api";
import type {
  AdminUser,
  ApiError,
  AuthTokens,
  CommitteeContext,
  LoginAttemptResponse,
  LoginResponse,
  OrganizationMembershipContext,
  OrganizationSummary,
  RegisterResponse,
  TwoFactorBackupCodesResponse,
  TwoFactorSetupResponse,
  TwoFactorStatusResponse,
  User,
} from "@/types";
import { getApiErrorMessage } from "@/utils/apiError";

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
  department: string;
  onboarding_token: string;
  // Legacy fields retained for backward-compatible payload tolerance.
  organization?: string;
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
  roles?: string[];
  capabilities?: string[];
  is_internal_operator?: boolean;
  organizations?: OrganizationSummary[];
  organization_memberships?: OrganizationMembershipContext[];
  committees?: CommitteeContext[];
  active_organization?: OrganizationSummary | null;
  active_organization_source?: string;
  invalid_requested_organization_id?: string;
}

export interface ActiveOrganizationSelectionResponse {
  message: string;
  active_organization: OrganizationSummary | null;
  active_organization_source: string;
  invalid_requested_organization_id?: string;
}

export interface OnboardingTokenValidationResponse {
  valid: boolean;
  reason: string;
  organization_id?: string;
  organization_name?: string;
  subscription_id?: string | null;
  remaining_uses?: number | null;
  expires_at?: string | null;
}

const toApiError = (error: any, fallback: string): Error => {
  const payload = error?.response?.data as ApiError | undefined;
  const message = getApiErrorMessage(payload ?? error, fallback);
  return new Error(message);
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

  async validateOnboardingToken(payload: {
    token: string;
    email?: string;
  }): Promise<OnboardingTokenValidationResponse> {
    try {
      const response = await api.post<OnboardingTokenValidationResponse>(
        "/billing/onboarding-token/validate/",
        payload,
      );
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Onboarding token validation failed");
    }
  },

  async logout(refreshToken: string): Promise<void> {
    try {
      await api.post("/auth/logout/", { refresh: refreshToken });
    } catch {
      // best effort only
    }
  },

  async getProfile(params?: { activeOrganizationId?: string }): Promise<ProfileResponse> {
    try {
      const response = await api.get<ProfileResponse>("/auth/profile/", {
        params: params?.activeOrganizationId
          ? { active_organization_id: params.activeOrganizationId }
          : undefined,
      });
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Profile fetch failed");
    }
  },

  async setActiveOrganization(payload: {
    organization_id?: string | null;
    clear?: boolean;
  }): Promise<ActiveOrganizationSelectionResponse> {
    try {
      const response = await api.post<ActiveOrganizationSelectionResponse>(
        "/auth/profile/active-organization/",
        payload,
      );
      return response.data;
    } catch (error: any) {
      throw toApiError(error, "Failed to update active organization.");
    }
  },

  async updateProfile(data: Record<string, unknown>): Promise<User | AdminUser> {
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

