"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, LogOut, Menu, X, Bell } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "??";

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-200 bg-white/95 backdrop-blur-sm shadow-sm">
      <div className="flex h-16 items-center justify-between px-4 md:px-6">
        {/* Logo */}
        <Link
          href={user ? "/customer/dashboard" : "/"}
          className="flex items-center gap-2.5 font-bold text-zinc-900 hover:opacity-80 transition-opacity"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-700">
            <ShieldCheck className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="hidden text-sm sm:block">
            AML <span className="text-teal-700">KYC</span> Portal
          </span>
        </Link>

        {/* Right section */}
        <div className="flex items-center gap-2">
          {user && (
            <>
              <button className="relative rounded-full p-2 text-zinc-500 hover:bg-zinc-100 transition-colors">
                <Bell className="h-4 w-4" />
                <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-teal-500" />
              </button>

              <div className="hidden items-center gap-3 sm:flex">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                    {initials}
                  </div>
                  <div className="hidden md:block">
                    <p className="text-xs font-medium text-zinc-900 leading-tight">{user.email}</p>
                    <p className="text-[10px] text-zinc-500 capitalize">{user.role.replace("_", " ")}</p>
                  </div>
                </div>

                <button
                  onClick={logout}
                  className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </div>

              <button
                className="rounded-md p-2 text-zinc-500 hover:bg-zinc-100 sm:hidden"
                onClick={() => setMobileOpen(!mobileOpen)}
              >
                {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </>
          )}

          {!user && (
            <div className="flex items-center gap-2">
              <Link
                href="/auth/login"
                className={cn(
                  "rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors",
                  pathname === "/auth/login" && "border-teal-200 bg-teal-50 text-teal-800"
                )}
              >
                Sign in
              </Link>
              <Link
                href="/auth/register"
                className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && user && (
        <div className="border-t border-zinc-100 bg-white px-4 py-3 sm:hidden animate-fade-in">
          <p className="text-xs text-zinc-500 mb-1">{user.email}</p>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-sm text-red-600 hover:text-red-700"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
