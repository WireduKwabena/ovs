// src/pages/RubricsPage.tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Filter, Edit, Trash2, Copy, Info } from "lucide-react";

import { Loader } from "@/components/common/Loader";
import { HelpTooltip } from "@/components/common/FieldHelp";
import { rubricService } from "@/services/rubric.service";
import { toast } from "react-toastify";
import type { VettingRubric } from "@/types";
import { formatDate } from "@/utils/helper";
import { useAuth } from "@/hooks/useAuth";

export const RubricsPage: React.FC = () => {
  const navigate = useNavigate();
  const { canManageRubrics } = useAuth();
  const [rubrics, setRubrics] = useState<VettingRubric[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    loadRubrics();
  }, []);

  const loadRubrics = async () => {
    try {
      setLoading(true);
      const data = await rubricService.getAll();
      setRubrics(data);
    } catch {
      toast.error("Failed to load rubrics");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this rubric?")) return;

    try {
      await rubricService.delete(id);
      toast.success("Rubric deleted successfully");
      loadRubrics();
    } catch {
      toast.error("Failed to delete rubric");
    }
  };

  const handleDuplicate = async (id: string) => {
    try {
      await rubricService.duplicate(id);
      toast.success("Rubric duplicated successfully");
      loadRubrics();
    } catch {
      toast.error("Failed to duplicate rubric");
    }
  };

  const handleActivate = async (id: string) => {
    try {
      await rubricService.activate(id);
      toast.success("Rubric activated successfully");
      loadRubrics();
    } catch {
      toast.error("Failed to activate rubric");
    }
  };

  const filteredRubrics = rubrics.filter((rubric) => {
    const matchesSearch = rubric.name
      .toLowerCase()
      .includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || rubric.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "draft":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "archived":
        return "bg-gray-100 text-gray-800 border-gray-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Vetting Rubrics
            </h1>
            <p className="text-slate-700 mt-1">
              Create and manage evaluation criteria
            </p>
          </div>
          {canManageRubrics ? (
            <button
              onClick={() => navigate("/rubrics/new")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-semibold transition-colors"
            >
              <Plus className="w-5 h-5" />
              Create Rubric
            </button>
          ) : null}
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            Hover or focus the <Info className="mx-1 inline h-4 w-4 align-text-bottom" /> icons to learn what each control does.
          </div>
          {!canManageRubrics ? (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              You have read-only rubric access. Create, edit, activate, and delete actions are limited to authorized internal operators.
            </div>
          ) : null}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="mb-2 flex items-center gap-1.5">
                <label htmlFor="rubrics-search" className="text-sm font-medium text-slate-800">
                  Search Rubrics
                </label>
                <HelpTooltip text="Find rubrics by name. Use this to quickly locate existing templates before creating a new one." />
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5" />
                <input
                  id="rubrics-search"
                  type="text"
                  placeholder="Search rubrics..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5">
                <label htmlFor="rubrics-status-filter" className="text-sm font-medium text-slate-800">
                  Status Filter
                </label>
                <HelpTooltip text="Filter rubrics by lifecycle status. Active rubrics are available for campaign use." />
              </div>
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5" />
                <select
                  id="rubrics-status-filter"
                  aria-label="Filter rubrics by status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 appearance-none"
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Rubrics List */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <Loader size="lg" />
          </div>
        ) : filteredRubrics.length > 0 ? (
          <div className="grid gap-6">
            {filteredRubrics.map((rubric) => (
              <div
                key={rubric.id}
                className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">
                        {rubric.name}
                      </h3>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(rubric.status!)}`}
                      >
                        {rubric.status}
                      </span>
                    </div>
                    {rubric.description && (
                      <p className="text-slate-700 mb-2">{rubric.description}</p>
                    )}
                    <div className="flex gap-4 text-sm text-slate-700">
                      <span>Type: {rubric.rubric_type}</span>
                      {rubric.department && (
                        <span>Department: {rubric.department}</span>
                      )}
                      <span>Passing Score: {rubric.passing_score}%</span>
                      <span>{rubric.criteria?.length || 0} Criteria</span>
                    </div>
                    {rubric.created_at && (
                      <p className="text-xs text-slate-700 mt-2">
                        Created: {formatDate(rubric.created_at)}
                      </p>
                    )}
                  </div>

                  {canManageRubrics ? (
                    <div className="flex gap-2 ml-4">
                      {rubric.status !== "active" && (
                        <button
                          onClick={() => handleActivate(rubric.id!)}
                          className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                          title="Activate rubric for campaign use"
                        >
                          <Plus className="w-5 h-5" />
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/rubrics/${rubric.id}/edit`)}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Edit rubric details and criteria"
                      >
                        <Edit className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDuplicate(rubric.id!)}
                        className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        title="Duplicate rubric as a starting template"
                      >
                        <Copy className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDelete(rubric.id!)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete rubric permanently"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No rubrics found
            </h3>
            <p className="text-slate-700 mb-6">
              {searchTerm || statusFilter !== "all"
                ? "Try adjusting your filters"
                : "Get started by creating your first rubric"}
            </p>
            {!searchTerm && statusFilter === "all" && canManageRubrics && (
              <button
                onClick={() => navigate("/rubrics/new")}
                className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium"
              >
                <Plus className="w-5 h-5" />
                Create Rubric
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};


