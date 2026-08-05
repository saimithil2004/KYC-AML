"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ShieldCheck, Eye, EyeOff, LogIn, Briefcase, Settings, UserCheck, Lock } from "lucide-react";
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
      badgeClass: "bg-teal-100 text-teal-800 border-teal-200",
      bgGradient: "bg-gradient-to-r from-teal-700 to-teal-800",
      buttonBg: "bg-teal-700 hover:bg-teal-800 focus:ring-teal-200",
      icon: UserCheck,
    },
    compliance: {
      title: "Compliance Officer Portal",
      subtitle: "Sign in to AML risk screening & investigation desk",
      badge: "Officer & Analyst Access",
      badgeClass: "bg-indigo-100 text-indigo-800 border-indigo-200",
      bgGradient: "bg-gradient-to-r from-indigo-800 to-slate-900",
      buttonBg: "bg-indigo-700 hover:bg-indigo-800 focus:ring-indigo-200",
      icon: Briefcase,
    },
    admin: {
      title: "Administrator Portal Access",
      subtitle: "Sign in to system admin, policy engine & AI governance",
      badge: "Admin Privileges Required",
      badgeClass: "bg-purple-100 text-purple-800 border-purple-200",
      bgGradient: "bg-gradient-to-r from-purple-800 to-zinc-900",
      buttonBg: "bg-purple-700 hover:bg-purple-800 focus:ring-purple-200",
      icon: Settings,
    },
  };

  const currentConfig = portalConfig[activeTab];
  const IconComponent = currentConfig.icon;

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-50 px-4 py-12">
      <div className="w-full max-w-lg">

        {/* Portal Selection Tabs */}
        <div className="mb-4 grid grid-cols-3 gap-1 rounded-xl bg-zinc-200/80 p-1.5 shadow-inner">
          <button
            type="button"
            onClick={() => setActiveTab("client")}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition-all",
              activeTab === "client"
                ? "bg-white text-teal-800 shadow-sm"
                : "text-zinc-600 hover:text-zinc-900"
            )}
          >
            <UserCheck className="h-3.5 w-3.5" />
            Client
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("compliance")}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition-all",
              activeTab === "compliance"
                ? "bg-white text-indigo-800 shadow-sm"
                : "text-zinc-600 hover:text-zinc-900"
            )}
          >
            <Briefcase className="h-3.5 w-3.5" />
            Officer
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("admin")}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition-all",
              activeTab === "admin"
                ? "bg-white text-purple-800 shadow-sm"
                : "text-zinc-600 hover:text-zinc-900"
            )}
          >
            <Settings className="h-3.5 w-3.5" />
            Admin
          </button>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-xl">
          {/* Logo & Portal Header */}
          <div className="mb-6 flex flex-col items-center text-center">
            <div className={cn("mb-3 flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-md transition-all duration-300", currentConfig.bgGradient)}>
              <IconComponent className="h-7 w-7" />
            </div>

            <span className={cn("mb-2 rounded-full border px-3 py-0.5 text-[11px] font-bold uppercase tracking-wider", currentConfig.badgeClass)}>
              {currentConfig.badge}
            </span>

            <h1 className="text-2xl font-extrabold text-zinc-900">{currentConfig.title}</h1>
            <p className="mt-1 text-sm text-zinc-500">{currentConfig.subtitle}</p>
          </div>

          {/* Form */}
          <form method="POST" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Email Address <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                {...register("email")}
                autoComplete="email"
                placeholder={activeTab === "client" ? "customer@example.com" : "officer@company.com"}
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

            {activeTab !== "client" && (
              <div className="rounded-lg bg-zinc-50 p-3 border border-zinc-200 flex items-start gap-2 text-xs text-zinc-600">
                <Lock className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />
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
                "flex w-full items-center justify-center gap-2 rounded-lg py-3 text-sm font-bold text-white shadow focus:outline-none focus:ring-2 transition-all mt-2",
                currentConfig.buttonBg,
                isSubmitting && "opacity-60 cursor-not-allowed"
              )}
            >
              {isSubmitting ? (
                <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
              ) : (
                <><LogIn className="h-4 w-4" /> Sign In to {activeTab === "client" ? "Client Portal" : activeTab === "compliance" ? "Officer Panel" : "Admin Panel"}</>
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-zinc-100 pt-5 text-center">
            {activeTab === "client" ? (
              <p className="text-sm text-zinc-500">
                No account?{" "}
                <Link href="/auth/register" className="font-semibold text-teal-700 hover:text-teal-800 hover:underline">
                  Register customer account
                </Link>
              </p>
            ) : (
              <p className="text-xs text-zinc-500">
                Need an officer or admin account?{" "}
                <Link href="/auth/register" className="font-semibold text-teal-700 hover:text-teal-800 hover:underline">
                  Create role profile
                </Link>
              </p>
            )}
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-zinc-400">
          Protected by 256-bit AES encryption & MFA support. Compliant with UK MLR 2017 & GDPR.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-zinc-50">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-teal-700" />
      </div>
    }>
      <LoginFormContent />
    </Suspense>
  );
}
