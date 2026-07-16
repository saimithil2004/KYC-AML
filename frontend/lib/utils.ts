import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(dateString));
  } catch {
    return dateString;
  }
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getStatusColor(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("approved") || s.includes("verified") || s.includes("completed")) {
    return "text-emerald-700 bg-emerald-50 border-emerald-200";
  }
  if (s.includes("reject") || s.includes("fail") || s.includes("sanction")) {
    return "text-red-700 bg-red-50 border-red-200";
  }
  if (s.includes("pending") || s.includes("review") || s.includes("upload")) {
    return "text-amber-700 bg-amber-50 border-amber-200";
  }
  if (s.includes("onboard") || s.includes("progress") || s.includes("invest")) {
    return "text-blue-700 bg-blue-50 border-blue-200";
  }
  return "text-zinc-700 bg-zinc-50 border-zinc-200";
}

export function getRiskColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case "high": return "text-red-700 bg-red-50 border-red-200";
    case "medium": return "text-amber-700 bg-amber-50 border-amber-200";
    case "low": return "text-emerald-700 bg-emerald-50 border-emerald-200";
    default: return "text-zinc-600 bg-zinc-50 border-zinc-200";
  }
}
