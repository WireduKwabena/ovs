import React from "react";
import { Link } from "react-router-dom";
import { Building2, ShieldCheck, Users2 } from "lucide-react";

const PLATFORM_SECTIONS = [
  {
    label: "Organizations",
    description: "Create and manage organization-level onboarding and setup context.",
    to: "/admin/organizations",
    icon: Building2,
  },
  {
    label: "Organization Admins",
    description: "Manage organization administrator accounts and security posture.",
    to: "/admin/users",
    icon: Users2,
  },
  {
    label: "Platform Analytics",
    description: "Review platform-wide trends and operational telemetry.",
    to: "/admin/analytics",
    icon: ShieldCheck,
  },
];

const AdminControlCenterPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Platform Control Center</h1>
              <p className="mt-1 text-sm text-slate-800">
                Platform admins manage organizations and organization-admin access from in-app tools.
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto [&>*]:w-full sm:[&>*]:w-auto">
              <Link
                to="/admin/users"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
              >
                Open Organization Admin Management
              </Link>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {PLATFORM_SECTIONS.map((section) => (
            <article key={section.to} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <section.icon className="h-5 w-5 text-indigo-700" />
              <h2 className="text-base font-semibold text-slate-900">{section.label}</h2>
              <p className="mt-1 text-xs text-slate-800">{section.description}</p>
              <Link
                to={section.to}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 sm:w-auto"
              >
                Open
              </Link>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
};

export default AdminControlCenterPage;
