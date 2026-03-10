import api from "./api";
import type {
  GovernanceChoicesResponse,
  GovernanceCommittee,
  GovernanceCommitteeChairReassignPayload,
  GovernanceCommitteeChairReassignResponse,
  GovernanceCommitteeMembership,
  GovernanceMemberOption,
  GovernanceOrganizationMember,
  GovernanceOrganizationBootstrapPayload,
  GovernanceOrganizationBootstrapResponse,
  GovernanceOrganizationSummaryResponse,
  PaginatedResponse,
} from "@/types";

type PaginatedOrArray<T> = PaginatedResponse<T> | T[];

const extractResults = <T>(payload: PaginatedOrArray<T>): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload?.results) ? payload.results : [];
};

const bootstrapOrganization = async (
  payload: GovernanceOrganizationBootstrapPayload,
): Promise<GovernanceOrganizationBootstrapResponse> => {
  const response = await api.post<GovernanceOrganizationBootstrapResponse>(
    "/governance/organization/bootstrap/",
    payload,
  );
  return response.data;
};

const getOrganizationSummary = async (): Promise<GovernanceOrganizationSummaryResponse> => {
  const response = await api.get<GovernanceOrganizationSummaryResponse>(
    "/governance/organization/summary/",
  );
  return response.data;
};

const listOrganizationMembers = async (params?: {
  search?: string;
  membership_role?: string;
  is_active?: boolean;
  is_default?: boolean;
  page?: number;
}): Promise<PaginatedResponse<GovernanceOrganizationMember>> => {
  const response = await api.get<PaginatedResponse<GovernanceOrganizationMember>>(
    "/governance/organization/members/",
    { params },
  );
  return response.data;
};

const updateOrganizationMember = async (
  membershipId: string,
  payload: Partial<{
    title: string;
    membership_role: string;
    is_active: boolean;
    is_default: boolean;
    left_at: string | null;
    metadata: Record<string, unknown>;
  }>,
): Promise<GovernanceOrganizationMember> => {
  const response = await api.patch<GovernanceOrganizationMember>(
    `/governance/organization/members/${membershipId}/`,
    payload,
  );
  return response.data;
};

const listCommittees = async (params?: {
  search?: string;
  committee_type?: string;
  is_active?: boolean;
  page?: number;
}): Promise<PaginatedResponse<GovernanceCommittee>> => {
  const response = await api.get<PaginatedResponse<GovernanceCommittee>>(
    "/governance/organization/committees/",
    { params },
  );
  return response.data;
};

const createCommittee = async (payload: {
  organization?: string;
  code: string;
  name: string;
  committee_type: string;
  description?: string;
  is_active?: boolean;
  metadata?: Record<string, unknown>;
}): Promise<GovernanceCommittee> => {
  const response = await api.post<GovernanceCommittee>("/governance/organization/committees/", payload);
  return response.data;
};

const getCommittee = async (committeeId: string): Promise<GovernanceCommittee> => {
  const response = await api.get<GovernanceCommittee>(`/governance/organization/committees/${committeeId}/`);
  return response.data;
};

const updateCommittee = async (
  committeeId: string,
  payload: Partial<{
    code: string;
    name: string;
    committee_type: string;
    description: string;
    is_active: boolean;
    metadata: Record<string, unknown>;
  }>,
): Promise<GovernanceCommittee> => {
  const response = await api.patch<GovernanceCommittee>(
    `/governance/organization/committees/${committeeId}/`,
    payload,
  );
  return response.data;
};

const deactivateCommittee = async (committeeId: string): Promise<void> => {
  await api.delete(`/governance/organization/committees/${committeeId}/`);
};

const listCommitteeMemberships = async (params?: {
  committee?: string;
  committee_role?: string;
  is_active?: boolean;
  page?: number;
}): Promise<PaginatedResponse<GovernanceCommitteeMembership>> => {
  const response = await api.get<PaginatedResponse<GovernanceCommitteeMembership>>(
    "/governance/organization/committee-memberships/",
    { params },
  );
  return response.data;
};

const createCommitteeMembership = async (payload: {
  committee: string;
  user: string;
  organization_membership?: string;
  committee_role: string;
  can_vote?: boolean;
  is_active?: boolean;
  metadata?: Record<string, unknown>;
}): Promise<GovernanceCommitteeMembership> => {
  const response = await api.post<GovernanceCommitteeMembership>(
    "/governance/organization/committee-memberships/",
    payload,
  );
  return response.data;
};

const updateCommitteeMembership = async (
  committeeMembershipId: string,
  payload: Partial<{
    committee_role: string;
    can_vote: boolean;
    is_active: boolean;
    left_at: string | null;
    metadata: Record<string, unknown>;
  }>,
): Promise<GovernanceCommitteeMembership> => {
  const response = await api.patch<GovernanceCommitteeMembership>(
    `/governance/organization/committee-memberships/${committeeMembershipId}/`,
    payload,
  );
  return response.data;
};

const deactivateCommitteeMembership = async (committeeMembershipId: string): Promise<void> => {
  await api.delete(`/governance/organization/committee-memberships/${committeeMembershipId}/`);
};

const reassignCommitteeChair = async (
  committeeId: string,
  payload: GovernanceCommitteeChairReassignPayload,
): Promise<GovernanceCommitteeChairReassignResponse> => {
  const response = await api.post<GovernanceCommitteeChairReassignResponse>(
    `/governance/organization/committees/${committeeId}/reassign-chair/`,
    payload,
  );
  return response.data;
};

const listMemberOptions = async (params?: {
  active_only?: boolean;
}): Promise<GovernanceMemberOption[]> => {
  const response = await api.get<PaginatedOrArray<GovernanceMemberOption>>(
    "/governance/organization/lookups/member-options/",
    { params },
  );
  return extractResults(response.data);
};

const getGovernanceChoices = async (): Promise<GovernanceChoicesResponse> => {
  const response = await api.get<GovernanceChoicesResponse>(
    "/governance/organization/lookups/choices/",
  );
  return response.data;
};

export const governanceService = {
  bootstrapOrganization,
  getOrganizationSummary,
  listOrganizationMembers,
  updateOrganizationMember,
  listCommittees,
  createCommittee,
  getCommittee,
  updateCommittee,
  deactivateCommittee,
  listCommitteeMemberships,
  createCommitteeMembership,
  updateCommitteeMembership,
  deactivateCommitteeMembership,
  reassignCommitteeChair,
  listMemberOptions,
  getGovernanceChoices,
};
