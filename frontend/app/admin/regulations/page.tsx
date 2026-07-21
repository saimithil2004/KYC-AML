"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { listRegulations, uploadRegulation } from "@/lib/api";
import type { Regulation, Paginated } from "@/lib/types";
import {
  FileText, Upload, Search, RefreshCw, ChevronLeft, ChevronRight,
  BookOpen, Calendar, HelpCircle, CheckCircle, AlertCircle, Plus,
} from "lucide-react";
import Link from "next/link";

const PAGE_SIZE = 10;

export default function RegulationsListPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [data, setData] = useState<Paginated<Regulation> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterCountry, setFilterCountry] = useState("");
  const [loading, setLoading] = useState(false);

  // Upload modal states
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");

  const [formTitle, setFormTitle] = useState("");
  const [formAuthority, setFormAuthority] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formCountry, setFormCountry] = useState("");
  const [formJurisdiction, setFormJurisdiction] = useState("");
  const [formRegulator, setFormRegulator] = useState("");
  const [formType, setFormType] = useState("");
  const [formVersion, setFormVersion] = useState("1.0.0");
  const [formEffectiveDate, setFormEffectiveDate] = useState("");
  const [formExpiryDate, setFormExpiryDate] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listRegulations(token, {
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        country: filterCountry || undefined,
      });
      setData(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, page, search, filterCountry]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedFile) {
      setUploadError("Please select a file to upload.");
      return;
    }

    setUploading(true);
    setUploadError("");
    setUploadSuccess("");

    const formData = new FormData();
    formData.append("title", formTitle);
    formData.append("authority", formAuthority);
    formData.append("description", formDescription);
    formData.append("country", formCountry);
    formData.append("jurisdiction", formJurisdiction);
    formData.append("regulator", formRegulator);
    formData.append("regulation_type", formType);
    formData.append("version", formVersion);
    if (formEffectiveDate) formData.append("effective_date", formEffectiveDate);
    if (formExpiryDate) formData.append("expiry_date", formExpiryDate);
    formData.append("file", selectedFile);

    try {
      await uploadRegulation(token, formData);
      setUploadSuccess("Regulation uploaded and text extracted successfully!");
      setUploadOpen(false);
      // Reset form
      setFormTitle("");
      setFormAuthority("");
      setFormDescription("");
      setFormCountry("");
      setFormJurisdiction("");
      setFormRegulator("");
      setFormType("");
      setFormVersion("1.0.0");
      setFormEffectiveDate("");
      setFormExpiryDate("");
      setSelectedFile(null);
      fetchData();
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload regulation");
    } finally {
      setUploading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-6 animate-fade-in text-zinc-800 dark:text-zinc-200">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white flex items-center gap-2">
            <BookOpen className="text-teal-600 h-6.5 w-6.5" /> Regulations Library
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Ingest policies & regulations to generate automated compliance PolicyRules
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm font-medium hover:bg-zinc-50 transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {isAdmin && (
            <button
              onClick={() => {
                setUploadOpen(true);
                setUploadError("");
                setUploadSuccess("");
              }}
              className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-sm font-bold text-white hover:bg-teal-700 transition shadow-sm"
            >
              <Upload className="h-4 w-4" />
              Upload Regulation
            </button>
          )}
        </div>
      </div>

      {/* Success Notification Banner */}
      {uploadSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 p-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />
          <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-400">{uploadSuccess}</p>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
          <input
            type="text"
            placeholder="Search regulations by title, description or regulator..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 pl-9 pr-3 py-2 text-sm placeholder:text-zinc-400 focus:border-teal-500 focus:outline-none"
          />
        </div>
        <input
          type="text"
          placeholder="Filter country..."
          value={filterCountry}
          onChange={(e) => {
            setFilterCountry(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        />
      </div>

      {/* Upload Dialog (Modal overlay) */}
      {uploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-xl bg-white dark:bg-zinc-900 rounded-xl border border-zinc-250 dark:border-zinc-800 p-6 space-y-4 max-h-[90vh] overflow-y-auto shadow-xl">
            <div className="flex justify-between items-center border-b pb-3 dark:border-zinc-800">
              <h3 className="text-lg font-bold text-zinc-900 dark:text-white flex items-center gap-2">
                <Upload className="text-teal-600 h-5 w-5" /> Ingest Regulation File
              </h3>
              <button
                onClick={() => setUploadOpen(false)}
                className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              >
                ✕
              </button>
            </div>

            {uploadError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 rounded-lg text-xs text-red-700 dark:text-red-400">
                {uploadError}
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Regulation Title *</label>
                  <input
                    type="text"
                    required
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    placeholder="e.g. FCA Anti-Money Laundering Regulations 2026"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Regulator / Authority *</label>
                  <input
                    type="text"
                    required
                    value={formAuthority}
                    onChange={(e) => setFormAuthority(e.target.value)}
                    placeholder="e.g. FCA"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Regulated Country</label>
                  <input
                    type="text"
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value)}
                    placeholder="e.g. United Kingdom"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Jurisdiction</label>
                  <input
                    type="text"
                    value={formJurisdiction}
                    onChange={(e) => setFormJurisdiction(e.target.value)}
                    placeholder="e.g. European Union"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Regulation Version</label>
                  <input
                    type="text"
                    value={formVersion}
                    onChange={(e) => setFormVersion(e.target.value)}
                    placeholder="e.g. 1.0.0"
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Effective Date</label>
                  <input
                    type="date"
                    value={formEffectiveDate}
                    onChange={(e) => setFormEffectiveDate(e.target.value)}
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-zinc-650 dark:text-zinc-400">Expiry Date</label>
                  <input
                    type="date"
                    value={formExpiryDate}
                    onChange={(e) => setFormExpiryDate(e.target.value)}
                    className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-zinc-650 dark:text-zinc-400">Brief Description</label>
                <textarea
                  rows={2}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Overview of scope and reporting targets..."
                  className="w-full rounded border px-3 py-2 dark:bg-zinc-800 dark:border-zinc-700"
                />
              </div>

              <div className="space-y-2.5 rounded-lg border-2 border-dashed border-zinc-200 dark:border-zinc-850 p-4 text-center">
                <input
                  type="file"
                  id="reg-file-upload"
                  accept=".pdf,.docx,.txt,.md"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <label htmlFor="reg-file-upload" className="cursor-pointer space-y-1.5 block">
                  <Upload className="h-8 w-8 text-teal-600 mx-auto" />
                  <span className="block font-bold text-zinc-700 dark:text-zinc-300">
                    {selectedFile ? selectedFile.name : "Select Document File"}
                  </span>
                  <span className="block text-[10px] text-zinc-450">
                    Supports PDF, DOCX, TXT, or Markdown formats
                  </span>
                </label>
              </div>

              <div className="flex gap-2 justify-end pt-3 border-t dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setUploadOpen(false)}
                  className="rounded border border-zinc-200 hover:bg-zinc-50 px-4 py-2 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="rounded bg-teal-600 hover:bg-teal-700 text-white font-bold px-6 py-2 disabled:opacity-50"
                >
                  {uploading ? "Extracting Text…" : "Ingest & Extract"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Regulations Cards List */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : !data?.items.length ? (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-12 text-center text-zinc-400">
            <BookOpen className="h-8 w-8 mx-auto mb-2 text-zinc-350" />
            <p className="text-sm">No regulation documents found</p>
          </div>
        ) : (
          data.items.map((reg) => (
            <div
              key={reg.id}
              className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 shadow-sm flex items-start gap-4 hover:shadow-md transition-shadow"
            >
              <div className="p-3 bg-teal-50 dark:bg-teal-950/20 rounded-xl shrink-0">
                <BookOpen className="h-6 w-6 text-teal-600" />
              </div>
              <div className="flex-1 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-bold text-zinc-900 dark:text-white hover:text-teal-600">
                    <Link href={`/admin/regulations/${reg.id}`}>{reg.title}</Link>
                  </h3>
                  <span className="text-[10px] bg-zinc-150 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded px-2 py-0.5">
                    v{reg.version}
                  </span>
                  <span className="text-[10px] bg-teal-50 dark:bg-teal-950/20 text-teal-700 rounded px-2 py-0.5 capitalize">
                    {reg.status}
                  </span>
                </div>
                <p className="text-xs text-zinc-550 line-clamp-2">{reg.description || "No description provided."}</p>
                <div className="flex items-center gap-4 text-[10px] text-zinc-450 flex-wrap">
                  <span className="font-bold">Regulator: {reg.authority}</span>
                  {reg.country && <span>Country: {reg.country}</span>}
                  {reg.effective_date && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Eff: {reg.effective_date}
                    </span>
                  )}
                </div>
              </div>
              <Link
                href={`/admin/regulations/${reg.id}`}
                className="shrink-0 text-xs font-bold text-teal-600 hover:text-teal-800 hover:underline"
              >
                Manage & Rules →
              </Link>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded border border-zinc-200 dark:border-zinc-700 p-2 text-zinc-450 disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-xs font-bold px-3">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded border border-zinc-200 dark:border-zinc-700 p-2 text-zinc-450 disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
