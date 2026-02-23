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
import { UserPlus, Eye, EyeOff, Building2 } from "lucide-react";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) {
    return fallback;
  }

  if (typeof error === "string") {
    return error;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  const normalizedError = error as {
    message?: string;
    response?: {
      data?: {
        message?: string;
        detail?: string;
      };
    };
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
    defaultValues: {
      organization: "",
      department: "",
    },
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
    if (loading) {
      return;
    }

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

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-4xl mx-auto lg:grid lg:grid-cols-2 rounded-3xl shadow-2xl overflow-hidden bg-gray-800 border border-gray-700">
        <div className="relative hidden lg:block overflow-hidden">
          <div className="absolute inset-0 bg-linear-to-br from-purple-600 to-blue-500"></div>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-lg border-r border-white/20"></div>
          <div className="relative z-10 flex flex-col justify-between h-full p-12">
            <div>
              <h2 className="text-4xl font-bold tracking-tighter text-white">
                Online Vetting System
              </h2>
              <p className="mt-4 text-lg text-gray-200">
                Create a firm account to run and manage vetting campaigns.
              </p>
            </div>
            <div className="mt-auto text-sm text-gray-300">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        <div className="p-8 md:p-12 bg-gray-800">
          <div className="flex justify-center mb-6">
            <UserPlus className="h-16 w-16 text-blue-400" />
          </div>
          <h1 className="text-4xl font-bold text-center tracking-tighter">
            Create Firm Account
          </h1>
          <p className="text-center text-gray-400 mt-2 mb-8">
            Register with your work details.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
              <div className="space-y-2">
                <Label htmlFor="first_name" className="text-gray-300 font-medium">
                  First Name
                </Label>
                <Input
                  {...register("first_name")}
                  id="first_name"
                  placeholder="John"
                  autoComplete="given-name"
                  disabled={loading}
                  aria-invalid={Boolean(errors.first_name)}
                  aria-describedby={errors.first_name ? "register-first-name-error" : undefined}
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${errors.first_name ? "border-red-500" : ""}`}
                />
                {errors.first_name && (
                  <p id="register-first-name-error" className="text-sm text-red-400 mt-1">{errors.first_name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="last_name" className="text-gray-300 font-medium">
                  Last Name
                </Label>
                <Input
                  {...register("last_name")}
                  id="last_name"
                  placeholder="Doe"
                  autoComplete="family-name"
                  disabled={loading}
                  aria-invalid={Boolean(errors.last_name)}
                  aria-describedby={errors.last_name ? "register-last-name-error" : undefined}
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${errors.last_name ? "border-red-500" : ""}`}
                />
                {errors.last_name && (
                  <p id="register-last-name-error" className="text-sm text-red-400 mt-1">{errors.last_name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-gray-300 font-medium">
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
                  aria-describedby={errors.email ? "register-email-error" : undefined}
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${errors.email ? "border-red-500" : ""}`}
                />
                {errors.email && (
                  <p id="register-email-error" className="text-sm text-red-400 mt-1">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone_number" className="text-gray-300 font-medium">
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
                  aria-describedby={errors.phone_number ? "register-phone-number-error" : undefined}
                  className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${errors.phone_number ? "border-red-500" : ""}`}
                />
                {errors.phone_number && (
                  <p id="register-phone-number-error" className="text-sm text-red-400 mt-1">{errors.phone_number.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="organization" className="text-gray-300 font-medium">
                  Organization
                </Label>
                <div className="relative">
                  <Input
                    {...register("organization")}
                    id="organization"
                    placeholder="Acme Corp"
                    autoComplete="organization"
                    disabled={loading}
                    className="w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 pl-10 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300"
                  />
                  <Building2 className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="department" className="text-gray-300 font-medium">
                  Department
                </Label>
                <Input
                  {...register("department")}
                  id="department"
                  placeholder="Human Resources"
                  disabled={loading}
                  className="w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-gray-300 font-medium">
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
                    aria-describedby={errors.password ? "register-password-error" : undefined}
                    className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.password ? "border-red-500" : ""}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p id="register-password-error" className="text-sm text-red-400 mt-1">{errors.password.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password_confirm" className="text-gray-300 font-medium">
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
                    aria-describedby={errors.password_confirm ? "register-password-confirm-error" : undefined}
                    className={`w-full bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.password_confirm ? "border-red-500" : ""}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    disabled={loading}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password_confirm && (
                  <p id="register-password-confirm-error" className="text-sm text-red-400 mt-1">
                    {errors.password_confirm.message}
                  </p>
                )}
              </div>
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg rounded-lg py-3 transition-transform duration-200 active:scale-95"
              disabled={loading}
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader size="sm" color="white" />
                  Registering...
                </span>
              ) : (
                <div className="flex items-center justify-center">
                  <UserPlus className="mr-2 h-5 w-5" />
                  <span>Register</span>
                </div>
              )}
            </Button>
          </form>

          <div className="text-center text-sm text-gray-400 mt-8">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-blue-400 hover:underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
