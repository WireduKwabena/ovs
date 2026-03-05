import axios from "axios";
import api from "./api";
import {
  grantSubscriptionAccess,
  setSubscriptionAccessTicket,
  type BillingCycle,
  type PaymentMethod,
  type SubscriptionAccessTicket,
} from "@/utils/subscriptionAccess";

export type CheckoutMode = "mock" | "api" | "stripe" | "paystack";

export interface ConfirmSubscriptionInput {
  planId: string;
  planName: string;
  billingCycle: BillingCycle;
  paymentMethod: PaymentMethod;
  amountUsd: number;
  successUrl?: string;
  cancelUrl?: string;
}

export interface ConfirmSubscriptionResult {
  ticket: SubscriptionAccessTicket;
  source: "mock" | "api";
}

export interface VerifySubscriptionAccessResult {
  valid: boolean;
  reason: string;
  reference: string;
  planId?: string;
  planName?: string;
  billingCycle?: BillingCycle;
  paymentMethod?: PaymentMethod;
  amountUsd?: number;
  confirmedAt?: number;
  expiresAt?: number;
  status?: string;
  paymentStatus?: string;
  registrationConsumedAt?: number | null;
}

interface ApiConfirmSubscriptionRequest {
  plan_id: string;
  plan_name: string;
  billing_cycle: BillingCycle;
  payment_method: PaymentMethod;
  amount_usd: number;
}

interface StripeCheckoutSessionRequest {
  plan_id: string;
  plan_name: string;
  billing_cycle: BillingCycle;
  amount_usd: number;
  success_url: string;
  cancel_url: string;
}

interface StripeCheckoutSessionResponse {
  provider: "stripe";
  session_id: string;
  checkout_url: string;
}

interface StripeConfirmRequest {
  session_id: string;
}

interface PaystackCheckoutSessionRequest {
  plan_id: string;
  plan_name: string;
  billing_cycle: BillingCycle;
  amount_usd: number;
  success_url: string;
  cancel_url: string;
  customer_email?: string;
}

interface PaystackCheckoutSessionResponse {
  provider: "paystack";
  reference: string;
  checkout_url: string;
}

interface PaystackConfirmRequest {
  reference: string;
}

const env = (import.meta as { env?: Record<string, string | undefined> }).env;
const API_URL = env?.VITE_API_URL || "http://localhost:8000/api";

