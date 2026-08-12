"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ShieldCheck, Eye, EyeOff, LogIn, Briefcase, Settings, UserCheck, Lock, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type LoginFormData = z.infer<typeof loginSchema>;

type PortalTab = "client" | "compliance" | "admin";

function LoginFormContent() {
  const { login, logout } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [activeTab, setActiveTab] = useState<PortalTab>("client");
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const portal = searchParams?.get("portal");
    if (portal === "compliance") {
      setActiveTab("compliance");
    } else if (portal === "admin") {
      setActiveTab("admin");
    } else if (portal === "client") {
      setActiveTab("client");
    }
  }, [searchParams]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginFormData) => {
    try {
      const loggedUser = await login(data.email, data.password);

      // Validate user role against selected portal tab
      if (activeTab === "compliance" && loggedUser.role === "customer") {
        logout();
        toast.error("Access Denied: Your account does not have Compliance Officer privileges.");
        return;
      }

      if (activeTab === "admin" && loggedUser.role !== "admin") {
        logout();
        toast.error("Access Denied: Your account does not have Administrator privileges.");
        return;
      }

      // Successful login & authorization
      if (loggedUser.role === "compliance_officer" || loggedUser.role === "admin") {
        toast.success(`Welcome back, ${loggedUser.email}! Redirecting to Officer Workspace...`);
        router.push("/admin");
      } else {
        toast.success(`Welcome back, ${loggedUser.email}!`);
        router.push("/customer/dashboard");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invalid email or password");
    }
  };

  const portalConfig = {
    client: {
      title: "Client Portal Access",
      subtitle: "Sign in to complete your KYC application & onboarding",
      badge: "Customer Portal",
      badgeClass: "bg-teal-500/10 text-teal-300 border-teal-500/30",
      bgGradient: "bg-gradient-to-br from-teal-500 via-emerald-500 to-cyan-600 shadow-teal-500/25",
      buttonBg: "bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-400 hover:to-emerald-400 focus:ring-teal-500/50 shadow-lg shadow-teal-500/20",
      icon: UserCheck,
    },
    compliance: {
      title: "Compliance Officer Portal",
      subtitle: "Sign in to AML risk screening & investigation desk",
      badge: "Officer & Analyst Access",
      badgeClass: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30",
      bgGradient: "bg-gradient-to-br from-indigo-500 via-purple-500 to-slate-700 shadow-indigo-500/25",
      buttonBg: "bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 focus:ring-indigo-500/50 shadow-lg shadow-indigo-500/20",
      icon: Briefcase,
    },
    admin: {
      title: "Administrator Portal Access",
      subtitle: "Sign in to system admin, policy engine & AI governance",
      badge: "Admin Privileges Required",
      badgeClass: "bg-purple-500/10 text-purple-300 border-purple-500/30",
      bgGradient: "bg-gradient-to-br from-purple-600 via-fuchsia-600 to-pink-600 shadow-purple-500/25",
      buttonBg: "bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 focus:ring-purple-500/50 shadow-lg shadow-purple-500/20",
      icon: Settings,
    },
  };

  const currentConfig = portalConfig[activeTab];
  const IconComponent = currentConfig.icon;

  return (
    <div className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-950 px-4 py-12 text-zinc-100 overflow-hidden">
      {/* Background Ambient Glows */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-96 w-96 rounded-full bg-teal-500/15 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-indigo-500/15 blur-[120px]" />

      <div className="relative w-full max-w-lg animate-fade-in">
        {/* Portal Selection Tabs */}
        <div className="mb-4 grid grid-cols-3 gap-1.5 rounded-2xl bg-zinc-900/90 p-1.5 border border-zinc-800/80 backdrop-blur-md shadow-2xl">
          <button
            type="button"
            onClick={() => setActiveTab("client")}
            className={cn(
              "flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-bold transition-all duration-200",
              activeTab === "client"
                ? "bg-gradient-to-r from-teal-500/20 to-emerald-500/20 text-teal-300 border border-teal-500/40 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            )}
          >
            <UserCheck className="h-3.5 w-3.5" />
            Client
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("compliance")}
            className={cn(
              "flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-bold transition-all duration-200",
              activeTab === "compliance"
                ? "bg-gradient-to-r from-indigo-500/20 to-purple-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            )}
          >
            <Briefcase className="h-3.5 w-3.5" />
            Officer
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("admin")}
            className={cn(
              "flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-bold transition-all duration-200",
              activeTab === "admin"
                ? "bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-300 border border-purple-500/40 shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            )}
          >
            <Settings className="h-3.5 w-3.5" />
            Admin
          </button>
        </div>

        {/* Glass Card */}
        <div className="glass-card rounded-2xl border border-zinc-800/80 p-8 shadow-2xl backdrop-blur-xl">
          {/* Header */}
          <div className="mb-6 flex flex-col items-center text-center">
            <div className={cn("mb-3 flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-xl transition-all duration-300 animate-float", currentConfig.bgGradient)}>
              <IconComponent className="h-7 w-7" />
            </div>

            <span className={cn("mb-2 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-wider", currentConfig.badgeClass)}>
              <Sparkles className="h-3 w-3" />
              {currentConfig.badge}
            </span>

            <h1 className="text-2xl font-extrabold tracking-tight text-white">{currentConfig.title}</h1>
            <p className="mt-1 text-sm text-zinc-400">{currentConfig.subtitle}</p>
          </div>

          {/* Form */}
          <form method="POST" onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Email Address <span className="text-teal-400">*</span>
              </label>
              <input
                type="email"
                {...register("email")}
                autoComplete="email"
                placeholder={activeTab === "client" ? "john.clean@example.com" : "officer@compliance.com"}
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
                  autoComplete="current-password"
                  placeholder="••••••••"
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

            {activeTab !== "client" && (
              <div className="rounded-xl bg-indigo-500/10 p-3.5 border border-indigo-500/20 flex items-start gap-2.5 text-xs text-indigo-300">
                <Lock className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                <span>
                  {activeTab === "compliance"
                    ? "Compliance Officer accounts require verified officer role credentials."
                    : "Administrator accounts require full system administrator permissions."}
                </span>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                "flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-sm font-bold text-white transition-all transform active:scale-[0.98]",
                currentConfig.buttonBg,
                isSubmitting && "opacity-60 cursor-not-allowed"
              )}
            >
              {isSubmitting ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
              ) : (
                <><LogIn className="h-4 w-4" /> Sign In to {activeTab === "client" ? "Client Portal" : activeTab === "compliance" ? "Officer Panel" : "Admin Panel"}</>
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-zinc-800/80 pt-5 text-center">
            {activeTab === "client" ? (
              <p className="text-sm text-zinc-400">
                No account?{" "}
                <Link href="/auth/register" className="font-semibold text-teal-400 hover:text-teal-300 underline underline-offset-4">
                  Register customer account
                </Link>
              </p>
            ) : (
              <p className="text-xs text-zinc-400">
                Need an officer or admin account?{" "}
                <Link href="/auth/register" className="font-semibold text-teal-400 hover:text-teal-300 underline underline-offset-4">
                  Create role profile
                </Link>
              </p>
            )}
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-zinc-500 flex items-center justify-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
          Protected by 256-bit AES encryption & MFA support. Compliant with UK MLR 2017 & GDPR.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500/20 border-t-teal-500" />
      </div>
    }>
      <LoginFormContent />
    </Suspense>
  );
}
