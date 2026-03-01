import React, { useEffect, useState } from "react";
import { Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import * as yup from "yup";
import { toast } from "react-toastify";

import { type AppDispatch, type RootState } from "@/app/store";
import { changePassword, clearError } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/common/Loader";

const schema = yup.object({
  old_password: yup.string().required("Current password is required"),
  new_password: yup
    .string()
    .min(8, "New password must be at least 8 characters")
    .required("New password is required"),
  new_password_confirm: yup
    .string()
    .oneOf([yup.ref("new_password")], "Passwords must match")
    .required("Password confirmation is required"),
});

type ChangePasswordFormData = yup.InferType<typeof schema>;
type PasswordToggleProps = {
  visible: boolean;
  onToggle: () => void;
  disabled: boolean;
};

const PasswordToggle: React.FC<PasswordToggleProps> = ({ visible, onToggle, disabled }) => (
  <button
    type="button"
    onClick={onToggle}
    disabled={disabled}
    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700 disabled:cursor-not-allowed"
    aria-label={visible ? "Hide password" : "Show password"}
  >
    {visible ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
  </button>
);

export const ChangePasswordForm: React.FC = () => {
  const dispatch: AppDispatch = useDispatch();
  const { loading, error } = useSelector((state: RootState) => state.auth);

  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ChangePasswordFormData>({
    resolver: yupResolver(schema),
  });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  useEffect(() => {
    if (error) {
      toast.error(error, { toastId: `change-password-${error}` });
    }
  }, [error]);

  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<ChangePasswordFormData> = async (data) => {
    if (loading) return;

    try {
      await dispatch(changePassword(data)).unwrap();
      toast.success("Password updated successfully.");
      dispatch(clearError());
      reset();
    } catch {
      // Toast handled by auth error observer.
    }
  };

  const inputClass = (hasError: boolean) =>
    `h-12 rounded-xl border px-4 pr-11 text-sm transition focus-visible:ring-cyan-500 ${
      hasError
        ? "border-red-400 bg-red-50"
        : "border-slate-300 bg-slate-50 focus-visible:border-cyan-600"
    }`;


  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-100 px-4 py-8">
      <div className="pointer-events-none absolute -left-20 top-4 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />

      <div className="relative w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.7)] lg:grid lg:grid-cols-5">
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800 p-8 text-slate-100 lg:col-span-2 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.32),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(251,191,36,0.2),transparent_35%)]" />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
              <ShieldCheck className="h-4 w-4" />
              Security Controls
            </div>

            <div>
              <h1 className="text-3xl font-black leading-tight">Rotate Your Password</h1>
              <p className="mt-4 text-sm text-slate-200/90">
                Update your password regularly to keep your organization workspace secure.
              </p>
            </div>

            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 text-xs text-slate-200">
              Use a unique password that is not reused on any other service.
            </div>
          </div>
        </aside>

        <section className="p-6 sm:p-8 lg:col-span-3 lg:p-10">
          <div className="mx-auto w-full max-w-md">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Password actions</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-900">Change password</h2>
            <p className="mt-2 text-sm text-slate-600">Enter your current password and choose a new one.</p>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="old_password" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Current Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("old_password")}
                    id="old_password"
                    type={showOldPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Enter current password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.old_password)}
                    className={inputClass(Boolean(errors.old_password))}
                  />
                  <PasswordToggle
                    visible={showOldPassword}
                    onToggle={() => setShowOldPassword((prev) => !prev)}
                    disabled={loading}
                  />
                </div>
                {errors.old_password && <p className="text-xs font-medium text-red-600">{errors.old_password.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="new_password" className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  New Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("new_password")}
                    id="new_password"
                    type={showNewPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Create new password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.new_password)}
                    className={inputClass(Boolean(errors.new_password))}
                  />
                  <PasswordToggle
                    visible={showNewPassword}
                    onToggle={() => setShowNewPassword((prev) => !prev)}
                    disabled={loading}
                  />
                </div>
                {errors.new_password && <p className="text-xs font-medium text-red-600">{errors.new_password.message}</p>}
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="new_password_confirm"
                  className="text-xs font-semibold uppercase tracking-wide text-slate-700"
                >
                  Confirm Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("new_password_confirm")}
                    id="new_password_confirm"
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Re-enter new password"
                    disabled={loading}
                    aria-invalid={Boolean(errors.new_password_confirm)}
                    className={inputClass(Boolean(errors.new_password_confirm))}
                  />
                  <PasswordToggle
                    visible={showConfirmPassword}
                    onToggle={() => setShowConfirmPassword((prev) => !prev)}
                    disabled={loading}
                  />
                </div>
                {errors.new_password_confirm && (
                  <p className="text-xs font-medium text-red-600">{errors.new_password_confirm.message}</p>
                )}
              </div>

              <Button
                type="submit"
                size="lg"
                className="h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white shadow-md transition hover:bg-cyan-800"
                disabled={loading}
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader size="sm" color="white" />
                    Updating password...
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <LockKeyhole className="h-4 w-4" />
                    Update password
                  </span>
                )}
              </Button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};
