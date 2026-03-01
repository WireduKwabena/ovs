import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, UserPlus } from "lucide-react";

const AdminRegisterForm: React.FC = () => {
  return (
    <main className="flex min-h-[70vh] items-center justify-center px-4 py-10">
      <section className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <ShieldCheck className="h-3.5 w-3.5" />
          Admin provisioning
        </div>

        <h1 className="text-2xl font-black text-slate-900">Admin account creation is controlled</h1>
        <p className="mt-3 text-sm text-slate-600">
          Self-service admin signup is disabled. Create admin users through secure internal provisioning
          (Django admin or approved management commands).
        </p>

        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <p className="font-semibold text-slate-900">Recommended flow</p>
          <p className="mt-2">
            Provision account in backend, enforce password reset, then assign least-privilege roles.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            to="/admin/dashboard"
            className="inline-flex items-center gap-2 rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
          >
            <UserPlus className="h-4 w-4" />
            Back to Admin Dashboard
          </Link>
          <Link
            to="/dashboard"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Return to Workspace
          </Link>
        </div>
      </section>
    </main>
  );
};

export default AdminRegisterForm;
