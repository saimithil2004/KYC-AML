"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  getIntegrationSettings, createIntegrationSetting, updateIntegrationSetting, deleteIntegrationSetting,
  triggerManualSync, triggerSyncAll, getSyncStatus, getProviderHealth,
  getNotificationTemplates, createNotificationTemplate, deleteNotificationTemplate,
  getNotificationHistory, getWebhooks, createWebhook, deleteWebhook, testWebhook,
  getWebhookLogs, getAllWebhookLogs, getWebhookEvents,
} from "@/lib/api";
import {
  Webhook, Bell, RefreshCw, CheckCircle, XCircle, Clock, Plus, Trash2,
  Play, Settings, Zap, Activity, AlertTriangle, Shield, Globe, Database,
  ChevronDown, ChevronUp, ExternalLink, Copy, Eye, EyeOff,
} from "lucide-react";

// ─── Utilities ────────────────────────────────────────────────────────────────

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-800",
    success: "bg-emerald-100 text-emerald-800",
    started: "bg-blue-100 text-blue-800",
    failed: "bg-red-100 text-red-800",
    pending: "bg-amber-100 text-amber-800",
    retry: "bg-purple-100 text-purple-800",
    healthy: "bg-emerald-100 text-emerald-800",
    mock: "bg-zinc-100 text-zinc-600",
    never: "bg-zinc-100 text-zinc-500",
    sent: "bg-emerald-100 text-emerald-800",
  };
  const base = "px-2 py-0.5 rounded-full text-xs font-semibold";
  return `${base} ${map[status] ?? "bg-zinc-100 text-zinc-700"}`;
};

const fmt = (dt?: string) =>
  dt ? new Date(dt).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "—";

const PROVIDERS = ["opensanctions", "companies_house", "fatf", "pep_list", "sanctions_list"];

// ─── Section Card ─────────────────────────────────────────────────────────────

