import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RefreshCw, Search, ShieldAlert, ShieldCheck, UserCog, Users } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { adminService } from "@/services/admin.service";
import type { AdminManagedUser, AdminUsersResponse } from "@/types";
import { formatDate } from "@/utils/helper";
import { applyQueryUpdates } from "@/utils/queryParams";

type UserTypeFilter = "all" | "admin" | "internal" | "applicant";
type ActiveFilter = "all" | "active" | "inactive";

const PAGE_SIZE = 20;
const USER_TYPE_LABELS: Record<Exclude<UserTypeFilter, "all">, string> = {
  admin: "Admin",
  internal: "Operations User",
  applicant: "Applicant",
};

const parsePage = (value: string | null): number => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
};

const parseUserTypeFilter = (value: string | null): UserTypeFilter => {
  if (value === "admin" || value === "internal" || value === "applicant") {
    return value;
  }
  return "all";
};

const parseActiveFilter = (value: string | null): ActiveFilter => {
  if (value === "true" || value === "1") {
    return "active";
  }
  if (value === "false" || value === "0") {
    return "inactive";
  }
  return "all";
};

const formatUserTypeFilter = (value: UserTypeFilter): string => {
  if (value === "all") {
    return "All";
  }
  return USER_TYPE_LABELS[value];
};

export interface AdminUsersPageProps {
  scope?: "platform" | "org";
  organizationId?: string | null;
  title?: string;
  description?: string;
}

