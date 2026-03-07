export type BillingCycle = "monthly" | "annual";
export type PaymentMethod = "card" | "bank_transfer" | "mobile_money";

export interface SubscriptionAccessTicket {
  planId: string;
  planName: string;
  billingCycle: BillingCycle;
  paymentMethod: PaymentMethod;
  amountUsd: number;
  reference: string;
  confirmedAt: number;
  expiresAt: number;
}

const STORAGE_KEY = "ovs_subscription_access_ticket_v1";
const DEFAULT_TTL_HOURS = 24;

const isBrowser = (): boolean => typeof window !== "undefined";

export const setSubscriptionAccessTicket = (
  ticket: SubscriptionAccessTicket,
): SubscriptionAccessTicket => {
  if (isBrowser()) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ticket));
  }
  return ticket;
};

export const grantSubscriptionAccess = (input: {
  planId: string;
  planName: string;
  billingCycle: BillingCycle;
  paymentMethod: PaymentMethod;
  amountUsd: number;
  ttlHours?: number;
}): SubscriptionAccessTicket => {
  const now = Date.now();
  const ttl = Math.max(1, input.ttlHours ?? DEFAULT_TTL_HOURS);
  const ticket: SubscriptionAccessTicket = {
    planId: input.planId,
    planName: input.planName,
    billingCycle: input.billingCycle,
    paymentMethod: input.paymentMethod,
    amountUsd: input.amountUsd,
    reference: `OVS-GAMS-${Math.random().toString(36).slice(2, 10).toUpperCase()}`,
    confirmedAt: now,
    expiresAt: now + ttl * 60 * 60 * 1000,
  };

  return setSubscriptionAccessTicket(ticket);
};

export const getSubscriptionAccessTicket = (): SubscriptionAccessTicket | null => {
  if (!isBrowser()) return null;

  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as SubscriptionAccessTicket;
    if (!parsed.expiresAt || Date.now() > parsed.expiresAt) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
};

export const hasValidSubscriptionAccess = (): boolean => {
  return Boolean(getSubscriptionAccessTicket());
};

export const clearSubscriptionAccess = (): void => {
  if (!isBrowser()) return;
  localStorage.removeItem(STORAGE_KEY);
};
