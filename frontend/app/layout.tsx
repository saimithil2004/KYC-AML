import React from "react";
import "./globals.css";
import { Inter } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import { ReactQueryProvider } from "@/lib/query-client";
import { Toaster } from "sonner";
import { PortalShell } from "@/components/PortalShell";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata = {
  title: "UK Compliance — AML & KYC Portal",
  description:
    "Agentic AI-powered AML and KYC compliance management platform for financial institutions.",
  keywords: ["AML", "KYC", "compliance", "financial regulation", "anti-money laundering"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-zinc-50 text-zinc-950 font-sans antialiased">
        <ReactQueryProvider>
          <AuthProvider>
            <PortalShell>{children}</PortalShell>
            <Toaster position="top-right" richColors closeButton />
          </AuthProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
