import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Lock, RefreshCw } from 'lucide-react';

import { handleApiError } from '@/services/api';
import { billingService, type BillingHealthResponse } from '@/services/billing.service';

const POLL_INTERVAL_MS = 60_000;

export type BillingHealthStatus = 'checking' | 'healthy' | 'attention' | 'unavailable';

interface BillingHealthCardProps {
  onStatusChange?: (status: BillingHealthStatus) => void;
}

const badgeClass = (isGood: boolean): string => {
  return isGood
    ? 'inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700'
    : 'inline-flex rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700';
};

const deriveHealthStatus = (health: BillingHealthResponse): BillingHealthStatus => {
  const configured =
    health.status === 'ok' &&
    health.stripe.sdk_installed &&
    health.stripe.secret_key_configured &&
    health.stripe.webhook_secret_configured;

  return configured ? 'healthy' : 'attention';
};

const responseStatusCode = (error: unknown): number | null => {
  const candidate = error as { response?: { status?: number } };
  const status = candidate?.response?.status;
  return typeof status === 'number' ? status : null;
};

export const BillingHealthCard: React.FC<BillingHealthCardProps> = ({ onStatusChange }) => {
  const [health, setHealth] = useState<BillingHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [staffOnlyPolicyActive, setStaffOnlyPolicyActive] = useState(false);
  const [isAccessDenied, setIsAccessDenied] = useState(false);
  const latestHealthRef = useRef<BillingHealthResponse | null>(null);

  const loadHealth = useCallback(
    async (mode: 'initial' | 'refresh' | 'poll' = 'initial') => {
      if (mode === 'initial') {
        setIsLoading(true);
        onStatusChange?.('checking');
      }
      if (mode === 'refresh') {
        setIsRefreshing(true);
      }
      if (mode !== 'poll') {
        setError(null);
      }

      try {
        const response = await billingService.getHealth();
        setHealth(response);
        latestHealthRef.current = response;
        setLastCheckedAt(new Date());
        setError(null);
        setStaffOnlyPolicyActive(Boolean(response.access.staff_required));
        setIsAccessDenied(false);
        onStatusChange?.(deriveHealthStatus(response));
      } catch (err: unknown) {
        const statusCode = responseStatusCode(err);
        const restricted = statusCode === 401 || statusCode === 403;
        const nextError = restricted
          ? 'Billing health endpoint is restricted to staff users in this environment.'
          : handleApiError(err);

        setError(nextError);
        setIsAccessDenied(restricted);
        if (restricted) {
          setStaffOnlyPolicyActive(true);
        }

        const latestHealth = latestHealthRef.current;
        onStatusChange?.(latestHealth ? deriveHealthStatus(latestHealth) : 'unavailable');
      } finally {
        if (mode === 'initial') {
          setIsLoading(false);
        }
        if (mode === 'refresh') {
          setIsRefreshing(false);
        }
      }
    },
    [onStatusChange]
  );

  useEffect(() => {
    void loadHealth('initial');
  }, [loadHealth]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadHealth('poll');
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(interval);
    };
  }, [loadHealth]);

  const staffOnlyTooltip = isAccessDenied
    ? 'Billing health endpoint requires a staff account in this environment.'
    : 'Staff-only billing health policy is active for this environment.';

  return (
    <div className='rounded-xl border border-slate-200 bg-white p-5'>
      <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
        <div>
          <div className='flex items-center gap-2'>
            <h2 className='inline-flex items-center gap-2 text-lg font-semibold'>
              <Activity className='h-5 w-5 text-cyan-600' />
              Billing Runtime
            </h2>
            {staffOnlyPolicyActive ? (
              <span
                className='inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700'
                title={staffOnlyTooltip}
              >
                <Lock className='h-3 w-3' />
                Staff-only
              </span>
            ) : null}
          </div>
          <p className='mt-1 text-[11px] text-slate-700'>
            {lastCheckedAt ? `Last checked ${lastCheckedAt.toLocaleTimeString()}` : 'Not checked yet'}
          </p>
        </div>
        <button
          type='button'
          onClick={() => void loadHealth('refresh')}
          disabled={isLoading || isRefreshing}
          className='inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-900 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto'
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {isLoading && !health ? (
        <p className='mt-3 text-sm text-slate-700'>Checking billing health...</p>
      ) : (
        <>
          {error ? <p className='mt-3 text-sm text-rose-600'>{error}</p> : null}
          {health ? (
            <div className='mt-4 space-y-3 text-sm'>
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>API Status</span>
                <span className={badgeClass(health.status === 'ok')}>
                  {health.status === 'ok' ? 'OK' : health.status}
                </span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>Access Policy</span>
                <span className={badgeClass(!health.access.staff_required)}>
                  {health.access.staff_required ? 'Staff-only' : 'Open'}
                </span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>Stripe SDK (Backend)</span>
                <span className={badgeClass(health.stripe.sdk_installed)}>
                  {health.stripe.sdk_installed ? 'Installed' : 'Missing'}
                </span>
              </div>
              {!health.stripe.sdk_installed ? (
                <p className='text-xs text-amber-700'>
                  Backend runtime is missing the Python `stripe` package. Rebuild and restart backend services.
                </p>
              ) : null}
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>Stripe Secret Key</span>
                <span className={badgeClass(health.stripe.secret_key_configured)}>
                  {health.stripe.secret_key_configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>Stripe Webhook Secret</span>
                <span className={badgeClass(health.stripe.webhook_secret_configured)}>
                  {health.stripe.webhook_secret_configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-slate-700'>Verify Rate Limit</span>
                <span className={badgeClass(health.subscription_verify_rate_limit.enabled)}>
                  {health.subscription_verify_rate_limit.enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              <p className='text-xs text-slate-700'>
                Verify limit: {health.subscription_verify_rate_limit.per_minute} requests/minute.
              </p>
            </div>
          ) : (
            <p className='mt-3 text-sm text-slate-700'>No health data available.</p>
          )}
        </>
      )}
    </div>
  );
};

export default BillingHealthCard;
