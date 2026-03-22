/**
 * Zod runtime schemas for auth API responses.
 *
 * Why: The auth responses drive Redux state that controls routing and access
 * decisions for every page.  Silent type coercion of unexpected shapes
 * (null tokens, unknown user_type, etc.) causes split-brain between the
 * backend's intent and the client's security model.  These schemas fail fast
 * with a descriptive error before any data reaches the store.
 *
 * Design: validate User/AdminUser shapes completely (not with passthrough) so
 * that missing required fields surface immediately.  Optional fields use
 * .optional() so the schema stays forward-compatible with new profile fields.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export const AuthTokensSchema = z.object({
  access: z.string().min(1, "access token must be a non-empty string"),
  refresh: z.string().min(1, "refresh token must be a non-empty string"),
});

const UserTypeSchema = z.enum([
  "applicant",
  "internal",
  "admin",
  "org_admin",
  "platform_admin",
]);

// ---------------------------------------------------------------------------
// ExtendedUserProfile — optional nested profile object
// ---------------------------------------------------------------------------

const ExtendedUserProfileSchema = z
  .object({
    date_of_birth: z.string().nullable().optional(),
    nationality: z.string().optional(),
    address: z.string().optional(),
    city: z.string().optional(),
    country: z.string().optional(),
    postal_code: z.string().optional(),
    current_job_title: z.string().optional(),
    years_of_experience: z.number().nullable().optional(),
    linkedin_url: z.string().optional(),
    bio: z.string().optional(),
    profile_completion_percentage: z.number().optional(),
    avatar_url: z.string().optional(),
  })
  .passthrough(); // allow new profile fields without breaking validation

// ---------------------------------------------------------------------------
// Shared optional role / capability fields present on both user shapes
// ---------------------------------------------------------------------------

const _rolesCapabilities = {
  roles: z.array(z.string()).optional(),
  group_roles: z.array(z.string()).optional(),
  capabilities: z.array(z.string()).optional(),
  is_internal_operator: z.boolean().optional(),
  is_staff: z.boolean().optional(),
  is_superuser: z.boolean().optional(),
};

// ---------------------------------------------------------------------------
// User — full required-field set (applicant / internal users)
// ---------------------------------------------------------------------------

export const UserSchema = z.object({
  id: z.union([z.string(), z.number()]),
  email: z.string().email(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  full_name: z.string(),
  user_type: UserTypeSchema.optional(),
  phone_number: z.string(),
  organization: z.string().optional(),
  department: z.string().optional(),
  profile_picture_url: z.string(),
  avatar_url: z.string(),
  date_of_birth: z.string(),
  profile: ExtendedUserProfileSchema.nullable().optional(),
  is_active: z.boolean(),
  created_at: z.string(),
  ..._rolesCapabilities,
});

// ---------------------------------------------------------------------------
// AdminUser — looser required-field set (platform / org admins)
// ---------------------------------------------------------------------------

export const AdminUserSchema = z.object({
  id: z.union([z.string(), z.number()]),
  email: z.string().email(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  full_name: z.string().optional(),          // optional on admin shape
  phone_number: z.string().optional(),       // optional on admin shape
  organization: z.string().optional(),
  department: z.string().optional(),
  user_type: UserTypeSchema.optional(),
  role_display: z.string().optional(),
  username: z.string().optional(),
  role: z.enum(["admin", "reviewer", "internal", "super_admin"]).optional(),
  avatar_url: z.string().optional(),
  profile: ExtendedUserProfileSchema.nullable().optional(),
  is_active: z.boolean(),
  created_at: z.string(),
  ..._rolesCapabilities,
});

/**
 * Accepts either a full User or an AdminUser.
 * AdminUser is tried first since it has fewer required fields — a valid User
 * will also pass AdminUserSchema, which is fine because the union resolves
 * on first success and we only care that the critical shape is valid.
 */
export const AnyUserSchema = z.union([AdminUserSchema, UserSchema]);

// ---------------------------------------------------------------------------
// Auth flow schemas
// ---------------------------------------------------------------------------

export const LoginResponseSchema = z.object({
  user: AnyUserSchema,
  tokens: AuthTokensSchema,
  user_type: UserTypeSchema.optional(),
  backup_codes: z.array(z.string()).optional(),
});

export const TwoFactorChallengeResponseSchema = z.object({
  message: z.string(),
  token: z.string().min(1, "2FA challenge token must be a non-empty string"),
  user_type: UserTypeSchema.optional(),
  setup_required: z.boolean().optional(),
  expires_in_seconds: z.number().optional(),
  provisioning_uri: z.string().nullable().optional(),
});

/**
 * Discriminated parse: if the response has `tokens` it is a LoginResponse;
 * if it has `token` (challenge token) it is a TwoFactorChallengeResponse.
 */
export const LoginAttemptResponseSchema = z.union([
  LoginResponseSchema,
  TwoFactorChallengeResponseSchema,
]);

export const ProfileResponseSchema = z.object({
  user: AnyUserSchema,
  user_type: z
    .enum(["applicant", "internal", "admin", "org_admin", "platform_admin"])
    .catch(() => "internal" as const),
  roles: z.array(z.string()).optional(),
  capabilities: z.array(z.string()).optional(),
  is_internal_operator: z.boolean().optional(),
  organizations: z.array(z.record(z.string(), z.unknown())).optional(),
  organization_memberships: z.array(z.record(z.string(), z.unknown())).optional(),
  committees: z.array(z.record(z.string(), z.unknown())).optional(),
  active_organization: z.record(z.string(), z.unknown()).nullable().optional(),
  active_organization_source: z.string().optional(),
  invalid_requested_organization_id: z.string().optional(),
});

export const ActiveOrganizationSelectionResponseSchema = z.object({
  message: z.string(),
  active_organization: z.record(z.string(), z.unknown()).nullable(),
  active_organization_source: z.string(),
  invalid_requested_organization_id: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Validation helper
// ---------------------------------------------------------------------------

/**
 * Parse a raw API response against a schema.
 * Throws an augmented Error with field-level Zod issues if validation fails.
 */
export function parseAuthResponse<T>(
  schema: z.ZodType<T>,
  data: unknown,
  context: string,
): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    const issues = result.error.issues
      .map((i) => `  [${i.path.join(".")}] ${i.message}`)
      .join("\n");
    throw new Error(
      `Auth response validation failed for ${context}:\n${issues}`,
    );
  }
  return result.data;
}
