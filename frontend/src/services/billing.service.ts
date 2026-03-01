import api from './api';

export interface BillingHealthAccess {
  staff_required: boolean;
  requester_is_staff: boolean;
}

export interface BillingHealthResponse {
  status: 'ok' | string;
  access: BillingHealthAccess;
  stripe: {
    sdk_installed: boolean;
    secret_key_configured: boolean;
    webhook_secret_configured: boolean;
  };
  subscription_verify_rate_limit: {
    enabled: boolean;
    per_minute: number;
  };
}

const getHealth = async (): Promise<BillingHealthResponse> => {
  const response = await api.get<BillingHealthResponse>('/billing/health/');
  return response.data;
};

export const billingService = {
  getHealth,
};
