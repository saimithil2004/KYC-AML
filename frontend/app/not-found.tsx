import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <h1 className="text-4xl font-bold text-zinc-900">404</h1>
      <p className="mt-2 text-sm text-zinc-600">Page not found</p>
      <Link
        href="/"
        className="mt-4 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 transition-colors"
      >
        Return Home
      </Link>
    </div>
  );
}