const AdminUsersPage: React.FC<AdminUsersPageProps> = ({
  scope = "platform",
  organizationId = null,
  title = "Admin Users",
  description = "Manage platform users, access states, and account security controls.",
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parsePage(searchParams.get("page"));
  const searchQuery = (searchParams.get("q") || "").trim();
  const userTypeFilter = parseUserTypeFilter(searchParams.get("user_type"));
  const activeFilter = parseActiveFilter(searchParams.get("is_active"));

  const [searchInput, setSearchInput] = useState(searchQuery);

  const [payload, setPayload] = useState<AdminUsersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoadingUserId, setActionLoadingUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isPlatformScope = scope === "platform";

  const users = useMemo(() => payload?.results ?? [], [payload]);
  const totalPages = payload?.total_pages ?? 1;
  const totalCount = payload?.count ?? 0;
  const isSearchFilterActive = searchQuery.length > 0;
  const isUserTypeFilterActive = userTypeFilter !== "all";
  const isActiveFilterActive = activeFilter !== "all";
  const hasUserFilters = isSearchFilterActive || isUserTypeFilterActive || isActiveFilterActive;

  const fetchUsers = useCallback(async () => {
    if (scope === "org" && !organizationId) {
      setPayload(null);
      setError("Active organization context is required to load organization users.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const getUsersForScope =
        scope === "org" && organizationId
          ? (params: Parameters<typeof adminService.getOrgUsers>[1]) =>
              adminService.getOrgUsers(organizationId, params)
          : adminService.getUsers;

      const response = await getUsersForScope({
        q: searchQuery || undefined,
        user_type: userTypeFilter === "all" ? undefined : userTypeFilter,
        is_active:
          activeFilter === "all"
            ? undefined
            : activeFilter === "active",
        page,
        page_size: PAGE_SIZE,
        ordering: "-created_at",
      });
      setPayload(response);
    } catch (fetchError: any) {
      setError(fetchError?.message || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  }, [activeFilter, organizationId, page, scope, searchQuery, userTypeFilter]);

  const updateQuery = (updates: Record<string, string | null>, options: { keepPage?: boolean } = {}) => {
    const nextParams = applyQueryUpdates(searchParams, updates, {
      keepPage: options.keepPage ?? false,
      pageParam: "page",
      resetPageTo: "1",
    });

    setSearchParams(nextParams, { replace: true });
  };

  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  const applySearch = () => {
    updateQuery({ q: searchInput.trim() || null });
  };

  const refresh = () => {
    void fetchUsers();
  };

  const updateUser = async (userId: string, updates: Record<string, unknown>, successMessage: string) => {
    try {
      setActionLoadingUserId(userId);
      if (scope === "org" && organizationId) {
        await adminService.updateOrgUser(organizationId, userId, updates);
      } else {
        await adminService.updateUser(userId, updates);
      }
      toast.success(successMessage);
      await fetchUsers();
    } catch (actionError: any) {
      toast.error(actionError?.message || "User update failed.");
    } finally {
      setActionLoadingUserId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-6 xl:px-8">
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
              <p className="mt-1 text-sm text-slate-800">
                {description}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
              onClick={refresh}
              disabled={loading}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div className="md:col-span-2">
              <label htmlFor="user-search" className="mb-1 block text-sm font-medium text-slate-800">
                Search
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="user-search"
                  value={searchInput}
                  placeholder="name or email"
                  className="text-slate-900 placeholder:text-slate-500 placeholder:opacity-100"
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      applySearch();
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                  onClick={applySearch}
                >
                  <Search className="h-4 w-4" />
                  Search
                </Button>
              </div>
            </div>

            <div>
              <label htmlFor="filter-type" className="mb-1 block text-sm font-medium text-slate-800">
                User Type
              </label>
              <Select
                value={userTypeFilter}
                onValueChange={(value) => {
                  updateQuery({ user_type: value });
                }}
              >
                <SelectTrigger id="filter-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="internal">Operations User</SelectItem>
                  <SelectItem value="applicant">Applicant</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label htmlFor="filter-active" className="mb-1 block text-sm font-medium text-slate-800">
                Status
              </label>
              <Select
                value={activeFilter}
                onValueChange={(value) => {
                  updateQuery({
                    is_active:
                      value === "all" ? null : value === "active" ? "true" : "false",
                  });
                }}
              >
                <SelectTrigger id="filter-active">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {hasUserFilters ? (
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">Active filters</span>
                {isSearchFilterActive ? (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchInput("");
                      updateQuery({ q: null });
                    }}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    Search: {searchQuery} x
                  </button>
                ) : null}
                {isUserTypeFilterActive ? (
                  <button
                    type="button"
                    onClick={() => updateQuery({ user_type: null })}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    User Type: {formatUserTypeFilter(userTypeFilter)} x
                  </button>
                ) : null}
                {isActiveFilterActive ? (
                  <button
                    type="button"
                    onClick={() => updateQuery({ is_active: null })}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    Status: {activeFilter} x
                  </button>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  className="ml-auto border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
                  onClick={() => {
                    setSearchInput("");
                    updateQuery({
                      q: null,
                      user_type: null,
                      is_active: null,
                    });
                  }}
                >
                  Clear user filters
                </Button>
              </div>
            </div>
          ) : null}
        </section>

        <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="flex flex-col gap-1 border-b border-gray-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-800">
              {loading ? "Loading users..." : `Total users: ${totalCount}`}
            </p>
            <p className="text-sm text-slate-800">Page {page} of {totalPages}</p>
          </div>

          {error ? (
            <div className="p-8 text-center">
              <ShieldAlert className="mx-auto h-8 w-8 text-red-500" />
              <p className="mt-2 text-sm font-medium text-red-600">{error}</p>
            </div>
          ) : users.length === 0 ? (
            <div className="p-10 text-center text-slate-800">
              <Users className="mx-auto h-10 w-10 text-slate-800" />
              <p className="mt-3">No users found for this filter.</p>
            </div>
          ) : (
            <>
              <div className="md:hidden px-4 pt-3 text-xs text-slate-800">
                Swipe horizontally to view all user columns.
              </div>
              <div className="overflow-x-auto">
              <table className="min-w-[980px] w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="sticky left-0 z-20 min-w-[260px] bg-gray-50 px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">User</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Role</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">2FA</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Created</th>
                    <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-800">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {users.map((user: AdminManagedUser) => {
                    const busy = actionLoadingUserId === user.id;
                    return (
                      <tr key={user.id} className="hover:bg-slate-100">
                        <td className="sticky left-0 z-10 min-w-[260px] bg-white px-6 py-4 text-sm">
                          <div className="font-medium text-gray-900">{user.full_name || "Unnamed User"}</div>
                          <div className="text-slate-800">{user.email}</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-800">
                          {isPlatformScope ? (
                            <Select
                              value={user.user_type}
                              onValueChange={(nextRole) => {
                                void updateUser(
                                  user.id,
                                  { user_type: nextRole },
                                  "User role updated.",
                                );
                              }}
                              disabled={busy}
                            >
                              <SelectTrigger className="w-40">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="admin">Admin</SelectItem>
                                <SelectItem value="internal">Operations User</SelectItem>
                                <SelectItem value="applicant">Applicant</SelectItem>
                              </SelectContent>
                            </Select>
                          ) : (
                            <div className="space-y-1">
                              <span className="inline-flex rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-800">
                                {USER_TYPE_LABELS[user.user_type] || "Applicant"}
                              </span>
                              <p className="text-xs text-slate-600">
                                Role changes are managed from platform administration.
                              </p>
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                              user.is_active
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-slate-200 text-slate-800"
                            }`}
                          >
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span className="inline-flex items-center gap-1 text-slate-800">
                            {user.is_two_factor_enabled ? (
                              <>
                                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                                Enabled
                              </>
                            ) : (
                              <>
                                <ShieldAlert className="h-4 w-4 text-amber-600" />
                                Disabled
                              </>
                            )}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-800">{formatDate(user.created_at)}</td>
                        <td className="px-6 py-4 text-right">
                          <div className="inline-flex flex-wrap justify-end gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="border-slate-700 text-slate-900 hover:bg-slate-100"
                              disabled={busy}
                              onClick={() =>
                                void updateUser(
                                  user.id,
                                  { is_active: !user.is_active },
                                  user.is_active ? "User deactivated." : "User activated.",
                                )
                              }
                            >
                              <UserCog className="h-4 w-4" />
                              {user.is_active ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="border-slate-700 text-slate-900 hover:bg-slate-100"
                              disabled={busy}
                              onClick={() =>
                                void updateUser(
                                  user.id,
                                  { reset_two_factor: true },
                                  "2FA reset completed.",
                                )
                              }
                            >
                              Reset 2FA
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            </>
          )}

          <div className="flex flex-col gap-2 border-t border-gray-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="button"
              variant="outline"
              className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() =>
                updateQuery({ page: String(Math.max(1, page - 1)) }, { keepPage: true })
              }
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() =>
                updateQuery({ page: String(page + 1) }, { keepPage: true })
              }
            >
              Next
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminUsersPage;

