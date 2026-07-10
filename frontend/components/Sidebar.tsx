"use client";

import Link from "next/link";
import { FileUp, Gauge, IdCard, UserRound } from "lucide-react";

const links = [
  { href: "/customer/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/customer/profile", label: "Profile", icon: UserRound },
  { href: "/customer/kyc", label: "KYC Form", icon: IdCard },
  { href: "/customer/documents", label: "Documents", icon: FileUp },
];

export function Sidebar() {
  return (
    <aside className="hidden w-64 border-r border-zinc-200 bg-zinc-50 p-4 md:block">
      <nav className="space-y-1">
        {links.map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-white hover:text-teal-800">
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
