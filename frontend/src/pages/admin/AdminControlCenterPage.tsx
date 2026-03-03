import React from "react";
import { Link } from "react-router-dom";
import { ExternalLink, ShieldCheck } from "lucide-react";

const ADMIN_SECTIONS = [
  { label: "Users", path: "authentication/user/" },
  { label: "Vetting Cases", path: "applications/vettingcase/" },
  { label: "Documents", path: "applications/document/" },
  { label: "Interviews", path: "interviews/interviewsession/" },
  { label: "Rubrics", path: "rubrics/rubric/" },
  { label: "Campaigns", path: "campaigns/vettingcampaign/" },
  { label: "Notifications", path: "notifications/notification/" },
  { label: "Background Checks", path: "background_checks/backgroundcheck/" },
  { label: "Billing Subscriptions", path: "billing/subscription/" },
  { label: "Video Meetings", path: "video_calls/videomeeting/" },
];

const adminBaseUrl = (
  (import.meta as { env?: Record<string, string> }).env?.VITE_DJANGO_ADMIN_URL ||
  "http://localhost:8000/admin/"
).replace(/\/?$/, "/");

const AdminControlCenterPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Admin Control Center</h1>
              <p className="mt-1 text-sm text-slate-700">
                Full backend administration is available through Django Admin modules below.
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto [&>*]:w-full sm:[&>*]:w-auto">
              <Link
                to="/admin/users"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
              >
                Manage Users In-App
              </Link>
              <a
                href={adminBaseUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                <ShieldCheck className="h-4 w-4" />
                Open Django Admin
              </a>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {ADMIN_SECTIONS.map((section) => (
            <article key={section.path} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">{section.label}</h2>
              <p className="mt-1 text-xs text-slate-700">Direct model administration panel.</p>
              <a
                href={`${adminBaseUrl}${section.path}`}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 sm:w-auto"
              >
                Open
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
};

export default AdminControlCenterPage;
