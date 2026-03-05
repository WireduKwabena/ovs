# 6) Candidate Invitations and Access Journey

## 6.1 Invitation Model

Candidates are onboarded through invitation flows rather than unrestricted public signups.

Main invitation APIs:

- `GET/POST /api/invitations/`
- `GET/PATCH/DELETE /api/invitations/{id}/`
- `POST /api/invitations/{id}/send/`
- `POST /api/invitations/accept/`

## 6.2 Candidate Access APIs

- `POST /api/invitations/access/consume/`
- `GET /api/invitations/access/me/`
- `GET /api/invitations/access/results/`
- `POST /api/invitations/access/logout/`

## 6.3 Candidate Entry Points

Frontend pages:

- `/invite/:token`
- `/candidate/access`

Typical sequence:

1. Candidate receives invitation link via channel.
2. Candidate accepts invitation token.
3. Candidate access session is consumed/bootstrapped.
4. Candidate sees allowed tasks/status.
5. Candidate submits required artifacts.
6. Candidate revisits results route after processing/decision.

## 6.4 Candidate Enrollment Surfaces

APIs:

- `GET/POST /api/enrollments/`
- `GET/PATCH/DELETE /api/enrollments/{id}/`
- `POST /api/enrollments/{id}/mark-complete/`

Related candidate APIs:

- `GET/POST /api/candidates/`
- `GET/PATCH/DELETE /api/candidates/{id}/`
- `GET/POST /api/social-profiles/`
- `GET/PATCH/DELETE /api/social-profiles/{id}/`

## 6.5 Invitation Operational Tips

1. Confirm candidate email and phone data quality before sending.
2. Re-send invitation if status indicates delivery failure or expiry.
3. Track acceptance timestamps for pipeline health.
4. Avoid issuing duplicate active invitations for same enrollment.

## 6.6 Candidate Session Security Notes

- Access flows are token/session scoped.
- Sessions can be explicitly closed via logout endpoint.
- Candidate privileges are intentionally narrower than staff/admin accounts.

## 6.7 Candidate Experience Checklist

From HR perspective, verify candidate can:

- Open invitation link,
- Authenticate into access session,
- Upload required documents,
- Complete interview stage if required,
- View result summary once published.

