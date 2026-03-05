# 4) Authentication, Login, and Security

## 4.1 Authentication Endpoints

Primary authentication APIs:

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `POST /api/auth/admin/login/`
- `POST /api/auth/login/verify/`
- `POST /api/auth/admin/login/verify/`
- `POST /api/auth/token/refresh/` (if enabled)

## 4.2 Login Flow (Standard User)

1. Enter credentials on `/login`.
2. If 2FA is required, user is redirected to `/login/2fa`.
3. User submits OTP or backup code.
4. System issues authenticated session/JWT context.
5. Profile fetch runs automatically for role and permissions.

## 4.3 Admin Login Flow

Admin login uses dedicated backend route:

- `POST /api/auth/admin/login/`

2FA verification can still be required:

- `POST /api/auth/admin/login/verify/`

## 4.4 Password Management

Supported actions:

- Change password: `POST /api/auth/change-password/`
- Request reset: `POST /api/auth/password-reset/`
- Confirm reset: `POST /api/auth/password-reset-confirm/`

UI paths:

- `/change-password`
- `/forgot-password`
- `/forgot-password/email-sent`
- `/reset-password/:token`

## 4.5 Profile Management

Profile APIs:

- `GET /api/auth/profile/`
- `PATCH /api/auth/profile/update/`

User settings page supports:

- Personal details,
- Professional metadata,
- Optional profile fields,
- Billing management section (for non-applicant roles),
- Security action links.

## 4.6 Two-Factor Authentication (2FA)

2FA APIs:

- `POST /api/auth/admin/2fa/setup/`
- `POST /api/auth/admin/2fa/enable/`
- `GET /api/auth/2fa/status/`
- `POST /api/auth/2fa/backup-codes/regenerate/`

Operational model:

- Non-candidate accounts are expected to use 2FA.
- Backup codes are generated and stored securely (hashed).
- Backup code regeneration should be treated as a sensitive action.

## 4.7 Security Page

From `/security` (non-applicant roles):

- View 2FA status,
- Setup/enable authenticator flow,
- Regenerate backup codes,
- Validate account protection state.

## 4.8 Session and CSRF Notes

Common causes of login failure:

- Missing CSRF token on POST requests,
- Origin not present in trusted CSRF origins,
- Expired session or stale token after environment changes.

Best practices:

- Keep frontend origin in `CSRF_TRUSTED_ORIGINS`.
- Keep frontend origin in `CORS_ALLOWED_ORIGINS`.
- Use consistent protocol and hostnames across frontend/backend.

## 4.9 Email Delivery Behavior

Configured behavior:

- Debug/development: console/terminal email backend.
- Production: SMTP backend.

Ensure SMTP env values are configured in production:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

