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
  paystack?: {
    secret_key_configured: boolean;
    base_url: string;
    currency: string;
  };
  exchange_rate?: {
    api_url_configured: boolean;
    fallback_rate: number;
    timeout_seconds: number;
    cache_ttl_seconds: number;
  };
  subscription_verify_rate_limit: {
    enabled: boolean;
    per_minute: number;
  };
}

export interface BillingQuotaCandidate {
  enforced: boolean;
  scope: string;
  reason: string | null;
  plan_id: string | null;
  plan_name: string | null;
  limit: number | null;
  used: number;
  remaining: number | null;
  period_start: string;
  period_end: string;
}

export interface BillingQuotaResponse {
  status: 'ok' | string;
  candidate: BillingQuotaCandidate;
}

export interface BillingPaymentMethodSummary {
  type: string | null;
  display: string | null;
  brand: string | null;
  last4: string | null;
  exp_month: number | null;
  exp_year: number | null;
}

export interface BillingManagedSubscription {
  id: string;
  provider: 'stripe' | 'paystack' | 'sandbox' | string;
  status: string;
  payment_status: string;
  plan_id: string;
  plan_name: string;
  billing_cycle: string;
  amount_usd: string;
  payment_method: BillingPaymentMethodSummary;
  checkout_url: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancellation_requested_at: string | null;
  cancellation_effective_at: string | null;
  can_update_payment_method: boolean;
  can_delete_payment_method: boolean;
  retry_available: boolean;
  retry_reason: string | null;
  updated_at: string;
}

export interface BillingSubscriptionManageResponse {
  status: 'ok' | string;
  message?: string;
  subscription: BillingManagedSubscription | null;
}

export interface BillingPortalSessionResponse {
  status: 'ok' | string;
  provider: 'stripe' | 'paystack' | string;
  url: string;
}

export interface BillingSubscriptionRetryResponse {
  status: 'ok' | string;
  provider: 'stripe' | 'paystack' | 'sandbox' | string;
  message?: string;
  session_id?: string;
  checkout_url?: string;
}

const getHealth = async (): Promise<BillingHealthResponse> => {
  const response = await api.get<BillingHealthResponse>('/billing/health/');
  return response.data;
};

const getQuota = async (): Promise<BillingQuotaResponse> => {
  const response = await api.get<BillingQuotaResponse>('/billing/quotas/');
  return response.data;
};

const getSubscriptionManagement = async (): Promise<BillingSubscriptionManageResponse> => {
  const response = await api.get<BillingSubscriptionManageResponse>('/billing/subscriptions/manage/');
  return response.data;
};

const updatePaymentMethod = async (
  paymentMethod: 'card' | 'bank_transfer' | 'mobile_money',
): Promise<BillingSubscriptionManageResponse> => {
  const response = await api.patch<BillingSubscriptionManageResponse>('/billing/subscriptions/manage/', {
    payment_method: paymentMethod,
  });
  return response.data;
};

const scheduleSubscriptionCancellation = async (): Promise<BillingSubscriptionManageResponse> => {
  const response = await api.delete<BillingSubscriptionManageResponse>('/billing/subscriptions/manage/');
  return response.data;
};

const createPaymentMethodUpdateSession = async (): Promise<BillingPortalSessionResponse> => {
  const response = await api.post<BillingPortalSessionResponse>(
    '/billing/subscriptions/manage/payment-method/update-session/',
    {},
  );
  return response.data;
};

const retrySubscription = async (): Promise<BillingSubscriptionRetryResponse> => {
  const response = await api.post<BillingSubscriptionRetryResponse>('/billing/subscriptions/manage/retry/', {});
  return response.data;
};

export const billingService = {
  getHealth,
  getQuota,
  getSubscriptionManagement,
  updatePaymentMethod,
  scheduleSubscriptionCancellation,
  createPaymentMethodUpdateSession,
  retrySubscription,
};
