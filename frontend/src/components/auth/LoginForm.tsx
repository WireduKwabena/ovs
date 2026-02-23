import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { yupResolver } from "@hookform/resolvers/yup";
import { loginSchema } from "@/utils/validators";
import type { LoginCredentials } from "@/types";
import { useDispatch } from "react-redux";
import type { AppDispatch } from "@/app/store";
import { clearError, login as loginThunk } from "@/store/authSlice";
import { Loader } from "@/components/common/Loader";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, LogIn, Shield } from "lucide-react";

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

export const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginCredentials>({
    resolver: yupResolver(loginSchema),
  });

  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  useEffect(() => {
    return () => {
      dispatch(clearError());
    };
  }, [dispatch]);

  const onSubmit = async (data: LoginCredentials) => {
    if (loading) {
      return;
    }

    setLoading(true);
    try {
      await dispatch(
        loginThunk({
          email: data.email.trim(),
          password: data.password,
        }),
      ).unwrap();
      toast.success("Login successful!");
      dispatch(clearError());
      navigate("/", { replace: true });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Login failed. Please try again."), {
        toastId: "login-form-error",
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
                Sign in with your firm account to continue.
              </p>
            </div>
            <div className="mt-auto text-sm text-gray-300">
              © {new Date().getFullYear()} OVS Inc. All Rights Reserved.
            </div>
          </div>
        </div>

        <div className="p-8 md:p-12 bg-gray-800">
          <div className="flex justify-center mb-6">
            <Shield className="w-8 h-8 text-indigo-600" />
          </div>
          <h1 className="text-4xl font-bold text-center tracking-tighter">Sign In</h1>
          <p className="text-center text-gray-400 mt-2 mb-8">
            Enter your credentials to access your account.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-300 font-medium">
                Email
              </Label>
              <Input
                {...register("email")}
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                disabled={loading}
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? "login-email-error" : undefined}
                className={`w-full bg-gray-700 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 ${errors.email ? "border-red-500" : ""}`}
              />
              {errors.email && (
                <p id="login-email-error" className="text-sm text-red-400 mt-1">{errors.email.message}</p>
              )}
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
                  autoComplete="current-password"
                  placeholder="••••••••"
                  disabled={loading}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? "login-password-error" : undefined}
                  className={`w-full bg-gray-700 border-gray-600 text-white placeholder:text-gray-400 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-shadow duration-300 pr-10 ${errors.password ? "border-red-500" : ""}`}
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
                <p id="login-password-error" className="text-sm text-red-400 mt-1">{errors.password.message}</p>
              )}
              <div className="text-right mt-2">
                <Link
                  to="/forgot-password"
                  className="text-sm font-medium text-blue-400 hover:underline"
                >
                  Forgot password?
                </Link>
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
                  Signing in...
                </span>
              ) : (
                <div className="flex items-center justify-center">
                  <LogIn className="mr-2 h-5 w-5" />
                  <span>Sign In</span>
                </div>
              )}
            </Button>
          </form>

          <div className="text-center text-sm text-gray-400 mt-8">
            Don&apos;t have an account?{" "}
            <Link to="/register" className="font-medium text-blue-400 hover:underline">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
