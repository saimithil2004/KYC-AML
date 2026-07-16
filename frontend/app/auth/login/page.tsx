"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ShieldCheck, Eye, EyeOff, LogIn } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data.email, data.password);
      toast.success("Welcome back!");
      router.push("/customer/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invalid credentials");
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-50 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg">
          {/* Logo */}
          <div className="mb-6 flex flex-col items-center gap-2">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-700 shadow">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-zinc-900">Client Portal Access</h1>
            <p className="text-sm text-zinc-500">Sign in to continue your KYC application</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Email Address <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                {...register("email")}
                autoComplete="email"
                placeholder="name@company.com"
                className={cn(
                  "w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none transition-all",
                  errors.email
                    ? "border-red-300 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100"
                    : "border-zinc-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                )}
              />
              {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Password <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  {...register("password")}
                  autoComplete="current-password"
                  placeholder="Minimum 8 characters"
                  className={cn(
                    "w-full rounded-lg border px-3.5 py-2.5 pr-10 text-sm outline-none transition-all",
                    errors.password
                      ? "border-red-300 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100"
                      : "border-zinc-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-700 py-3 text-sm font-bold text-white shadow hover:bg-teal-800 disabled:opacity-60 transition-colors mt-2"
            >
              {isSubmitting ? (
                <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
              ) : (
                <><LogIn className="h-4 w-4" /> Sign In</>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-zinc-500">
            No account?{" "}
            <Link href="/auth/register" className="font-semibold text-teal-700 hover:text-teal-800 hover:underline">
              Register here
            </Link>
          </p>
        </div>

        <p className="mt-4 text-center text-xs text-zinc-400">
          Protected by 256-bit encryption. All data processed under UK GDPR.
        </p>
      </div>
    </div>
  );
}
