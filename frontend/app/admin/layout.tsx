"use client";

import React from "react";
import Link from "next/link";
import {
  ShieldCheck, LogOut, LayoutDashboard, FileCheck, Users,
  ArrowUpDown, AlertTriangle, Briefcase, ScrollText, Zap, FileText, Sliders, RefreshCw,
  Webhook, Bell, Server, Brain, Cpu, FileCode, History, BarChart3
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";

const navItems = [
  { section: "General", items: [
    { href: "/admin", label: "Overview Dashboard", icon: LayoutDashboard },
  ]},
  { section: "Review", items: [
    { href: "/admin/documents", label: "Verification Desk", icon: FileCheck },
    { href: "/admin/investigations", label: "Investigations Workspace", icon: Briefcase },
  ]},
  { section: "Compliance", items: [
    { href: "/admin/transactions", label: "Transactions", icon: ArrowUpDown },
    { href: "/admin/alerts", label: "Alerts", icon: AlertTriangle },
    { href: "/admin/cases", label: "Cases", icon: Briefcase },
    { href: "/admin/monitoring", label: "Monitoring Hub", icon: RefreshCw },
  ]},
  { section: "Rules", items: [
    { href: "/admin/regulations", label: "Regulations Lib", icon: FileText },
    { href: "/admin/policy-rules", label: "Policy Rules", icon: Sliders },
  ]},
  { section: "Intelligence", items: [
    { href: "/admin/analytics", label: "Executive Analytics", icon: ScrollText },
    { href: "/admin/reports", label: "Reports & Schedules", icon: FileText },
  ]},
  { section: "AI Governance", items: [
    { href: "/admin/ai", label: "AI Analytics", icon: BarChart3 },
    { href: "/admin/ai/models", label: "AI Models", icon: Cpu },
    { href: "/admin/ai/prompts", label: "AI Prompts", icon: FileCode },
    { href: "/admin/ai/executions", label: "AI Executions", icon: History },
    { href: "/admin/ai/governance", label: "AI Governance", icon: Brain },
  ]},
  { section: "System", items: [
    { href: "/admin/audit", label: "Audit Log", icon: ScrollText },
    { href: "/admin/integrations", label: "Integrations & Alerts", icon: Webhook },
    { href: "/admin/system", label: "System Admin", icon: Zap },
    { href: "/admin/devops", label: "DevOps Hub", icon: Server },
    { href: "/customer/dashboard", label: "Customer View", icon: LayoutDashboard },
  ]},
];



export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <ProtectedRoute allowedRoles={["compliance_officer", "admin"]}>
      <div className="min-h-screen bg-zinc-50 flex flex-col">
        {/* Admin Navigation */}
        <header className="sticky top-0 z-50 border-b border-zinc-200 bg-zinc-900 text-white shadow-md">
          <div className="flex h-16 items-center justify-between px-6">
            <div className="flex items-center gap-2.5 font-bold">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600">
                <ShieldCheck className="h-4.5 w-4.5 text-white" />
              </div>
              <span>
                AML Compliance{" "}
                <span className="text-teal-400">
                  {user?.role === "admin" ? "System Admin Panel" : "Officer Panel"}
                </span>
              </span>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className={cn(
                  "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                  user?.role === "admin" ? "bg-purple-900/80 text-purple-200 border border-purple-700" : "bg-indigo-900/80 text-indigo-200 border border-indigo-700"
                )}>
                  {user?.role === "admin" ? "Administrator" : "Compliance Officer"}
                </span>
                <span className="text-xs text-zinc-400 font-medium">
                  <span className="text-white">{user?.email}</span>
                </span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" /> Sign out
              </button>
            </div>
          </div>
        </header>

        <div className="flex flex-1">
          {/* Admin Sidebar */}
          <aside className="w-56 shrink-0 border-r border-zinc-200 bg-white p-4 space-y-5">
            {navItems.map((section) => (
              <div key={section.section}>
                <p className="px-3 text-[10px] font-bold uppercase tracking-widest text-zinc-400 mb-1">
                  {section.section}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const active = pathname === item.href || (item.href !== "/customer/dashboard" && pathname?.startsWith(item.href));
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-semibold transition-all",
                          active
                            ? "bg-teal-50 text-teal-800"
                            : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
                        )}
                      >
                        <Icon className={cn("h-4 w-4", active ? "text-teal-600" : "text-zinc-400")} />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </aside>

          {/* Admin Content */}
          <main className="flex-1 p-8 overflow-auto">
            {children}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
