import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, GitBranch, Plus } from "lucide-react";
import type {
  ApprovalStage,
  ApprovalStageTemplate,
  AppointmentStatus,
} from "@/types";
import { governmentService } from "@/services/government.service";
import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { getWorkspacePath } from "@/utils/appPaths";

const SELECT_FIELD_CLASS =
  "w-full rounded-lg border border-slate-700 bg-white px-3 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-400 outline-none";

const EXERCISE_TYPE_OPTIONS = [
  "ministerial",
  "judicial",
  "board",
  "local_gov",
  "diplomatic",
  "security",
];

const REQUIRED_ROLE_OPTIONS = [
  "vetting_officer",
  "committee_member",
  "committee_chair",
  "appointing_authority",
  "registry_admin",
  "publication_officer",
  "auditor",
];

const APPOINTMENT_STATUS_OPTIONS: AppointmentStatus[] = [
  "nominated",
  "under_vetting",
  "committee_review",
  "confirmation_pending",
  "appointed",
  "rejected",
  "withdrawn",
  "serving",
  "exited",
];

const statusLabel = (status: AppointmentStatus): string =>
  status
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");

const RouteTemplatesPage: React.FC = () => {
  const { canManageRegistry } = useAuth();

  const [stageTemplates, setStageTemplates] = useState<ApprovalStageTemplate[]>(
    [],
  );
  const [stages, setStages] = useState<ApprovalStage[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templateCreating, setTemplateCreating] = useState(false);
  const [stageCreating, setStageCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [templateForm, setTemplateForm] = useState({
    name: "",
    exercise_type: "ministerial",
  });
  const [stageForm, setStageForm] = useState({
    template: "",
    order: 1,
    name: "",
    required_role: "vetting_officer",
    is_required: true,
    maps_to_status: "under_vetting" as AppointmentStatus,
  });

  const loadRouteTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const [templates, stageRows] = await Promise.all([
        governmentService.listApprovalStageTemplates(),
        governmentService.listApprovalStages(),
      ]);
      setStageTemplates(templates);
      setStages(stageRows);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to load appointment route templates.",
      );
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRouteTemplates();
  }, [loadRouteTemplates]);

  useEffect(() => {
    if (!stageForm.template && stageTemplates.length > 0) {
      setStageForm((previous) => ({
        ...previous,
        template: stageTemplates[0].id,
      }));
    }
  }, [stageForm.template, stageTemplates]);

  const stagesByTemplate = useMemo(() => {
    return stages.reduce<Record<string, ApprovalStage[]>>((acc, stage) => {
      if (!acc[stage.template]) {
        acc[stage.template] = [];
      }
      acc[stage.template].push(stage);
      return acc;
    }, {});
  }, [stages]);

  const handleCreateTemplate = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    if (!templateForm.name.trim()) {
      setError("Template name is required.");
      return;
    }
    setTemplateCreating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const created = await governmentService.createApprovalStageTemplate({
        name: templateForm.name.trim(),
        exercise_type: templateForm.exercise_type,
      });
      setTemplateForm((previous) => ({ ...previous, name: "" }));
      setStageForm((previous) => ({ ...previous, template: created.id }));
      await loadRouteTemplates();
      setSuccessMessage(`Route template "${created.name}" created.`);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to create route template.",
      );
    } finally {
      setTemplateCreating(false);
    }
  };

  const handleCreateStage = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      !stageForm.template ||
      !stageForm.name.trim() ||
      Number(stageForm.order) <= 0
    ) {
      setError("Template, stage name, and order are required.");
      return;
    }
    setStageCreating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await governmentService.createApprovalStage({
        template: stageForm.template,
        order: Number(stageForm.order),
        name: stageForm.name.trim(),
        required_role: stageForm.required_role.trim(),
        is_required: stageForm.is_required,
        maps_to_status: stageForm.maps_to_status,
      });
      setStageForm((previous) => ({
        ...previous,
        order: Number(previous.order) + 1,
        name: "",
      }));
      await loadRouteTemplates();
      setSuccessMessage("Route stage added.");
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to create route stage.",
      );
    } finally {
      setStageCreating(false);
    }
  };

  if (!canManageRegistry) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-6 xl:px-8">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-800">
          Your account does not have access to configure appointment route
          templates.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
      {/* Page header */}
      <section className="rounded-2xl bg-slate-900 text-white p-6">
        <div className="flex flex-wrap items-center gap-4 justify-between">
          <div>
            <h1 className="text-2xl font-semibold inline-flex items-center gap-2">
              <GitBranch className="w-6 h-6" />
              Appointment Route Templates
            </h1>
            <p className="mt-1 text-slate-200">
              Define the approval chain stages that govern how nomination files
              advance through vetting, committee review, and final appointment.
            </p>
          </div>
          <Link
            to={getWorkspacePath("campaigns")}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Exercises
          </Link>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
          {successMessage}
        </div>
      )}

      {/* Create forms */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Create template */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold inline-flex items-center gap-2">
            <Plus className="w-5 h-5 text-indigo-600" />
            Create Route Template
          </h2>
          <p className="mb-4 text-sm text-slate-700">
            A route template defines the type of appointment exercise it applies
            to. Add stages to it below to build the full approval chain.
          </p>
          <form onSubmit={handleCreateTemplate} className="space-y-4">
            <div>
              <label
                htmlFor="rt-template-name"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Template Name <span className="text-red-500">*</span>
              </label>
              <Input
                id="rt-template-name"
                value={templateForm.name}
                onChange={(event) =>
                  setTemplateForm((previous) => ({
                    ...previous,
                    name: event.target.value,
                  }))
                }
                placeholder="Ministerial Standard Chain"
                required
              />
            </div>
            <div>
              <label
                htmlFor="rt-template-exercise-type"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Exercise Type
              </label>
              <select
                id="rt-template-exercise-type"
                value={templateForm.exercise_type}
                onChange={(event) =>
                  setTemplateForm((previous) => ({
                    ...previous,
                    exercise_type: event.target.value,
                  }))
                }
                aria-label="Route template exercise type"
                title="Route template exercise type"
                className={SELECT_FIELD_CLASS}
              >
                {EXERCISE_TYPE_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value
                      .split("_")
                      .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
                      .join(" ")}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={templateCreating}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {templateCreating ? "Creating..." : "Create Route Template"}
            </button>
          </form>
        </div>

        {/* Add stage to template */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold inline-flex items-center gap-2">
            <Plus className="w-5 h-5 text-indigo-600" />
            Add Stage to Template
          </h2>
          <p className="mb-4 text-sm text-slate-700">
            Each stage represents one approval step. Stages are executed in
            order and each maps to a nomination file status transition.
          </p>
          <form onSubmit={handleCreateStage} className="space-y-4">
            <div>
              <label
                htmlFor="rt-stage-template"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Route Template <span className="text-red-500">*</span>
              </label>
              <select
                id="rt-stage-template"
                value={stageForm.template}
                onChange={(event) =>
                  setStageForm((previous) => ({
                    ...previous,
                    template: event.target.value,
                  }))
                }
                aria-label="Route stage template"
                title="Route stage template"
                className={SELECT_FIELD_CLASS}
              >
                <option value="">Select template</option>
                {stageTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="rt-stage-order"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Order <span className="text-red-500">*</span>
                </label>
                <Input
                  id="rt-stage-order"
                  type="number"
                  min={1}
                  value={stageForm.order}
                  onChange={(event) =>
                    setStageForm((previous) => ({
                      ...previous,
                      order: Number(event.target.value) || 1,
                    }))
                  }
                />
              </div>
              <div>
                <label
                  htmlFor="rt-stage-maps-to-status"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Maps to Status
                </label>
                <select
                  id="rt-stage-maps-to-status"
                  value={stageForm.maps_to_status}
                  onChange={(event) =>
                    setStageForm((previous) => ({
                      ...previous,
                      maps_to_status: event.target.value as AppointmentStatus,
                    }))
                  }
                  aria-label="Route stage maps to status"
                  title="Route stage maps to status"
                  className={SELECT_FIELD_CLASS}
                >
                  {APPOINTMENT_STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {statusLabel(status)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label
                htmlFor="rt-stage-name"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Stage Name <span className="text-red-500">*</span>
              </label>
              <Input
                id="rt-stage-name"
                value={stageForm.name}
                onChange={(event) =>
                  setStageForm((previous) => ({
                    ...previous,
                    name: event.target.value,
                  }))
                }
                placeholder="Committee Review"
                required
              />
            </div>
            <div>
              <label
                htmlFor="rt-stage-required-role"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Required Role
              </label>
              <select
                id="rt-stage-required-role"
                value={stageForm.required_role}
                onChange={(event) =>
                  setStageForm((previous) => ({
                    ...previous,
                    required_role: event.target.value,
                  }))
                }
                aria-label="Route stage required role"
                title="Route stage required role"
                className={SELECT_FIELD_CLASS}
              >
                {REQUIRED_ROLE_OPTIONS.map((roleName) => (
                  <option key={roleName} value={roleName}>
                    {roleName
                      .split("_")
                      .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
                      .join(" ")}
                  </option>
                ))}
              </select>
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={stageForm.is_required}
                onChange={(event) =>
                  setStageForm((previous) => ({
                    ...previous,
                    is_required: event.target.checked,
                  }))
                }
              />
              Required stage
            </label>
            <button
              type="submit"
              disabled={stageCreating || !stageForm.template}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {stageCreating ? "Adding..." : "Add Stage"}
            </button>
          </form>
        </div>
      </section>

      {/* Existing templates */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-lg font-semibold inline-flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-indigo-600" />
          Existing Route Templates
          {templatesLoading && (
            <span className="ml-2 text-sm font-normal text-slate-500">
              Loading...
            </span>
          )}
        </h2>

        {!templatesLoading && stageTemplates.length === 0 && (
          <p className="py-6 text-center text-slate-500">
            No route templates yet. Create your first one above.
          </p>
        )}

        {stageTemplates.length > 0 && (
          <div className="space-y-4">
            {stageTemplates.map((template) => {
              const templateStages = (stagesByTemplate[template.id] ?? [])
                .slice()
                .sort((a, b) => a.order - b.order);
              return (
                <div
                  key={template.id}
                  className="rounded-lg border border-slate-200 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-slate-900">
                        {template.name}
                      </h3>
                      <p className="text-xs text-slate-500 capitalize">
                        {template.exercise_type?.split("_").join(" ")} &middot;{" "}
                        {templateStages.length} stage
                        {templateStages.length === 1 ? "" : "s"}
                      </p>
                    </div>
                  </div>
                  {templateStages.length > 0 ? (
                    <ol className="mt-3 space-y-1">
                      {templateStages.map((stage) => (
                        <li
                          key={stage.id}
                          className="flex flex-wrap items-center gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm"
                        >
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                            {stage.order}
                          </span>
                          <span className="font-medium text-slate-900">
                            {stage.name}
                          </span>
                          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-700">
                            {stage.required_role?.split("_").join(" ")}
                          </span>
                          <span className="rounded-full bg-cyan-100 px-2 py-0.5 text-xs text-cyan-800">
                            →{" "}
                            {statusLabel(
                              stage.maps_to_status as AppointmentStatus,
                            )}
                          </span>
                          {!stage.is_required && (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                              optional
                            </span>
                          )}
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-2 text-xs text-slate-400 italic">
                      No stages yet.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
};

export default RouteTemplatesPage;
