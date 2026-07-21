"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  getFullHealth, listBackups, triggerBackup, verifyBackup, deleteBackup,
  getLoginHistory, changePassword, enrollMfa, verifyMfa, disableMfa
} from "@/lib/api";
import {
  Shield, Key, Lock, History, HardDrive, Cpu, Database, RefreshCw, Zap,
  CheckCircle, XCircle, AlertTriangle, Plus, Trash2, ShieldAlert,
  Server, FileArchive, CheckSquare, Settings, Activity, ClipboardList, Copy
} from "lucide-react";
import type { FullObservabilityReport, BackupRecord, LoginHistoryEntry, MFAEnrollData } from "@/lib/types";

// ─── Utility Helpers ─────────────────────────────────────────────────────────

const badgeClass = (status: string) => {
  const map: Record<string, string> = {
    healthy: "bg-emerald-100 text-emerald-800 border-emerald-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    verified: "bg-emerald-100 text-emerald-800 border-emerald-200",
    completed: "bg-emerald-100 text-emerald-800 border-emerald-200",
    pending: "bg-amber-100 text-amber-800 border-amber-200",
    failed: "bg-rose-100 text-rose-800 border-rose-200",
    unhealthy: "bg-rose-100 text-rose-800 border-rose-200",
  };
  return `px-2 py-0.5 rounded-full text-xs font-semibold border ${map[status.toLowerCase()] ?? "bg-zinc-100 text-zinc-600 border-zinc-200"}`;
};

const formatSize = (bytes?: number) => {
  if (!bytes) return "—";
  const mb = bytes / (1024 * 1024);
  return mb < 1000 ? `${mb.toFixed(2)} MB` : `${(mb / 1024).toFixed(2)} GB`;
};

const fmtDate = (dt?: string) =>
  dt ? new Date(dt).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "—";

// ─── Page Component ──────────────────────────────────────────────────────────