function SectionCard({ title, icon: Icon, children, accent = "teal" }: {
  title: string; icon: any; children: React.ReactNode; accent?: string;
}) {
  const accentMap: Record<string, string> = {
    teal: "border-teal-500", blue: "border-blue-500", purple: "border-purple-500",
    amber: "border-amber-500", rose: "border-rose-500",
  };
  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-zinc-100 border-l-4 ${accentMap[accent] ?? "border-teal-500"} overflow-hidden`}>
      <div className="flex items-center gap-2.5 px-6 py-4 border-b border-zinc-100">
        <Icon className="h-5 w-5 text-zinc-500" />
        <h2 className="text-sm font-semibold text-zinc-800">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

// ─── Provider Health Cards ────────────────────────────────────────────────────

function ProviderHealthSection({ token }: { token: string }) {
  const [health, setHealth] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProviderHealth(token);
      setHealth(Array.isArray(data) ? data : []);
    } catch { setHealth([]); } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <SectionCard title="Compliance Provider Health" icon={Shield} accent="teal">
      <div className="flex justify-end mb-4">
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition disabled:opacity-50">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {health.length === 0 && !loading && (
          <p className="col-span-3 text-sm text-zinc-400 text-center py-4">No provider data. Click Refresh.</p>
        )}
        {health.map((h) => (
          <div key={h.provider} className="rounded-xl border border-zinc-100 p-4 bg-zinc-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-zinc-700 capitalize">{h.provider.replace(/_/g, " ")}</span>
              <span className={statusBadge(h.status)}>{h.status}</span>
            </div>
            {h.mock_mode && <p className="text-xs text-amber-600 mb-1">⚠ Mock Mode</p>}
            <p className="text-xs text-zinc-500">Version: {h.version}</p>
            <p className="text-xs text-zinc-500">Last Sync: {fmt(h.last_sync)}</p>
            <p className="text-xs text-zinc-500">Sync Status: <span className={statusBadge(h.last_sync_status)}>{h.last_sync_status}</span></p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ─── Manual Sync Section ──────────────────────────────────────────────────────

function ManualSyncSection({ token }: { token: string }) {
  const [syncing, setSyncing] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);

  const syncOne = async (provider: string) => {
    setSyncing(provider);
    try {
      const r = await triggerManualSync(token, provider);
      setResults((prev) => [{ ...r, _provider: provider, _ts: new Date().toISOString() }, ...prev].slice(0, 20));
    } catch (e: any) {
      setResults((prev) => [{ _provider: provider, status: "failed", error: e.message, _ts: new Date().toISOString() }, ...prev].slice(0, 20));
    } finally { setSyncing(null); }
  };

  const syncAll = async () => {
    setSyncing("__all__");
    try {
      const r = await triggerSyncAll(token);
      const rs = (r.results || []).map((x: any) => ({ ...x, _ts: new Date().toISOString() }));
      setResults((prev) => [...rs, ...prev].slice(0, 40));
    } catch (e: any) {
      setResults((prev) => [{ status: "failed", error: e.message, _ts: new Date().toISOString() }, ...prev].slice(0, 20));
    } finally { setSyncing(null); }
  };

  return (
    <SectionCard title="Manual Synchronization" icon={RefreshCw} accent="blue">
      <div className="flex flex-wrap gap-2 mb-6">
        {PROVIDERS.map((p) => (
          <button key={p} onClick={() => syncOne(p)} disabled={!!syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 capitalize">
            {syncing === p ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            {p.replace(/_/g, " ")}
          </button>
        ))}
        <button onClick={syncAll} disabled={!!syncing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition disabled:opacity-50 font-semibold">
          {syncing === "__all__" ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          Sync All Providers
        </button>
      </div>
      {results.length > 0 && (
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {results.map((r, i) => (
            <div key={i} className="flex items-center gap-3 text-xs bg-zinc-50 rounded-lg p-2 border border-zinc-100">
              <span className={statusBadge(r.status)}>{r.status}</span>
              <span className="font-medium text-zinc-700 capitalize">{(r.provider || r._provider || "—").replace(/_/g, " ")}</span>
              {r.records_processed !== undefined && <span className="text-zinc-500">{r.records_processed} records</span>}
              {r.mock_mode && <span className="text-amber-600">mock</span>}
              {r.error && <span className="text-red-500 truncate max-w-xs">{r.error}</span>}
              <span className="ml-auto text-zinc-400">{fmt(r._ts)}</span>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Sync History Section ─────────────────────────────────────────────────────

function SyncHistorySection({ token }: { token: string }) {
  const [history, setHistory] = useState<any[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    getSyncStatus(token, filter || undefined).then((d) => setHistory(Array.isArray(d) ? d : [])).catch(() => {});
  }, [token, filter]);

  return (
    <SectionCard title="Synchronization History" icon={Database} accent="purple">
      <div className="flex items-center gap-3 mb-4">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}
          className="text-sm border border-zinc-200 rounded-lg px-3 py-1.5 bg-white text-zinc-700 outline-none">
          <option value="">All Providers</option>
          {PROVIDERS.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-zinc-500 border-b border-zinc-100">
              <th className="pb-2 pr-4">Provider</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Processed</th>
              <th className="pb-2 pr-4">Added</th>
              <th className="pb-2 pr-4">Failed</th>
              <th className="pb-2">Started</th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 && (
              <tr><td colSpan={7} className="py-6 text-center text-zinc-400">No sync history available.</td></tr>
            )}
            {history.map((h) => (
              <tr key={h.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                <td className="py-2 pr-4 font-medium capitalize">{h.provider.replace(/_/g, " ")}</td>
                <td className="py-2 pr-4 capitalize">{h.sync_type}</td>
                <td className="py-2 pr-4"><span className={statusBadge(h.status)}>{h.status}</span></td>
                <td className="py-2 pr-4 text-zinc-600">{h.records_processed}</td>
                <td className="py-2 pr-4 text-emerald-700">{h.records_added}</td>
                <td className="py-2 pr-4 text-red-600">{h.records_failed}</td>
                <td className="py-2 text-zinc-500">{fmt(h.started_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ─── Notification Templates Section ──────────────────────────────────────────

function NotificationTemplatesSection({ token }: { token: string }) {
  const [templates, setTemplates] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", event_type: "", channel: "email", subject: "", body: "", active: true });

  const load = useCallback(() => {
    getNotificationTemplates(token).then((d) => setTemplates(Array.isArray(d) ? d : [])).catch(() => {});
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await createNotificationTemplate(token, { ...form, variables: [] });
      setShowForm(false);
      setForm({ name: "", event_type: "", channel: "email", subject: "", body: "", active: true });
      load();
    } catch {}
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this template?")) return;
    await deleteNotificationTemplate(token, id);
    load();
  };

  return (
    <SectionCard title="Notification Templates" icon={Bell} accent="amber">
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition">
          <Plus className="h-3.5 w-3.5" /> New Template
        </button>
      </div>
      {showForm && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Template name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <input placeholder="Event type (e.g. customer.approved)" value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <input placeholder="Subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none bg-white">
              {["email", "slack", "teams", "in_app"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <textarea placeholder="Body (use {{variable_name}} placeholders)" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
            rows={4} className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none resize-none" />
          <div className="flex gap-2">
            <button onClick={save} className="px-4 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition">Save</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 text-xs bg-zinc-200 text-zinc-700 rounded-lg hover:bg-zinc-300 transition">Cancel</button>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {templates.length === 0 && <p className="text-sm text-zinc-400 text-center py-4">No templates configured.</p>}
        {templates.map((t) => (
          <div key={t.id} className="flex items-center justify-between p-3 bg-zinc-50 rounded-xl border border-zinc-100">
            <div>
              <p className="text-sm font-medium text-zinc-800">{t.name}</p>
              <p className="text-xs text-zinc-500">{t.event_type} · {t.channel} · {t.active ? "Active" : "Inactive"}</p>
            </div>
            <button onClick={() => remove(t.id)} className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ─── Notification History Section ─────────────────────────────────────────────

function NotificationLogsSection({ token }: { token: string }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    getNotificationHistory(token, channel || undefined, status || undefined)
      .then((d) => setLogs(Array.isArray(d) ? d : [])).catch(() => {});
  }, [token, channel, status]);

  return (
    <SectionCard title="Notification Logs" icon={Activity} accent="rose">
      <div className="flex items-center gap-3 mb-4">
        <select value={channel} onChange={(e) => setChannel(e.target.value)}
          className="text-sm border border-zinc-200 rounded-lg px-3 py-1.5 bg-white text-zinc-700 outline-none">
          <option value="">All Channels</option>
          {["email", "slack", "teams", "in_app"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="text-sm border border-zinc-200 rounded-lg px-3 py-1.5 bg-white text-zinc-700 outline-none">
          <option value="">All Status</option>
          {["sent", "failed", "pending", "retry"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto max-h-72 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left text-zinc-500 border-b border-zinc-100">
              <th className="pb-2 pr-4">Title</th>
              <th className="pb-2 pr-4">Channel</th>
              <th className="pb-2 pr-4">Priority</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Retries</th>
              <th className="pb-2">Sent At</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-zinc-400">No notification logs.</td></tr>}
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                <td className="py-2 pr-4 font-medium text-zinc-800 max-w-xs truncate">{l.title}</td>
                <td className="py-2 pr-4 capitalize">{l.channel}</td>
                <td className="py-2 pr-4 capitalize">{l.priority}</td>
                <td className="py-2 pr-4"><span className={statusBadge(l.status)}>{l.status}</span></td>
                <td className="py-2 pr-4 text-zinc-500">{l.retry_count}</td>
                <td className="py-2 text-zinc-500">{fmt(l.sent_at || l.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ─── Webhooks Section ─────────────────────────────────────────────────────────

function WebhookSection({ token }: { token: string }) {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", secret: "", events: [] as string[], retries: 3, enabled: true });
  const [testingId, setTestingId] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [allEvents, setAllEvents] = useState<string[]>([]);

  const load = useCallback(async () => {
    const [eps, wlogs, evts] = await Promise.allSettled([
      getWebhooks(token),
      getAllWebhookLogs(token),
      getWebhookEvents(token),
    ]);
    if (eps.status === "fulfilled") setEndpoints(Array.isArray(eps.value) ? eps.value : []);
    if (wlogs.status === "fulfilled") setLogs(Array.isArray(wlogs.value) ? wlogs.value : []);
    if (evts.status === "fulfilled") setAllEvents((evts.value as any)?.events ?? []);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await createWebhook(token, form);
      setShowForm(false);
      setForm({ name: "", url: "", secret: "", events: [], retries: 3, enabled: true });
      load();
    } catch {}
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this webhook?")) return;
    await deleteWebhook(token, id);
    load();
  };

  const test = async (id: string) => {
    setTestingId(id);
    try { await testWebhook(token, id); } catch {}
    setTimeout(() => { setTestingId(null); load(); }, 1500);
  };

  const toggleEvent = (evt: string) => {
    setForm((prev) => ({
      ...prev,
      events: prev.events.includes(evt) ? prev.events.filter((e) => e !== evt) : [...prev.events, evt],
    }));
  };

  return (
    <SectionCard title="Webhook Endpoints" icon={Webhook} accent="purple">
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition">
          <Plus className="h-3.5 w-3.5" /> Register Webhook
        </button>
      </div>

      {showForm && (
        <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Endpoint name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <input placeholder="Target URL (https://...)" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <div className="relative">
              <input placeholder="Signing secret" type={showSecret ? "text" : "password"} value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 pr-10 outline-none" />
              <button onClick={() => setShowSecret(!showSecret)}
                className="absolute right-3 top-2.5 text-zinc-400 hover:text-zinc-600">
                {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <input type="number" placeholder="Max retries" min={0} max={10} value={form.retries}
              onChange={(e) => setForm({ ...form, retries: parseInt(e.target.value) })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
          </div>
          <div>
            <p className="text-xs font-medium text-zinc-600 mb-2">Subscribe to events:</p>
            <div className="flex flex-wrap gap-1.5">
              {allEvents.map((evt) => (
                <button key={evt} onClick={() => toggleEvent(evt)}
                  className={`text-xs px-2 py-1 rounded-md border transition ${form.events.includes(evt) ? "bg-purple-600 text-white border-purple-600" : "bg-white text-zinc-600 border-zinc-200 hover:border-purple-400"}`}>
                  {evt}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="px-4 py-1.5 text-xs bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition">Register</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 text-xs bg-zinc-200 text-zinc-700 rounded-lg hover:bg-zinc-300 transition">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-3 mb-6">
        {endpoints.length === 0 && <p className="text-sm text-zinc-400 text-center py-3">No webhook endpoints registered.</p>}
        {endpoints.map((ep) => (
          <div key={ep.id} className="p-4 bg-zinc-50 rounded-xl border border-zinc-100">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="text-sm font-semibold text-zinc-800">{ep.name}</p>
                <p className="text-xs text-zinc-500 font-mono break-all">{ep.url}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={statusBadge(ep.enabled ? "success" : "failed")}>{ep.enabled ? "Active" : "Disabled"}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1 mb-3">
              {(ep.events || []).map((evt: string) => (
                <span key={evt} className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">{evt}</span>
              ))}
              {(!ep.events || ep.events.length === 0) && <span className="text-xs text-zinc-400">All events</span>}
            </div>
            <div className="flex gap-2">
              <button onClick={() => test(ep.id)} disabled={testingId === ep.id}
                className="flex items-center gap-1 px-2.5 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
                {testingId === ep.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
                Test
              </button>
              <button onClick={() => remove(ep.id)} className="flex items-center gap-1 px-2.5 py-1 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition border border-red-200">
                <Trash2 className="h-3 w-3" /> Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Webhook Logs */}
      <h3 className="text-xs font-semibold text-zinc-600 mb-3 uppercase tracking-wide">Recent Webhook Logs</h3>
      <div className="overflow-x-auto max-h-56 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left text-zinc-500 border-b border-zinc-100">
              <th className="pb-2 pr-4">Event</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">HTTP</th>
              <th className="pb-2 pr-4">Retries</th>
              <th className="pb-2">Time</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-zinc-400">No webhook activity yet.</td></tr>}
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                <td className="py-2 pr-4 font-mono text-zinc-700">{l.event}</td>
                <td className="py-2 pr-4"><span className={statusBadge(l.status)}>{l.status}</span></td>
                <td className="py-2 pr-4 text-zinc-500">{l.response_code ?? "—"}</td>
                <td className="py-2 pr-4 text-zinc-500">{l.retry_count}</td>
                <td className="py-2 text-zinc-500">{fmt(l.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ─── Integration Settings Section ────────────────────────────────────────────

function IntegrationSettingsSection({ token }: { token: string }) {
  const [settings, setSettings] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    provider_name: "", provider_type: "sanctions", base_url: "", api_key: "", api_secret: "", enabled: true, timeout: 30, configuration: {}
  });

  const load = useCallback(() => {
    getIntegrationSettings(token).then((d) => setSettings(Array.isArray(d) ? d : [])).catch(() => {});
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await createIntegrationSetting(token, form);
      setShowForm(false);
      setForm({ provider_name: "", provider_type: "sanctions", base_url: "", api_key: "", api_secret: "", enabled: true, timeout: 30, configuration: {} });
      load();
    } catch {}
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this setting?")) return;
    await deleteIntegrationSetting(token, id);
    load();
  };

  return (
    <SectionCard title="Provider Settings" icon={Settings} accent="teal">
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition">
          <Plus className="h-3.5 w-3.5" /> Add Provider
        </button>
      </div>
      {showForm && (
        <div className="mb-6 p-4 bg-teal-50 border border-teal-200 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Provider name (e.g. opensanctions)" value={form.provider_name}
              onChange={(e) => setForm({ ...form, provider_name: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <select value={form.provider_type} onChange={(e) => setForm({ ...form, provider_type: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none bg-white">
              {["sanctions", "pep", "company", "notification"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input placeholder="Base URL" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
            <input placeholder="API Key" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              className="text-sm border border-zinc-200 rounded-lg px-3 py-2 outline-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="px-4 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition">Save</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 text-xs bg-zinc-200 text-zinc-700 rounded-lg hover:bg-zinc-300 transition">Cancel</button>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {settings.length === 0 && <p className="text-sm text-zinc-400 text-center py-4">No custom provider settings. Providers run in mock mode by default.</p>}
        {settings.map((s) => (
          <div key={s.id} className="flex items-center justify-between p-3 bg-zinc-50 rounded-xl border border-zinc-100">
            <div>
              <p className="text-sm font-medium text-zinc-800 capitalize">{s.provider_name.replace(/_/g, " ")}</p>
              <p className="text-xs text-zinc-500">{s.provider_type} · {s.base_url || "No URL"} · {s.enabled ? "Enabled" : "Disabled"}</p>
            </div>
            <button onClick={() => remove(s.id)} className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"providers" | "notifications" | "webhooks">("providers");

  if (!token) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-zinc-900 to-zinc-800 text-white px-8 py-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-teal-500/20 rounded-xl">
              <Webhook className="h-6 w-6 text-teal-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Integrations & Alert Center</h1>
              <p className="text-sm text-zinc-400">External compliance providers, notifications & webhooks</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white border-b border-zinc-200 px-8">
        <div className="max-w-7xl mx-auto flex gap-1">
          {([
            { id: "providers", label: "Compliance Providers", icon: Globe },
            { id: "notifications", label: "Notifications", icon: Bell },
            { id: "webhooks", label: "Webhooks", icon: Webhook },
          ] as const).map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3.5 text-sm font-medium border-b-2 transition ${
                activeTab === id ? "border-teal-600 text-teal-700" : "border-transparent text-zinc-500 hover:text-zinc-700"
              }`}>
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-8 py-8 space-y-8">
        {activeTab === "providers" && (
          <>
            <ProviderHealthSection token={token} />
            <ManualSyncSection token={token} />
            <SyncHistorySection token={token} />
            <IntegrationSettingsSection token={token} />
          </>
        )}
        {activeTab === "notifications" && (
          <>
            <NotificationTemplatesSection token={token} />
            <NotificationLogsSection token={token} />
          </>
        )}
        {activeTab === "webhooks" && (
          <WebhookSection token={token} />
        )}
      </div>
    </div>
  );
}
