"use client";

import React from "react";
import { Navbar } from "@/components/Navbar";
import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/context/AuthContext";
import { usePathname } from "next/navigation";

const AUTH_ROUTES = ["/auth/login", "/auth/register"];

export function PortalShell({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const pathname = usePathname();
  const isAuthPage = AUTH_ROUTES.some((r) => pathname?.startsWith(r));
  const isLanding = pathname === "/";

  const showSidebar = token && !isAuthPage && !isLanding;

  return (
    <>
      <Navbar />
      <div className="flex min-h-[calc(100vh-4rem)]">
        {showSidebar && <Sidebar />}
        <main className={`flex-1 ${showSidebar ? "p-5 md:p-8" : "p-0"} overflow-auto`}>
          {children}
        </main>
      </div>
    </>
  );
}