export default function SystemAdminPage() {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<"health" | "security" | "history" | "backups">("health");
  
  // Loading & Error States
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Observability & System Data
  const [healthData, setHealthData] = useState<FullObservabilityReport | null>(null);
  const [backups, setBackups] = useState<BackupRecord[]>([]);
  const [loginHistory, setLoginHistory] = useState<LoginHistoryEntry[]>([]);

  // Password Change
  const [passForm, setPassForm] = useState({ old_password: "", new_password: "" });

  // MFA setup states
  const [mfaEnrolled, setMfaEnrolled] = useState<MFAEnrollData | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaEnabled, setMfaEnabled] = useState(false);

  // ─── Fetch Action Operations ────────────────────────────────────────────────

  const loadHealth = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getFullHealth(token);
      setHealthData(data);
      // Determine if MFA is currently set on the current session user
      if (user?.id) {
        // Assume MFA enabled if user model states it (or if secret setup state returns true)
        setMfaEnabled(!!user.mfa_enabled);
      }
    } catch (e: any) {
      setErrorMsg("Failed to query full system observability logs.");
    }
  }, [token, user]);

  const loadBackups = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listBackups(token);
      setBackups(data);
    } catch {}
  }, [token]);

  const loadLoginHistory = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getLoginHistory(token);
      setLoginHistory(data);
    } catch {}
  }, [token]);

  // Combined Refresh
  const refreshAll = useCallback(async () => {
    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      if (activeTab === "health") await loadHealth();
      else if (activeTab === "backups") await loadBackups();
      else if (activeTab === "history") await loadLoginHistory();
    } catch (e: any) {
      setErrorMsg(e.message || "An error occurred during fetch.");
    } finally {
      setLoading(false);
    }
  }, [activeTab, loadHealth, loadBackups, loadLoginHistory]);

  useEffect(() => {
    refreshAll();
  }, [activeTab, refreshAll]);

  // ─── Tab-Specific Action Handlers ───────────────────────────────────────────

  // 1. Password Change
  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await changePassword(token, passForm);
      setSuccessMsg("Password changed successfully.");
      setPassForm({ old_password: "", new_password: "" });
    } catch (e: any) {
      setErrorMsg(e.message || "Password change rejected.");
    }
  };

  // 2. MFA Enrollment Setup
  const handleEnrollMfa = async () => {
    if (!token) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const data = await enrollMfa(token);
      setMfaEnrolled(data);
    } catch (e: any) {
      setErrorMsg("Failed to initialize multi-factor configuration enrollment.");
    }
  };

  const handleConfirmMfa = async () => {
    if (!token || !mfaCode) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const res = await verifyMfa(token, mfaCode);
      if (res.success) {
        setSuccessMsg("TOTP Multi-factor authentication successfully configured!");
        setMfaEnabled(true);
        setMfaEnrolled(null);
        setMfaCode("");
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Verification code mismatch.");
    }
  };

  const handleDisableMfa = async () => {
    if (!token || !confirm("Disable Multi-factor authentication? Security logs will record this action.")) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await disableMfa(token);
      setMfaEnabled(false);
      setSuccessMsg("MFA has been disabled.");
    } catch (e: any) {
      setErrorMsg("Failed to disable TOTP security settings.");
    }
  };

  // 3. Backup Handlers
  const handleTriggerBackup = async (type: "database" | "documents" | "config" | "full") => {
    if (!token) return;
    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const record = await triggerBackup(token, type);
      setSuccessMsg(`Manual backup archive triggered successfully: ${record.file_name}`);
      await loadBackups();
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to compile manual system backup archive.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyBackup = async (id: string) => {
    if (!token) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const res = await verifyBackup(token, id);
      setSuccessMsg(res.message);
      await loadBackups();
    } catch (e: any) {
      setErrorMsg(e.message || "Archive checksum verification failed.");
    }
  };

  const handleDeleteBackup = async (id: string) => {
    if (!token || !confirm("Permanently purge this backup from storage?")) return;
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await deleteBackup(token, id);
      setSuccessMsg("Backup archive purged successfully.");
      await loadBackups();
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to delete backup.");
    }
  };

  if (!token) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Premium Header */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white px-8 py-8 shadow-sm">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
              <Server className="h-6.5 w-6.5 text-teal-400" />
            </div>
            <div>
              <h1 className="text-2.5xl font-bold tracking-tight">System Administration Panel</h1>
              <p className="text-sm text-zinc-400">Hardening operations, audit checks, database backups & health metrics</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={refreshAll} disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg transition border border-zinc-700 disabled:opacity-50">
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh Data
            </button>
          </div>
        </div>
      </div>

      {/* Tab Selectors */}
      <div className="bg-white border-b border-zinc-200 px-8">
        <div className="max-w-7xl mx-auto flex gap-1">
          {([
            { id: "health", label: "Observability Metrics", icon: Activity },
            { id: "security", label: "MFA & Password Control", icon: Shield },
            { id: "history", label: "Brute-force Audit", icon: History },
            { id: "backups", label: "Backup & Restore", icon: FileArchive },
          ] as const).map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3.5 text-sm font-semibold border-b-2 transition ${
                activeTab === id ? "border-teal-600 text-teal-700" : "border-transparent text-zinc-500 hover:text-zinc-700"
              }`}>
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="max-w-7xl mx-auto px-8 py-8 space-y-6">
        
        {/* Message Banner Alerts */}
        {errorMsg && (
          <div className="flex items-center gap-2 px-5 py-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
            <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
            <p className="font-semibold">{errorMsg}</p>
          </div>
        )}
        {successMsg && (
          <div className="flex items-center gap-2 px-5 py-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm">
            <CheckCircle className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
            <p className="font-semibold">{successMsg}</p>
          </div>
        )}

        {/* TAB 1: OBSERVABILITY METRICS */}
        {activeTab === "health" && healthData && (
          <div className="space-y-6 animate-fadeIn">
            {/* System Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Overall Liveness</span>
                  <CheckSquare className="h-4 w-4 text-emerald-600" />
                </div>
                <p className="text-xl font-bold text-zinc-800">ONLINE</p>
                <p className="text-xs text-zinc-400 mt-1">Platform version {healthData.database.status === "healthy" ? "15.0.0" : "N/A"}</p>
              </div>
              <div className="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Database Latency</span>
                  <Database className="h-4 w-4 text-teal-600" />
                </div>
                <p className="text-xl font-bold text-zinc-800">{healthData.database.latency_ms} ms</p>
                <p className="text-xs text-zinc-400 mt-1">Status: <span className={badgeClass(healthData.database.status)}>{healthData.database.status}</span></p>
              </div>
              <div className="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Redis Latency</span>
                  <Zap className="h-4 w-4 text-amber-500" />
                </div>
                <p className="text-xl font-bold text-zinc-800">{healthData.redis.latency_ms} ms</p>
                <p className="text-xs text-zinc-400 mt-1">Status: <span className={badgeClass(healthData.redis.status)}>{healthData.redis.status}</span></p>
              </div>
              <div className="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Celery Workers</span>
                  <Cpu className="h-4 w-4 text-blue-600" />
                </div>
                <p className="text-xl font-bold text-zinc-800">{healthData.celery.active_workers} Active</p>
                <p className="text-xs text-zinc-400 mt-1">Queue length: {healthData.celery.queue_length} tasks</p>
              </div>
            </div>

            {/* Resources & Health Progress */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
                <h3 className="text-sm font-bold text-zinc-800 mb-4 flex items-center gap-1.5">
                  <Cpu className="h-4.5 w-4.5 text-zinc-500" /> System Resources
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs text-zinc-600 mb-1">
                      <span>CPU Utilization</span>
                      <span className="font-semibold">{healthData.system.cpu_percent}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 rounded-full h-2">
                      <div className="bg-teal-600 h-2 rounded-full" style={{ width: `${healthData.system.cpu_percent}%` }}></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs text-zinc-600 mb-1">
                      <span>Memory Utilization ({healthData.system.memory_used_mb}MB / {healthData.system.memory_total_mb}MB)</span>
                      <span className="font-semibold">{healthData.system.memory_percent}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${healthData.system.memory_percent}%` }}></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs text-zinc-600 mb-1">
                      <span>Disk Storage ({healthData.system.disk_used_gb}GB / {healthData.system.disk_total_gb}GB)</span>
                      <span className="font-semibold">{healthData.system.disk_percent}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 rounded-full h-2">
                      <div className="bg-purple-600 h-2 rounded-full" style={{ width: `${healthData.system.disk_percent}%` }}></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Cache Stats */}
              <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
                <h3 className="text-sm font-bold text-zinc-800 mb-4 flex items-center gap-1.5">
                  <Zap className="h-4.5 w-4.5 text-zinc-500" /> Cache Performance
                </h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="p-3 bg-zinc-50 rounded-lg">
                    <p className="text-xs text-zinc-400">Hits</p>
                    <p className="text-lg font-bold text-zinc-800">{healthData.cache.hits}</p>
                  </div>
                  <div className="p-3 bg-zinc-50 rounded-lg">
                    <p className="text-xs text-zinc-400">Misses</p>
                    <p className="text-lg font-bold text-zinc-800">{healthData.cache.misses}</p>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>Cache Backend:</span>
                    <span className="font-semibold capitalize">{healthData.cache.backend}</span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>Hit Ratio:</span>
                    <span className="font-bold text-teal-600">{healthData.cache.hit_rate}%</span>
                  </div>
                </div>
              </div>

              {/* API Statistics */}
              <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
                <h3 className="text-sm font-bold text-zinc-800 mb-4 flex items-center gap-1.5">
                  <ClipboardList className="h-4.5 w-4.5 text-zinc-500" /> API Metrics (Last 1h)
                </h3>
                <div className="space-y-3.5">
                  <div className="flex justify-between text-xs text-zinc-600 border-b border-zinc-100 pb-2">
                    <span>Total Request Count:</span>
                    <span className="font-semibold text-zinc-800">{healthData.api_stats.request_count_1h} requests</span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-600 border-b border-zinc-100 pb-2">
                    <span>Avg Endpoint Latency:</span>
                    <span className="font-semibold text-zinc-800">{healthData.api_stats.average_latency_ms} ms</span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-600 border-b border-zinc-100 pb-2">
                    <span>Error Rate:</span>
                    <span className={`font-bold ${healthData.api_stats.error_rate_percent > 5 ? "text-rose-600" : "text-emerald-600"}`}>
                      {healthData.api_stats.error_rate_percent}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-600 pb-1">
                    <span>Slow Requests (&gt;1s):</span>
                    <span className="font-semibold text-zinc-800">{healthData.api_stats.slow_requests_count}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MFA & PASSWORD CONTROL */}
        {activeTab === "security" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fadeIn">
            {/* Password Policy update */}
            <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
              <div className="flex items-center gap-2 mb-4 border-b border-zinc-100 pb-3">
                <Key className="h-5 w-5 text-teal-600" />
                <h2 className="text-md font-bold text-zinc-800 font-semibold">Change Password</h2>
              </div>
              <form onSubmit={handlePasswordChange} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-zinc-500 uppercase mb-1">Current Password</label>
                  <input type="password" required value={passForm.old_password}
                    onChange={(e) => setPassForm({ ...passForm, old_password: e.target.value })}
                    className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none focus:border-teal-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-zinc-500 uppercase mb-1">New Password</label>
                  <input type="password" required value={passForm.new_password}
                    onChange={(e) => setPassForm({ ...passForm, new_password: e.target.value })}
                    className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none focus:border-teal-500" />
                </div>
                <div className="p-3.5 bg-zinc-50 rounded-lg border border-zinc-200">
                  <p className="text-xs font-bold text-zinc-700 mb-1.5">Complexity Requirements:</p>
                  <ul className="text-[11px] text-zinc-500 list-disc pl-4 space-y-0.5">
                    <li>Minimum 8 characters long</li>
                    <li>At least 1 uppercase & 1 lowercase letter</li>
                    <li>At least 1 numerical digit & 1 special symbol</li>
                    <li>Cannot reuse any of your last 5 passwords</li>
                  </ul>
                </div>
                <button type="submit" className="w-full py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm font-semibold transition">
                  Change Password
                </button>
              </form>
            </div>

            {/* TOTP Multi-factor Authentication control */}
            <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
              <div className="flex items-center gap-2 mb-4 border-b border-zinc-100 pb-3">
                <Shield className="h-5 w-5 text-teal-600" />
                <h2 className="text-md font-bold text-zinc-800 font-semibold">Multi-Factor Authentication (MFA)</h2>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-xl border bg-zinc-50 border-zinc-200">
                  <div>
                    <p className="text-sm font-bold text-zinc-800">MFA Status</p>
                    <p className="text-xs text-zinc-500">Secure your logins with dynamic TOTP tokens</p>
                  </div>
                  <span className={badgeClass(mfaEnabled ? "healthy" : "failed")}>
                    {mfaEnabled ? "ACTIVE" : "INACTIVE"}
                  </span>
                </div>

                {!mfaEnabled && !mfaEnrolled && (
                  <button onClick={handleEnrollMfa} className="w-full py-2 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg text-sm font-semibold transition">
                    Enroll in TOTP Authenticator
                  </button>
                )}

                {mfaEnabled && (
                  <button onClick={handleDisableMfa} className="w-full py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-semibold transition">
                    Disable Authenticator MFA
                  </button>
                )}

                {/* Enrollment QR code screen */}
                {mfaEnrolled && (
                  <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl space-y-4 animate-fadeIn">
                    <div className="flex flex-col items-center">
                      <p className="text-xs text-center text-zinc-600 mb-3">Scan this QR code with Google Authenticator or Microsoft Authenticator</p>
                      {mfaEnrolled.qr_code_base64 ? (
                        <img src={`data:image/png;base64,${mfaEnrolled.qr_code_base64}`} alt="TOTP QR Code" className="w-48 h-48 border border-zinc-200 rounded-lg bg-white" />
                      ) : (
                        <div className="w-48 h-48 flex items-center justify-center border border-zinc-200 rounded-lg bg-white text-zinc-400 text-xs">
                          QR Unavailable (pyotp dev mode)
                        </div>
                      )}
                      <p className="text-xs font-mono bg-white border px-3 py-1.5 rounded-lg text-zinc-700 mt-3 select-all select-all">
                        Key: {mfaEnrolled.secret}
                      </p>
                    </div>

                    {/* Backup recovery keys */}
                    <div>
                      <p className="text-xs font-bold text-zinc-600 mb-1">MFA Backup Recovery Codes:</p>
                      <div className="grid grid-cols-2 gap-1.5 p-2 bg-white rounded-lg border text-xs font-mono text-zinc-600">
                        {mfaEnrolled.backup_codes.map((c, idx) => (
                          <div key={idx} className="flex justify-between px-2 py-0.5 hover:bg-zinc-50 rounded">
                            <span>{c}</span>
                          </div>
                        ))}
                      </div>
                      <p className="text-[10px] text-zinc-500 mt-1">⚠️ Store these codes securely. They allow login if you lose your phone.</p>
                    </div>

                    <div className="border-t border-zinc-200 pt-3 flex gap-2">
                      <input type="text" maxLength={6} placeholder="Enter 6-digit code" value={mfaCode}
                        onChange={(e) => setMfaCode(e.target.value)}
                        className="flex-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none text-center font-mono" />
                      <button onClick={handleConfirmMfa} className="px-5 bg-teal-600 text-white text-xs font-semibold rounded-lg hover:bg-teal-700">
                        Verify & Enable
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: LOGIN HISTORY */}
        {activeTab === "history" && (
          <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs animate-fadeIn">
            <div className="flex items-center gap-2 mb-4 border-b border-zinc-100 pb-3">
              <History className="h-5 w-5 text-teal-600" />
              <h2 className="text-md font-bold text-zinc-800 font-semibold">Login History Audit</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="text-zinc-500 border-b border-zinc-200">
                    <th className="pb-3 pr-4 font-bold uppercase tracking-wider">Email</th>
                    <th className="pb-3 pr-4 font-bold uppercase tracking-wider">IP Address</th>
                    <th className="pb-3 pr-4 font-bold uppercase tracking-wider">Browser/Agent</th>
                    <th className="pb-3 pr-4 font-bold uppercase tracking-wider">Country</th>
                    <th className="pb-3 pr-4 font-bold uppercase tracking-wider">Status</th>
                    <th className="pb-3 font-bold uppercase tracking-wider">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {loginHistory.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-zinc-400">
                        No login events recorded.
                      </td>
                    </tr>
                  )}
                  {loginHistory.map((entry) => (
                    <tr key={entry.id} className="border-b border-zinc-100 hover:bg-zinc-50 transition-colors">
                      <td className="py-2.5 pr-4 font-medium text-zinc-800">{entry.email || "—"}</td>
                      <td className="py-2.5 pr-4 font-mono text-zinc-600">{entry.ip_address || "—"}</td>
                      <td className="py-2.5 pr-4 text-zinc-500 truncate max-w-xs" title={entry.user_agent}>
                        {entry.user_agent || "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-zinc-600">{entry.country || "United Kingdom"}</td>
                      <td className="py-2.5 pr-4">
                        <span className={badgeClass(entry.success ? "success" : "failed")}>
                          {entry.success ? "SUCCESS" : `FAILED: ${entry.failure_reason}`}
                        </span>
                      </td>
                      <td className="py-2.5 text-zinc-500">{fmtDate(entry.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: BACKUP & RESTORE */}
        {activeTab === "backups" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Backup actions controls */}
            <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
              <h3 className="text-sm font-bold text-zinc-800 mb-4 flex items-center gap-1.5">
                <FileArchive className="h-4.5 w-4.5 text-zinc-500" /> Create System Backup
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <button onClick={() => handleTriggerBackup("database")} disabled={loading}
                  className="flex flex-col items-center gap-1.5 p-4 rounded-xl border border-zinc-200 hover:border-teal-500 hover:bg-zinc-50 text-center transition disabled:opacity-50">
                  <Database className="h-6 w-6 text-teal-600" />
                  <span className="text-xs font-semibold text-zinc-700">Database SQL</span>
                </button>
                <button onClick={() => handleTriggerBackup("documents")} disabled={loading}
                  className="flex flex-col items-center gap-1.5 p-4 rounded-xl border border-zinc-200 hover:border-teal-500 hover:bg-zinc-50 text-center transition disabled:opacity-50">
                  <HardDrive className="h-6 w-6 text-blue-600" />
                  <span className="text-xs font-semibold text-zinc-700">Uploaded Documents</span>
                </button>
                <button onClick={() => handleTriggerBackup("config")} disabled={loading}
                  className="flex flex-col items-center gap-1.5 p-4 rounded-xl border border-zinc-200 hover:border-teal-500 hover:bg-zinc-50 text-center transition disabled:opacity-50">
                  <Settings className="h-6 w-6 text-purple-600" />
                  <span className="text-xs font-semibold text-zinc-700">System Config</span>
                </button>
                <button onClick={() => handleTriggerBackup("full")} disabled={loading}
                  className="flex flex-col items-center gap-1.5 p-4 rounded-xl border border-zinc-200 hover:border-teal-500 hover:bg-teal-50 bg-teal-50/20 text-center transition disabled:opacity-50">
                  <Zap className="h-6 w-6 text-teal-600" />
                  <span className="text-xs font-semibold text-zinc-800">Full Archive</span>
                </button>
              </div>
            </div>

            {/* Backups List */}
            <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-xs">
              <h3 className="text-sm font-bold text-zinc-800 mb-4 flex items-center gap-1.5">
                <ClipboardList className="h-4.5 w-4.5 text-zinc-500" /> Backup Archives History
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="text-zinc-500 border-b border-zinc-200">
                      <th className="pb-3 pr-4 font-bold uppercase">Filename</th>
                      <th className="pb-3 pr-4 font-bold uppercase">Type</th>
                      <th className="pb-3 pr-4 font-bold uppercase">Size</th>
                      <th className="pb-3 pr-4 font-bold uppercase">Status</th>
                      <th className="pb-3 pr-4 font-bold uppercase">Trigger</th>
                      <th className="pb-3 pr-4 font-bold uppercase">Created</th>
                      <th className="pb-3 font-bold uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backups.length === 0 && (
                      <tr>
                        <td colSpan={7} className="py-6 text-center text-zinc-400">
                          No system backup archives found.
                        </td>
                      </tr>
                    )}
                    {backups.map((b) => (
                      <tr key={b.id} className="border-b border-zinc-100 hover:bg-zinc-50">
                        <td className="py-2.5 pr-4 font-medium text-zinc-800 max-w-xs truncate" title={b.file_name}>
                          {b.file_name}
                        </td>
                        <td className="py-2.5 pr-4 capitalize text-zinc-600">{b.backup_type}</td>
                        <td className="py-2.5 pr-4 text-zinc-500 font-mono">{formatSize(b.file_size_bytes)}</td>
                        <td className="py-2.5 pr-4">
                          <span className={badgeClass(b.status)}>{b.status}</span>
                        </td>
                        <td className="py-2.5 pr-4 capitalize text-zinc-500">{b.triggered_by}</td>
                        <td className="py-2.5 pr-4 text-zinc-500">{fmtDate(b.created_at)}</td>
                        <td className="py-2.5 flex items-center gap-2">
                          {b.status === "completed" && (
                            <button onClick={() => handleVerifyBackup(b.id)}
                              className="px-2 py-1 text-xs text-teal-600 hover:bg-teal-50 border border-teal-200 rounded-md transition font-semibold">
                              Verify Checksum
                            </button>
                          )}
                          <button onClick={() => handleDeleteBackup(b.id)}
                            className="p-1.5 text-rose-600 hover:bg-rose-50 border border-rose-100 rounded-lg transition" title="Delete backup file">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
