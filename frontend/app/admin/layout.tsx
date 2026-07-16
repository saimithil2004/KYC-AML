"use client";

import React from "react";
import Link from "next/link";
import { ShieldCheck, LogOut, LayoutDashboard, FileCheck, Users, HelpCircle } from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";

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
              <span>UK Compliance <span className="text-teal-400">Officer Panel</span></span>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-xs text-zinc-400 font-medium">
                Logged in: <span className="text-white">{user?.email}</span>
              </span>
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
          <aside className="w-56 shrink-0 border-r border-zinc-200 bg-white p-4 space-y-1">
            <p className="px-3 text-[10px] font-bold uppercase tracking-widest text-zinc-400 mb-2">Navigation</p>
            {[
              { href: "/admin/documents", label: "Verification Desk", icon: FileCheck },
              { href: "/customer/dashboard", label: "Customer View", icon: LayoutDashboard },
            ].map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
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
                  <Icon className="h-4 w-4 text-zinc-400" />
                  {item.label}
                </Link>
              );
            })}
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
