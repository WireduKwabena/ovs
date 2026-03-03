import React, { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search, ShieldAlert, ShieldCheck, UserCog, Users } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { adminService } from "@/services/admin.service";
import type { AdminManagedUser, AdminUsersResponse } from "@/types";
import { formatDate } from "@/utils/helper";

type UserTypeFilter = "all" | "admin" | "hr_manager" | "applicant";
type ActiveFilter = "all" | "active" | "inactive";

const PAGE_SIZE = 20;

const AdminUsersPage: React.FC = () => {
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [userTypeFilter, setUserTypeFilter] = useState<UserTypeFilter>("all");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [page, setPage] = useState(1);

  const [payload, setPayload] = useState<AdminUsersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoadingUserId, setActionLoadingUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const users = useMemo(() => payload?.results ?? [], [payload]);
  const totalPages = payload?.total_pages ?? 1;
  const totalCount = payload?.count ?? 0;

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await adminService.getUsers({
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
  };

  useEffect(() => {
    void fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, userTypeFilter, activeFilter, page]);

  const applySearch = () => {
    setPage(1);
    setSearchQuery(searchInput.trim());
  };

  const refresh = () => {
    void fetchUsers();
  };

  const updateUser = async (userId: string, updates: Record<string, unknown>, successMessage: string) => {
    try {
      setActionLoadingUserId(userId);
      await adminService.updateUser(userId, updates);
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
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Admin Users</h1>
              <p className="mt-1 text-sm text-gray-600">
                Manage platform users, access states, and account security controls.
              </p>
            </div>
            <Button type="button" variant="outline" onClick={refresh} disabled={loading}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div className="md:col-span-2">
              <label htmlFor="user-search" className="mb-1 block text-sm font-medium text-gray-700">
                Search
              </label>
              <div className="flex gap-2">
                <Input
                  id="user-search"
                  value={searchInput}
                  placeholder="name or email"
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      applySearch();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={applySearch}>
                  <Search className="h-4 w-4" />
                  Search
                </Button>
              </div>
            </div>

            <div>
              <label htmlFor="filter-type" className="mb-1 block text-sm font-medium text-gray-700">
                User Type
              </label>
              <Select
                value={userTypeFilter}
                onValueChange={(value) => {
                  setPage(1);
                  setUserTypeFilter(value as UserTypeFilter);
                }}
              >
                <SelectTrigger id="filter-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="hr_manager">HR Manager</SelectItem>
                  <SelectItem value="applicant">Applicant</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label htmlFor="filter-active" className="mb-1 block text-sm font-medium text-gray-700">
                Status
              </label>
              <Select
                value={activeFilter}
                onValueChange={(value) => {
                  setPage(1);
                  setActiveFilter(value as ActiveFilter);
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
        </section>

        <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <p className="text-sm text-gray-600">
              {loading ? "Loading users..." : `Total users: ${totalCount}`}
            </p>
            <p className="text-sm text-gray-600">Page {page} of {totalPages}</p>
          </div>

          {error ? (
            <div className="p-8 text-center">
              <ShieldAlert className="mx-auto h-8 w-8 text-red-500" />
              <p className="mt-2 text-sm font-medium text-red-600">{error}</p>
            </div>
          ) : users.length === 0 ? (
            <div className="p-10 text-center text-gray-600">
              <Users className="mx-auto h-10 w-10 text-gray-300" />
              <p className="mt-3">No users found for this filter.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">User</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Role</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">2FA</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Created</th>
                    <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {users.map((user: AdminManagedUser) => {
                    const busy = actionLoadingUserId === user.id;
                    return (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm">
                          <div className="font-medium text-gray-900">{user.full_name || "Unnamed User"}</div>
                          <div className="text-gray-500">{user.email}</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-700">
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
                              <SelectItem value="hr_manager">HR Manager</SelectItem>
                              <SelectItem value="applicant">Applicant</SelectItem>
                            </SelectContent>
                          </Select>
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                              user.is_active
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-gray-200 text-gray-700"
                            }`}
                          >
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span className="inline-flex items-center gap-1 text-gray-700">
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
                        <td className="px-6 py-4 text-sm text-gray-600">{formatDate(user.created_at)}</td>
                        <td className="px-6 py-4 text-right">
                          <div className="inline-flex flex-wrap justify-end gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
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
          )}

          <div className="flex items-center justify-between border-t border-gray-100 px-6 py-4">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((value) => value + 1)}
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
