"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ShieldCheck, Eye, EyeOff, UserPlus, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const registerSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Must contain at least one uppercase letter")
    .regex(/[0-9]/, "Must contain at least one number"),
  confirmPassword: z.string(),
  role: z.enum(["customer", "compliance_officer", "admin"]),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const { register: authRegister } = useAuth();
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: "customer" },
  });

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await authRegister(data.email, data.password, data.role);
      toast.success("Account created! Please sign in.");
      router.push("/auth/login");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    }
  };

  return (
    <div className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-950 px-4 py-12 text-zinc-100 overflow-hidden">
      {/* Background Ambient Glows */}
      <div className="pointer-events-none absolute -top-40 -right-40 h-96 w-96 rounded-full bg-teal-500/15 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-emerald-500/15 blur-[120px]" />

      <div className="relative w-full max-w-md animate-fade-in">
        <div className="glass-card rounded-2xl border border-zinc-800/80 p-8 shadow-2xl backdrop-blur-xl">
          {/* Logo & Header */}
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 via-emerald-500 to-cyan-600 text-white shadow-xl shadow-teal-500/20 animate-float">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <span className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-teal-300">
              <Sparkles className="h-3 w-3" />
              Instant Registration
            </span>
            <h1 className="text-2xl font-extrabold tracking-tight text-white">Create Compliance Profile</h1>
            <p className="mt-1 text-sm text-zinc-400">Register to begin your KYC onboarding</p>
          </div>

          <form method="POST" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Email Address <span className="text-teal-400">*</span>
              </label>
              <input
                type="email"
                {...register("email")}
                autoComplete="email"
                placeholder="name@company.com"
                className={cn(
                  "glass-input w-full rounded-xl px-4 py-3 text-sm placeholder-zinc-500 outline-none transition-all",
                  errors.email && "border-red-500/50 bg-red-500/10 focus:border-red-500"
                )}
              />
              {errors.email && <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Password <span className="text-teal-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  {...register("password")}
                  placeholder="Min 8 chars, 1 uppercase, 1 number"
                  className={cn(
                    "glass-input w-full rounded-xl px-4 py-3 pr-10 text-sm placeholder-zinc-500 outline-none transition-all",
                    errors.password && "border-red-500/50 bg-red-500/10 focus:border-red-500"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>}
            </div>

            {/* Confirm Password */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Confirm Password <span className="text-teal-400">*</span>
              </label>
              <input
                type={showPassword ? "text" : "password"}
                {...register("confirmPassword")}
                placeholder="Re-enter your password"
                className={cn(
                  "glass-input w-full rounded-xl px-4 py-3 text-sm placeholder-zinc-500 outline-none transition-all",
                  errors.confirmPassword && "border-red-500/50 bg-red-500/10 focus:border-red-500"
                )}
              />
              {errors.confirmPassword && <p className="text-xs text-red-400 mt-1">{errors.confirmPassword.message}</p>}
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Account Role
              </label>
              <select
                {...register("role")}
                className="glass-input w-full rounded-xl px-4 py-3 text-sm outline-none transition-all bg-zinc-900 text-zinc-100"
              >
                <option value="customer">Customer — KYC Applicant</option>
                <option value="compliance_officer">Compliance Officer — Review access</option>
                <option value="admin">Administrator — Full access</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 to-emerald-500 py-3.5 text-sm font-bold text-white shadow-lg shadow-teal-500/20 hover:from-teal-400 hover:to-emerald-400 disabled:opacity-60 transition-all transform active:scale-[0.98] mt-2"
            >
              {isSubmitting ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
              ) : (
                <><UserPlus className="h-4 w-4" /> Create Account</>
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-zinc-800/80 pt-5 text-center">
            <p className="text-sm text-zinc-400">
              Already have an account?{" "}
              <Link href="/auth/login" className="font-semibold text-teal-400 hover:text-teal-300 underline underline-offset-4">
                Sign in here
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
