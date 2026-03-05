# 17) Frequently Asked Questions (FAQ)

## 17.1 Access and Accounts

### Q: Can anyone sign up directly?

A: The recommended flow is subscription-first onboarding, then registration access based on successful subscription confirmation.

### Q: Why am I redirected to 2FA after login?

A: Non-candidate accounts are expected to complete two-factor verification to reduce account takeover risk.

### Q: Why can I not see admin pages?

A: Admin pages are role-guarded. Confirm your account `user_type` is `admin`.

## 17.2 Billing

### Q: Why does cancellation not immediately remove access?

A: Unsubscribe operations are period-end cancellations by design. Service remains active until current billing period ends.

### Q: Why does callback say payment pending even after checkout?

A: Provider status can lag. Use retry confirmation and verify webhook delivery or manual confirm endpoint response.

### Q: Can payment method be changed?

A: Yes, through settings billing controls. Exact path depends on provider (Stripe hosted update session vs provider-specific flow).

## 17.3 Campaigns and Rubrics

### Q: Who should create rubrics?

A: HR managers typically own rubric design per campaign. Admins can oversee governance.

### Q: Can a rubric be changed after activation?

A: Use versioning patterns. Avoid silent in-place changes that compromise auditability.

### Q: Why are some cases marked for manual review?

A: The system routes low-confidence or conflicting signals for human decision.

## 17.4 Candidate Journey

### Q: Candidate says invitation link is invalid

A: Check token expiry, invitation state, and enrollment link. Re-send invitation if necessary.

### Q: Can candidate have a permanent account?

A: Candidate flow is designed for scoped participation; persistent account behavior depends on your configured process policy.

## 17.5 Interviews and Video Calls

### Q: Why is meeting join blocked?

A: Common causes include invalid meeting state, token generation failure, or LiveKit configuration issues.

### Q: What is reminder runtime health?

A: It indicates readiness of scheduled reminder processing pipeline (worker/beat/dependencies).

## 17.6 Monitoring and Audit

### Q: Who should access AI/ML monitoring?

A: Typically admins and authorized staff only.

### Q: Why audit logs matter?

A: They preserve who did what and when, which is critical for accountability and incident reconstruction.

## 17.7 Background Checks

### Q: Is background check provider integration real or mock?

A: It depends on configuration. Mock is suitable for development; production should use a real provider mode.

### Q: Webhook isn’t updating status. What next?

A: Use refresh endpoint, inspect provider logs, then confirm webhook auth/signature settings.
