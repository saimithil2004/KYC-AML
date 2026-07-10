"use client";

import Link from "next/link";
import { ShieldCheck, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="flex h-16 items-center justify-between px-5">
        <Link href="/customer/dashboard" className="flex items-center gap-2 font-semibold text-zinc-950">
          <ShieldCheck className="h-5 w-5 text-teal-700" />
          AML KYC Portal
        </Link>
        <div className="flex items-center gap-3 text-sm">
          {user && <span className="hidden text-zinc-500 sm:inline">{user.email}</span>}
          {user ? (
            <button onClick={logout} className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-zinc-700 hover:bg-zinc-50">
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          ) : (
            <Link href="/auth/login" className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-700 hover:bg-zinc-50">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
