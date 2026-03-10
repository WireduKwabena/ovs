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
