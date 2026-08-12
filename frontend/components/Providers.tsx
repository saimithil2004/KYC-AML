"use client";

import React from "react";
import { AuthProvider } from "@/context/AuthContext";
import { ReactQueryProvider } from "@/lib/query-client";
import { Toaster } from "sonner";
import { PortalShell } from "@/components/PortalShell";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ReactQueryProvider>
      <AuthProvider>
        <PortalShell>{children}</PortalShell>
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </ReactQueryProvider>
  );
}
