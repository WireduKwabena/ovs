import { describe, expect, it } from "vitest";

import {
  buildBillingProcessingErrorNotificationTraceHref,
  buildBillingPaymentFailureNotificationTraceHref,
  buildNotificationTraceHref,
  buildProcessingErrorNotificationTraceHref,
  buildReminderNotificationTraceHref,
} from "./notificationTrace";

describe("notificationTrace helpers", () => {
  it("builds the default all-channel notifications path when no filters are provided", () => {
    expect(buildNotificationTraceHref()).toBe("/notifications?channel=all");
  });

  it("builds a reminder trace href with the all-channel event filter", () => {
    expect(buildReminderNotificationTraceHref()).toBe(
      "/notifications?channel=all&event_type=video_call_reminder",
    );
  });

  it("builds a processing-error trace href with archived view when requested", () => {
    expect(buildProcessingErrorNotificationTraceHref("archived")).toBe(
      "/notifications?channel=all&event_type=processing_error&view=archived",
    );
  });

  it("builds a billing processing-error trace href scoped to the billing subsystem", () => {
    expect(buildBillingProcessingErrorNotificationTraceHref()).toBe(
      "/notifications?channel=all&event_type=processing_error&subsystem=billing",
    );
  });

  it("builds a billing payment-failure trace href scoped to the billing subsystem", () => {
    expect(buildBillingPaymentFailureNotificationTraceHref()).toBe(
      "/notifications?channel=all&event_type=billing_payment_failed&subsystem=billing",
    );
  });

  it("preserves channel, event type, idempotency key, and non-default view", () => {
    expect(
      buildNotificationTraceHref({
        channel: "email",
        eventType: "video_call_time_up",
        idempotencyKey: "trace-123",
        subsystem: "billing",
        view: "read",
      }),
    ).toBe(
      "/notifications?channel=email&event_type=video_call_time_up&idempotency_key=trace-123&subsystem=billing&view=read",
    );
  });

  it("omits default in-app channel and default all view from the URL", () => {
    expect(
      buildNotificationTraceHref({
        channel: "in_app",
        eventType: "appointment_nomination_created",
      }),
    ).toBe("/notifications?event_type=appointment_nomination_created");
  });
});
