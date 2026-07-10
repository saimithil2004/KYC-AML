import React from "react";
import "./globals.css";
import { AuthProvider } from "../context/AuthContext";
import { Navbar } from "../components/Navbar";
import { Sidebar } from "../components/Sidebar";

export const metadata = {
  title: "UK Compliance AML & KYC Portal",
  description: "Agentic AI compliance management platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-100 text-zinc-950">
        <AuthProvider>
          <Navbar />
          <div className="flex min-h-[calc(100vh-4rem)]">
            <Sidebar />
            <main className="flex-1 p-5 md:p-8">
            {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
