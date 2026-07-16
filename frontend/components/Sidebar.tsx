"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Gauge,
  UserRound,
  FileText,
  Upload,
  Building2,
  ClipboardCheck,
  Activity,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navSections = [
  {
    label: "Overview",
    items: [
      { href: "/customer/dashboard", label: "Dashboard", icon: Gauge },
    ],
  },
  {
    label: "Onboarding",
    items: [
      { href: "/customer/onboarding/profile", label: "Profile", icon: UserRound },
      { href: "/customer/onboarding/kyc", label: "KYC Form", icon: FileText },
      { href: "/customer/onboarding/documents", label: "Documents", icon: Upload },
      { href: "/customer/onboarding/company", label: "Company", icon: Building2 },
      { href: "/customer/onboarding/review", label: "Review & Submit", icon: ClipboardCheck },
    ],
  },
  {
    label: "Status",
    items: [
      { href: "/customer/status", label: "Application Status", icon: Activity },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 border-r border-zinc-200 bg-white md:block">
      <nav className="sticky top-16 max-h-[calc(100vh-4rem)] overflow-y-auto p-3">
        {navSections.map((section) => (
          <div key={section.label} className="mb-4">
            <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href ||
                  (item.href !== "/customer/dashboard" &&
                    pathname?.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-all",
                      active
                        ? "bg-teal-50 text-teal-800 shadow-sm"
                        : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
                    )}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={cn(
                          "h-4 w-4 transition-colors",
                          active ? "text-teal-700" : "text-zinc-400 group-hover:text-zinc-600"
                        )}
                      />
                      {item.label}
                    </div>
                    {active && (
                      <ChevronRight className="h-3.5 w-3.5 text-teal-600" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
