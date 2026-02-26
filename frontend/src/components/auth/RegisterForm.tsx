import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useForm, type SubmitHandler } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import { registerSchema } from "@/utils/validators";
import { clearError, register as registerThunk } from "@/store/authSlice";
import type { RegisterData } from "@/types";
import { useDispatch } from "react-redux";
import type { AppDispatch } from "@/app/store";
import { Loader } from "@/components/common/Loader";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { UserPlus, Eye, EyeOff, Building2, Shield } from "lucide-react";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;
  const normalizedError = error as {
    message?: string;
    response?: { data?: { message?: string; detail?: string } };
  };
  return (
    normalizedError.response?.data?.message ||
    normalizedError.response?.data?.detail ||
    normalizedError.message ||
    fallback
  );
};

export const RegisterForm: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterData>({
    resolver: yupResolver(registerSchema),
    defaultValues: { organization: "", department: "" },
  });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);
  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit: SubmitHandler<RegisterData> = async (data: RegisterData) => {
    if (loading) return;
    setLoading(true);
    try {
      await dispatch(
        registerThunk({
          ...data,
          first_name: data.first_name.trim(),
          last_name: data.last_name.trim(),
          email: data.email.trim(),
          phone_number: data.phone_number.trim(),
          organization: data.organization.trim(),
          department: data.department.trim(),
          password: data.password,
          password_confirm: data.password_confirm,
        }),
      ).unwrap();
      toast.success("Registration successful! Please log in.");
      dispatch(clearError());
      navigate("/login", { replace: true });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Registration failed"), {
        toastId: "register-form-error",
      });
    } finally {
      setLoading(false);
    }
  };

  const inputClass = (hasError: boolean) =>
    `w-full bg-gray-50 border text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200 ${
      hasError ? "border-red-400 bg-red-50" : "border-gray-200"
    }`;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center p-4 relative overflow-hidden">
      {/* Decorative background blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse delay-1000 pointer-events-none" />

      <div className="relative w-full max-w-4xl mx-auto lg:grid lg:grid-cols-2 rounded-3xl shadow-2xl overflow-hidden bg-white border border-gray-100 my-8">
        {/* Left decorative panel */}
        <div className="relative hidden lg:flex flex-col bg-indigo-600 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-purple-600" />
          <div className="absolute top-0 left-0 w-64 h-64 bg-white/10 rounded-full -translate-x-1/2 -translate-y-1/2" />
          <div className="absolute bottom-0 right-0 w-80 h-80 bg-white/10 rounded-full translate-x-1/2 translate-y-1/2" />
          <div className="relative z-10 flex flex-col justify-between h-full p-12">
            <div className="flex items-center gap-3">
              <div className="bg-white/20 rounded-lg p-2">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold text-white">
                VettingSystem
              </span>
            </div>
            <div>
              <h2 className="text-4xl font-extrabold tracking-tight text-white leading-tight">
                Create your firm account
              </h2>
              <p className="mt-4 text-lg text-indigo-100">
                Register to run and manage vetting campaigns with AI-powered
                verification.
              </p>
            </div>
            <div className="text-sm text-indigo-200">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        {/* Right form panel */}
        <div className="p-8 md:p-12 bg-white">
          <div className="flex justify-center mb-6">
            <div className="bg-indigo-50 rounded-2xl p-4">
              <UserPlus className="w-8 h-8 text-indigo-600" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-center text-gray-900 tracking-tight">
            Create Firm Account
          </h1>
          <p className="text-center text-gray-500 mt-2 mb-8">
            Register with your work details.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
              {/* First Name */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="first_name"
                  className="text-gray-700 font-medium text-sm"
                >
                  First Name
                </Label>
                <Input
                  {...register("first_name")}
                  id="first_name"
                  placeholder="John"
                  autoComplete="given-name"
                  disabled={loading}
                  aria-invalid={Boolean(errors.first_name)}
                  className={inputClass(Boolean(errors.first_name))}
                />
                {errors.first_name && (
                  <p className="text-sm text-red-500">
                    {errors.first_name.message}
                  </p>
                )}
              </div>

              {/* Last Name */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="last_name"
                  className="text-gray-700 font-medium text-sm"
                >
                  Last Name
                </Label>
                <Input
                  {...register("last_name")}
                  id="last_name"
                  placeholder="Doe"
                  autoComplete="family-name"
                  disabled={loading}
                  aria-invalid={Boolean(errors.last_name)}
                  className={inputClass(Boolean(errors.last_name))}
                />
                {errors.last_name && (
                  <p className="text-sm text-red-500">
                    {errors.last_name.message}
                  </p>
                )}
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="email"
                  className="text-gray-700 font-medium text-sm"
                >
                  Email
                </Label>
                <Input
                  {...register("email")}
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  disabled={loading}
                  aria-invalid={Boolean(errors.email)}
                  className={inputClass(Boolean(errors.email))}
                />
                {errors.email && (
                  <p className="text-sm text-red-500">{errors.email.message}</p>
                )}
              </div>

              {/* Phone Number */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="phone_number"
                  className="text-gray-700 font-medium text-sm"
                >
                  Phone Number
                </Label>
                <Input
                  {...register("phone_number")}
                  id="phone_number"
                  type="tel"
                  autoComplete="tel"
                  placeholder="+1 (555) 123-4567"
                  disabled={loading}
                  aria-invalid={Boolean(errors.phone_number)}
                  className={inputClass(Boolean(errors.phone_number))}
                />
                {errors.phone_number && (
                  <p className="text-sm text-red-500">
                    {errors.phone_number.message}
                  </p>
                )}
              </div>

              {/* Organization */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="organization"
                  className="text-gray-700 font-medium text-sm"
                >
                  Organization
                </Label>
                <div className="relative">
                  <Input
                    {...register("organization")}
                    id="organization"
                    placeholder="Acme Corp"
                    autoComplete="organization"
                    disabled={loading}
                    className="w-full bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 pl-10 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200"
                  />
                  <Building2 className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                </div>
              </div>

              {/* Department */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="department"
                  className="text-gray-700 font-medium text-sm"
                >
                  Department
                </Label>
                <Input
                  {...register("department")}
                  id="department"
                  placeholder="Human Resources"
                  disabled={loading}
                  className="w-full bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200"
                />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="password"
                  className="text-gray-700 font-medium text-sm"
                >
                  Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("password")}
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="••••••••"
                    disabled={loading}
                    aria-invalid={Boolean(errors.password)}
                    className={inputClass(Boolean(errors.password)) + " pr-10"}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-sm text-red-500">
                    {errors.password.message}
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="password_confirm"
                  className="text-gray-700 font-medium text-sm"
                >
                  Confirm Password
                </Label>
                <div className="relative">
                  <Input
                    {...register("password_confirm")}
                    id="password_confirm"
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="••••••••"
                    disabled={loading}
                    aria-invalid={Boolean(errors.password_confirm)}
                    className={
                      inputClass(Boolean(errors.password_confirm)) + " pr-10"
                    }
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
                    aria-label={
                      showConfirmPassword ? "Hide password" : "Show password"
                    }
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password_confirm && (
                  <p className="text-sm text-red-500">
                    {errors.password_confirm.message}
                  </p>
                )}
              </div>
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-base rounded-xl py-3 transition-all duration-200 hover:scale-[1.02] active:scale-95 shadow-md hover:shadow-indigo-200"
              disabled={loading}
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader size="sm" color="white" />
                  Registering...
                </span>
              ) : (
                <div className="flex items-center justify-center gap-2">
                  <UserPlus className="h-5 w-5" />
                  <span>Create Account</span>
                </div>
              )}
            </Button>
          </form>

          <div className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-semibold text-indigo-600 hover:underline"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