const publicApi = axios.create({
  baseURL: API_URL,
  withCredentials: false,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

const parseCheckoutMode = (): CheckoutMode => {
  const raw = (env?.VITE_SUBSCRIPTION_MODE || "mock").toLowerCase();
  if (raw === "api" || raw === "stripe" || raw === "paystack") return raw;
  return "mock";
};

const parseBoolean = (value: string | undefined, fallback: boolean): boolean => {
  if (!value) return fallback;
  return value.toLowerCase() === "true";
};

const CHECKOUT_MODE = parseCheckoutMode();
const API_FALLBACK_TO_MOCK = parseBoolean(env?.VITE_SUBSCRIPTION_API_FALLBACK, true);

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const isBillingCycle = (value: unknown): value is BillingCycle =>
  value === "monthly" || value === "annual";

const isPaymentMethod = (value: unknown): value is PaymentMethod =>
  value === "card" || value === "bank_transfer" || value === "mobile_money";

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const normalizeTicket = (payload: unknown): SubscriptionAccessTicket | null => {
  if (!payload || typeof payload !== "object") return null;

  const data = payload as Record<string, unknown>;

  const planId =
    (typeof data.planId === "string" && data.planId) ||
    (typeof data.plan_id === "string" && data.plan_id);
  const planName =
    (typeof data.planName === "string" && data.planName) ||
    (typeof data.plan_name === "string" && data.plan_name);
  const billingCycle = data.billingCycle ?? data.billing_cycle;
  const paymentMethod = data.paymentMethod ?? data.payment_method;
  const amountUsd = toNumber(data.amountUsd ?? data.amount_usd);
  const reference =
    (typeof data.reference === "string" && data.reference) ||
    (typeof data.txn_reference === "string" && data.txn_reference);
  const confirmedAt = toNumber(data.confirmedAt ?? data.confirmed_at);
  const expiresAt = toNumber(data.expiresAt ?? data.expires_at);

  if (
    !planId ||
    !planName ||
    !isBillingCycle(billingCycle) ||
    !isPaymentMethod(paymentMethod) ||
    amountUsd === null ||
    !reference ||
    confirmedAt === null ||
    expiresAt === null
  ) {
    return null;
  }

  return {
    planId,
    planName,
    billingCycle,
    paymentMethod,
    amountUsd,
    reference,
    confirmedAt,
    expiresAt,
  };
};

const buildMockTicket = async (
  input: ConfirmSubscriptionInput,
): Promise<SubscriptionAccessTicket> => {
  await sleep(1100);
  return grantSubscriptionAccess(input);
};

const confirmViaApi = async (
  input: ConfirmSubscriptionInput,
): Promise<SubscriptionAccessTicket> => {
  const payload: ApiConfirmSubscriptionRequest = {
    plan_id: input.planId,
    plan_name: input.planName,
    billing_cycle: input.billingCycle,
    payment_method: input.paymentMethod,
    amount_usd: input.amountUsd,
  };

  const response = await api.post("/billing/subscriptions/confirm/", payload);
  const responseData = response.data as Record<string, unknown>;

  const ticket = normalizeTicket(responseData.ticket ?? responseData);
  if (!ticket) {
    throw new Error("Subscription confirmation response is invalid.");
  }

  return setSubscriptionAccessTicket(ticket);
};

const getFrontendUrl = (): string => {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:3000";
};

const buildStripeSuccessUrl = (): string => {
  const configured = env?.VITE_SUBSCRIPTION_SUCCESS_URL;
  if (configured) return configured;
  return `${getFrontendUrl()}/billing/success`;
};

const buildStripeCancelUrl = (): string => {
  const configured = env?.VITE_SUBSCRIPTION_CANCEL_URL;
  if (configured) return configured;
  return `${getFrontendUrl()}/billing/cancel`;
};

const buildPaystackSuccessUrl = (): string => {
  const configured = env?.VITE_SUBSCRIPTION_SUCCESS_URL;
  if (configured) return configured;
  return `${getFrontendUrl()}/billing/success`;
};

const buildPaystackCancelUrl = (): string => {
  const configured = env?.VITE_SUBSCRIPTION_CANCEL_URL;
  if (configured) return configured;
  return `${getFrontendUrl()}/billing/cancel`;
};

const startStripeCheckout = async (
  input: ConfirmSubscriptionInput,
): Promise<StripeCheckoutSessionResponse> => {
  const payload: StripeCheckoutSessionRequest = {
    plan_id: input.planId,
    plan_name: input.planName,
    billing_cycle: input.billingCycle,
    amount_usd: input.amountUsd,
    success_url: input.successUrl || buildStripeSuccessUrl(),
    cancel_url: input.cancelUrl || buildStripeCancelUrl(),
  };

  const response = await api.post<StripeCheckoutSessionResponse>(
    "/billing/subscriptions/stripe/checkout-session/",
    payload,
  );

  const session = response.data;
  if (!session?.checkout_url || !session?.session_id) {
    throw new Error("Stripe checkout session response is invalid.");
  }

  return session;
};

const startPaystackCheckout = async (
  input: ConfirmSubscriptionInput & { customerEmail?: string },
): Promise<PaystackCheckoutSessionResponse> => {
  const payload: PaystackCheckoutSessionRequest = {
    plan_id: input.planId,
    plan_name: input.planName,
    billing_cycle: input.billingCycle,
    amount_usd: input.amountUsd,
    success_url: input.successUrl || buildPaystackSuccessUrl(),
    cancel_url: input.cancelUrl || buildPaystackCancelUrl(),
    customer_email: input.customerEmail,
  };

  const response = await api.post<PaystackCheckoutSessionResponse>(
    "/billing/subscriptions/paystack/checkout-session/",
    payload,
  );

  const session = response.data;
  if (!session?.checkout_url || !session?.reference) {
    throw new Error("Paystack checkout session response is invalid.");
  }

  return session;
};

const confirmStripeSession = async (
  sessionId: string,
): Promise<SubscriptionAccessTicket> => {
  const payload: StripeConfirmRequest = { session_id: sessionId };

  // Use a public client (without auth interceptors) to avoid session refresh loops on callback pages.
  const response = await publicApi.post("/billing/subscriptions/stripe/confirm/", payload);
  const responseData = response.data as Record<string, unknown>;

  const ticket = normalizeTicket(responseData.ticket ?? responseData);
  if (!ticket) {
    throw new Error("Stripe confirmation response is invalid.");
  }

  return setSubscriptionAccessTicket(ticket);
};

const confirmPaystackReference = async (
  reference: string,
): Promise<SubscriptionAccessTicket> => {
  const payload: PaystackConfirmRequest = { reference };

  const response = await publicApi.post("/billing/subscriptions/paystack/confirm/", payload);
  const responseData = response.data as Record<string, unknown>;

  const ticket = normalizeTicket(responseData.ticket ?? responseData);
  if (!ticket) {
    throw new Error("Paystack confirmation response is invalid.");
  }

  return setSubscriptionAccessTicket(ticket);
};

const verifySubscriptionAccess = async (
  reference: string,
): Promise<VerifySubscriptionAccessResult> => {
  const response = await publicApi.post<VerifySubscriptionAccessResult>(
    "/billing/subscriptions/access/verify/",
    { reference },
  );

  return response.data;
};

export const subscriptionService = {
  getCheckoutMode(): CheckoutMode {
    return CHECKOUT_MODE;
  },

  async beginStripeCheckout(input: ConfirmSubscriptionInput): Promise<StripeCheckoutSessionResponse> {
    return startStripeCheckout(input);
  },

  async beginPaystackCheckout(
    input: ConfirmSubscriptionInput & { customerEmail?: string },
  ): Promise<PaystackCheckoutSessionResponse> {
    return startPaystackCheckout(input);
  },

  async confirmStripeSession(sessionId: string): Promise<SubscriptionAccessTicket> {
    return confirmStripeSession(sessionId);
  },

  async confirmPaystackReference(reference: string): Promise<SubscriptionAccessTicket> {
    return confirmPaystackReference(reference);
  },

  async verifySubscriptionAccess(reference: string): Promise<VerifySubscriptionAccessResult> {
    return verifySubscriptionAccess(reference);
  },

  async confirmSubscription(input: ConfirmSubscriptionInput): Promise<ConfirmSubscriptionResult> {
    if (CHECKOUT_MODE === "mock") {
      try {
        const ticket = await confirmViaApi(input);
        return { ticket, source: "api" };
      } catch (error) {
        if (!API_FALLBACK_TO_MOCK) {
          throw error;
        }
        const ticket = await buildMockTicket(input);
        return { ticket, source: "mock" };
      }
    }

    if (CHECKOUT_MODE === "stripe" || CHECKOUT_MODE === "paystack") {
      throw new Error("Hosted checkout mode requires checkout session flow.");
    }

    try {
      const ticket = await confirmViaApi(input);
      return { ticket, source: "api" };
    } catch (error) {
      if (!API_FALLBACK_TO_MOCK) {
        throw error;
      }

      console.warn(
        "Subscription API confirm failed. Falling back to mock mode.",
        error,
      );
      const ticket = await buildMockTicket(input);
      return { ticket, source: "mock" };
    }
  },
};



