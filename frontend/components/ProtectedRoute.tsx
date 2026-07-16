"use client";
import React, { useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";

export const ProtectedRoute: React.FC<{ children: React.ReactNode; allowedRoles?: string[] }> = ({ 
  children, 
  allowedRoles 
}) => {
  const { user, token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (!token || !user) {
        router.push("/auth/login");
      } else if (allowedRoles && !allowedRoles.includes(user.role)) {
        router.push("/customer/dashboard");
      }
    }
  }, [user, token, isLoading, router, allowedRoles]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-400">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-teal-700" />
      </div>
    );
  }

  return (token && user) ? <>{children}</> : null;
};
