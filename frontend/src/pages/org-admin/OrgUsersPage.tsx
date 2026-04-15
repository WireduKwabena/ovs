import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  Users,
  Search,
  RefreshCw,
  Filter,
  XCircle,
  CheckCircle2,
  MoreVertical,
  Shield,
  Copy,
  ShieldOff,
  UserCog,
  Check,
} from "lucide-react";
import { toast } from "react-toastify";

import { adminService } from "@/services/admin.service";
import { governanceService } from "@/services/governance.service";
import type { AdminManagedUser, GovernanceOrganizationMember } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const USER_TYPE_OPTIONS = ["admin", "internal", "applicant"];

const MEMBERSHIP_ROLES: { value: string; label: string }[] = [
  { value: "registry_admin", label: "Registry Admin" },
  { value: "vetting_officer", label: "Vetting Officer" },
  { value: "committee_member", label: "Committee Member" },
  { value: "committee_chair", label: "Committee Chair" },
  { value: "appointing_authority", label: "Appointing Authority" },
  { value: "publication_officer", label: "Publication Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "nominee", label: "Nominee" },
];

const OrgUsersPage: React.FC = () => {
  const { orgId } = useParams<{ orgId: string }>();
  const organizationId = String(orgId || "").trim();
  const [searchParams, setSearchParams] = useSearchParams();

  const [users, setUsers] = useState<AdminManagedUser[]>([]);
  // Map from user ID → membership record
  const [membershipMap, setMembershipMap] = useState<Map<string, GovernanceOrganizationMember>>(
    new Map(),
  );
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!openMenuId) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [openMenuId]);

  const [searchFilter, setSearchFilter] = useState(
    () => searchParams.get("q") || "",
  );
  const [userTypeFilter, setUserTypeFilter] = useState(
    () => searchParams.get("user_type") || "",
  );
  const [isActiveFilter, setIsActiveFilter] = useState(() => {
    const v = searchParams.get("is_active");
    return v === "true" ? "true" : v === "false" ? "false" : "";
  });

  const hasActiveFilters = Boolean(
    searchFilter || userTypeFilter || isActiveFilter !== "",
  );

  const fetchUsers = useCallback(
    async (isSilent = false) => {
      if (!organizationId) return;
      if (!isSilent) setLoading(true);
      else setRefreshing(true);

      try {
        const isActiveParsed =
          isActiveFilter === "true"
            ? true
            : isActiveFilter === "false"
              ? false
              : undefined;

        const [usersResponse, membershipsResponse] = await Promise.all([
          adminService.getOrgUsers(organizationId, {
            q: searchFilter || undefined,
            user_type:
              (userTypeFilter as "admin" | "internal" | "applicant") ||
              undefined,
            is_active: isActiveParsed,
          }),
          governanceService.listOrganizationMembers({ is_active: undefined }),
        ]);

        setUsers(usersResponse.results);

        const map = new Map<string, GovernanceOrganizationMember>();
        for (const m of membershipsResponse.results) {
          map.set(m.user, m);
        }
        setMembershipMap(map);
      } catch {
        toast.error("Failed to load organization users");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [organizationId, searchFilter, userTypeFilter, isActiveFilter],
  );

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  const applyFilters = () => {
    const params: Record<string, string> = {};
    if (searchFilter) params.q = searchFilter;
    if (userTypeFilter) params.user_type = userTypeFilter;
    if (isActiveFilter !== "") params.is_active = isActiveFilter;
    setSearchParams(params);
  };

  const clearFilters = () => {
    setSearchFilter("");
    setUserTypeFilter("");
    setIsActiveFilter("");
    setSearchParams({});
  };

  const handleCopyEmail = async (email: string) => {
    setOpenMenuId(null);
    try {
      await navigator.clipboard.writeText(email);
      toast.success("Email copied to clipboard");
    } catch {
      toast.error("Could not copy email");
    }
  };

  const handleResetTwoFactor = async (user: AdminManagedUser) => {
    setOpenMenuId(null);
    setUpdatingId(user.id);
    try {
      const updated = await adminService.updateOrgUser(organizationId, user.id, {
        reset_two_factor: true,
      });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
      toast.success(
        `Two-factor authentication reset for ${user.full_name || user.email}`,
      );
    } catch {
      toast.error("Failed to reset two-factor authentication");
    } finally {
      setUpdatingId(null);
    }
  };

  const handleChangeMembershipRole = async (
    user: AdminManagedUser,
    newRole: string,
  ) => {
    setOpenMenuId(null);
    const membership = membershipMap.get(user.id);
    if (!membership) {
      toast.error("No membership record found for this user");
      return;
    }
    setUpdatingId(user.id);
    try {
      const updated = await governanceService.updateOrganizationMember(
        membership.id,
        { membership_role: newRole },
      );
      setMembershipMap((prev) => {
        const next = new Map(prev);
        next.set(user.id, updated);
        return next;
      });
      const roleLabel =
        MEMBERSHIP_ROLES.find((r) => r.value === newRole)?.label ?? newRole;
      toast.success(
        `${user.full_name || user.email} role changed to ${roleLabel}`,
      );
    } catch {
      toast.error("Failed to update membership role");
    } finally {
      setUpdatingId(null);
    }
  };

  const handleToggleStatus = async (user: AdminManagedUser) => {
    setUpdatingId(user.id);
    try {
      const updated = await adminService.updateOrgUser(organizationId, user.id, {
        is_active: !user.is_active,
      });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
      toast.success(`${user.full_name || user.email} status updated`);
    } catch {
      toast.error("Failed to update user status");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-8 py-6 px-4 md:px-8 lg:px-12 md:py-8 lg:py-10">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Organization Users
          </h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Manage user accounts within the currently selected organization.
          </p>
        </div>
        <Button
          variant="outline"
          className="rounded-xl gap-2"
          onClick={() => void fetchUsers(true)}
          disabled={refreshing}
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card className="p-4 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <label
                htmlFor="user-search"
                className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1"
              >
                Search
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <input
                  id="user-search"
                  aria-label="search"
                  type="text"
                  className="w-full bg-background/50 border border-border/70 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="Search by name or email..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                />
              </div>
            </div>

            <div className="flex-1 min-w-[160px]">
              <label
                htmlFor="user-type-filter"
                className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1"
              >
                User Type
              </label>
              <select
                id="user-type-filter"
                className="w-full bg-background/50 border border-border/70 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                value={userTypeFilter}
                onChange={(e) => setUserTypeFilter(e.target.value)}
              >
                <option value="">All Types</option>
                {USER_TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-w-[160px]">
              <label
                htmlFor="active-filter"
                className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1"
              >
                Status
              </label>
              <select
                id="active-filter"
                className="w-full bg-background/50 border border-border/70 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                value={isActiveFilter}
                onChange={(e) => setIsActiveFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button className="rounded-xl gap-2" onClick={applyFilters}>
              <Filter className="h-4 w-4" />
              Apply Filters
            </Button>
            {hasActiveFilters && (
              <>
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Active Filters
                </span>
                <Button
                  variant="outline"
                  className="rounded-xl gap-2 text-destructive border-destructive/30"
                  aria-label="clear user filters"
                  onClick={clearFilters}
                >
                  <XCircle className="h-4 w-4" />
                  Clear User Filters
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* Users List */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : users.length === 0 ? (
          <Card className="p-12 text-center rounded-2xl border-dashed border-border/70 bg-muted/20">
            <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              No users found for the selected filters.
            </p>
          </Card>
        ) : (
          users.map((u) => {
            const membership = membershipMap.get(u.id);
            const currentRole = membership?.membership_role ?? null;
            const currentRoleLabel =
              MEMBERSHIP_ROLES.find((r) => r.value === currentRole)?.label ??
              currentRole;

            return (
              <Card
                key={u.id}
                className="p-5 rounded-2xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-xl bg-muted flex items-center justify-center font-bold text-muted-foreground">
                      {(u.full_name || u.email).charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-0.5">
                        <span className="text-sm font-bold">
                          {u.full_name || u.email}
                        </span>
                        <Badge
                          variant="outline"
                          className="rounded-full text-[10px] font-bold uppercase tracking-widest"
                        >
                          {u.user_type}
                        </Badge>
                        {currentRoleLabel && (
                          <Badge className="bg-primary/10 text-primary hover:bg-primary/10 rounded-full border-primary/20 text-[10px]">
                            {currentRoleLabel}
                          </Badge>
                        )}
                        {u.is_active ? (
                          <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10 rounded-full border-emerald-500/20 text-[10px]">
                            Active
                          </Badge>
                        ) : (
                          <Badge className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/10 rounded-full border-rose-500/20 text-[10px]">
                            Inactive
                          </Badge>
                        )}
                        {u.is_superuser && (
                          <Badge className="bg-indigo-500/10 text-indigo-500 border-indigo-500/20 rounded-full text-[10px]">
                            <Shield className="h-3 w-3 mr-1 inline" />
                            Superuser
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                      {u.last_login && (
                        <p className="text-[10px] text-muted-foreground mt-0.5">
                          Last login:{" "}
                          {new Date(u.last_login).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end md:self-center">
                    <Button
                      variant={u.is_active ? "outline" : "default"}
                      className="rounded-xl gap-2 h-9 text-xs font-bold"
                      disabled={updatingId === u.id}
                      onClick={() => handleToggleStatus(u)}
                    >
                      {u.is_active ? (
                        <XCircle className="h-3.5 w-3.5" />
                      ) : (
                        <CheckCircle2 className="h-3.5 w-3.5" />
                      )}
                      {updatingId === u.id
                        ? "Updating..."
                        : u.is_active
                          ? "Suspend"
                          : "Activate"}
                    </Button>
                    <div
                      className="relative"
                      ref={openMenuId === u.id ? menuRef : null}
                    >
                      <Button
                        variant="ghost"
                        size="icon"
                        className="rounded-xl h-9 w-9"
                        aria-label="More actions"
                        disabled={updatingId === u.id}
                        onClick={() =>
                          setOpenMenuId((prev) =>
                            prev === u.id ? null : u.id,
                          )
                        }
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>

                      {openMenuId === u.id && (
                        <div className="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-xl border border-border/70 bg-background shadow-lg py-1">
                          {/* Copy email */}
                          <button
                            className="flex w-full items-center gap-2.5 px-3 py-2 text-xs font-medium hover:bg-accent transition-colors"
                            onClick={() => void handleCopyEmail(u.email)}
                          >
                            <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                            Copy Email
                          </button>

                          {/* Reset 2FA */}
                          {u.is_two_factor_enabled && (
                            <button
                              className="flex w-full items-center gap-2.5 px-3 py-2 text-xs font-medium hover:bg-accent transition-colors text-amber-600"
                              onClick={() => void handleResetTwoFactor(u)}
                            >
                              <ShieldOff className="h-3.5 w-3.5" />
                              Reset 2FA
                            </button>
                          )}

                          {/* Change membership role */}
                          {membership && (
                            <div className="border-t border-border/50 mt-1 pt-1">
                              <p className="flex items-center gap-2 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                                <UserCog className="h-3 w-3" />
                                Org Role
                              </p>
                              {MEMBERSHIP_ROLES.map((role) => (
                                <button
                                  key={role.value}
                                  className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium hover:bg-accent transition-colors disabled:opacity-40"
                                  disabled={currentRole === role.value}
                                  onClick={() =>
                                    void handleChangeMembershipRole(
                                      u,
                                      role.value,
                                    )
                                  }
                                >
                                  <span>{role.label}</span>
                                  {currentRole === role.value && (
                                    <Check className="h-3 w-3 text-primary" />
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
};

export default OrgUsersPage;
