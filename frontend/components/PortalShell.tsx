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
  const isAdmin = pathname?.startsWith("/admin");

  const showSidebar = token && !isAuthPage && !isLanding && !isAdmin;
  const showNavbar = !isAdmin;

  return (
    <>
      {showNavbar && <Navbar />}
      <div className={showNavbar ? "flex min-h-[calc(100vh-4rem)]" : "flex min-h-screen"}>
        {showSidebar && <Sidebar />}
        <main className={`flex-1 ${showSidebar ? "p-5 md:p-8" : "p-0"} overflow-auto`}>
          {children}
        </main>
      </div>
    </>
  );
}
