"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { getDevOpsStatus } from "@/lib/api";
import type { DevOpsStatusReport, DevOpsPodInfo } from "@/lib/types";
import {
  Server, Cpu, Database, Zap, RefreshCw, Layers, CheckCircle2,
  XCircle, AlertTriangle, ShieldCheck, Terminal, Compass, BarChart3, Clock
} from "lucide-react";

const statusBadgeClass = (status: string) => {
  const s = status.toLowerCase();
  if (s === "healthy" || s === "running" || s === "online" || s === "success") {
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  }
  if (s === "pending" || s === "unconfigured" || s === "warning") {
    return "bg-amber-100 text-amber-800 border-amber-200";
  }
  return "bg-rose-100 text-rose-800 border-rose-200";
};

export default function DevOpsDashboardPage() {
  const { token } = useAuth();
  const [data, setData] = useState<DevOpsStatusReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSubTab, setActiveSubTab] = useState<"k8s" | "db_cache" | "celery" | "system">("k8s");

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setErrorMsg("");
      const res = await getDevOpsStatus(token);
      setData(res);
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to fetch production infrastructure metrics.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-teal-600" />
        <span className="ml-3 text-sm text-zinc-600 font-semibold">Loading DevOps metrics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Premium Sub-Header */}
      <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-800 text-white p-6 rounded-2xl shadow-sm border border-zinc-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-teal-500/10 rounded-xl border border-teal-500/20">
              <Server className="h-6 w-6 text-teal-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">DevOps & Production Infrastructure</h1>
              <p className="text-xs text-zinc-400">Kubernetes namespaces, database replication pools, Redis Sentinel clustering & background task queues</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs bg-zinc-800/50 p-2.5 rounded-xl border border-zinc-700/50 font-mono">
            <div>Version: <span className="text-teal-400 font-bold">{data?.deployment_version}</span></div>
            <div className="text-zinc-600">|</div>
            <div>Commit: <span className="text-teal-400">{data?.git_commit}</span></div>
            <div className="text-zinc-600">|</div>
            <div>Uptime: <span className="text-teal-400 font-bold">{data?.uptime}</span></div>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm">
          <AlertTriangle className="h-4.5 w-4.5 text-rose-500 shrink-0" />
          <p className="font-semibold">{errorMsg}</p>
        </div>
      )}

      {/* DevOps Sub-Tabs Navigation */}
      <div className="flex border-b border-zinc-200 bg-white p-1 rounded-xl border">
        {([
          { id: "k8s", label: "Kubernetes Cluster", icon: Layers },
          { id: "db_cache", label: "Databases & Caches", icon: Database },
          { id: "celery", label: "Celery Workers & Queues", icon: Zap },
          { id: "system", label: "Core Resource Monitors", icon: Cpu },
        ] as const).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveSubTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold transition-all ${
              activeSubTab === id
                ? "bg-zinc-900 text-white shadow-sm"
                : "text-zinc-500 hover:text-zinc-800 hover:bg-zinc-50"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Sub-Tab 1: Kubernetes Cluster */}
      {activeSubTab === "k8s" && data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Cluster General Config info */}
            <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <Compass className="h-4 w-4 text-zinc-400" /> Namespace Details
              </h3>
              <div className="space-y-3 font-medium text-xs text-zinc-700">
                <div className="flex justify-between border-b pb-2">
                  <span>Namespace:</span>
                  <span className="font-mono text-zinc-900">{data.kubernetes_namespace}</span>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span>Image Registry Tag:</span>
                  <span className="font-mono text-teal-600 font-bold">{data.docker_image_version}</span>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span>Total Active Pods:</span>
                  <span className="font-bold text-zinc-900">{data.pods_count}</span>
                </div>
                <div className="flex justify-between">
                  <span>Restart Count:</span>
                  <span className={`font-bold ${data.restart_count > 0 ? "text-rose-600" : "text-emerald-600"}`}>
                    {data.restart_count}
                  </span>
                </div>
              </div>
            </div>

            {/* Performance Stats */}
            <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-4 lg:col-span-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <BarChart3 className="h-4 w-4 text-zinc-400" /> Screening Scale Indicators
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-zinc-50 p-4 rounded-lg border border-zinc-150">
                  <p className="text-[10px] uppercase font-bold text-zinc-500">Active Users (1h)</p>
                  <p className="text-2xl font-bold text-zinc-800 mt-1">{data.active_users}</p>
                </div>
                <div className="bg-zinc-50 p-4 rounded-lg border border-zinc-150">
                  <p className="text-[10px] uppercase font-bold text-zinc-500">Avg screening latency</p>
                  <p className="text-2xl font-bold text-zinc-800 mt-1">{data.average_screening_time_sec}s</p>
                </div>
                <div className="bg-zinc-50 p-4 rounded-lg border border-zinc-150">
                  <p className="text-[10px] uppercase font-bold text-zinc-500">Resource quotas</p>
                  <p className="text-2xl font-bold text-emerald-600 mt-1">Gated / OK</p>
                </div>
              </div>
            </div>
          </div>

          {/* Kubernetes Pods List */}
          <div className="bg-white rounded-xl border border-zinc-200 p-6">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-4 flex items-center gap-1.5">
              <Terminal className="h-4.5 w-4.5 text-zinc-400" /> Kubernetes Pod Instances List
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="text-zinc-500 border-b border-zinc-200">
                    <th className="pb-3 pr-4 font-bold uppercase">Pod Name</th>
                    <th className="pb-3 pr-4 font-bold uppercase">IP Address</th>
                    <th className="pb-3 pr-4 font-bold uppercase">CPU</th>
                    <th className="pb-3 pr-4 font-bold uppercase">Memory</th>
                    <th className="pb-3 pr-4 font-bold uppercase">Status</th>
                    <th className="pb-3 pr-4 font-bold uppercase text-center">Restarts</th>
                    <th className="pb-3 font-bold uppercase">Age</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pods.map((pod, idx) => (
                    <tr key={idx} className="border-b border-zinc-100 hover:bg-zinc-50">
                      <td className="py-3 pr-4 font-mono font-bold text-zinc-800">{pod.name}</td>
                      <td className="py-3 pr-4 font-mono text-zinc-500">{pod.ip}</td>
                      <td className="py-3 pr-4 text-zinc-700 font-semibold">{pod.cpu} Cores</td>
                      <td className="py-3 pr-4 text-zinc-700 font-semibold">{pod.memory}</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusBadgeClass(pod.status)}`}>
                          {pod.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-center font-bold text-zinc-800">{pod.restarts}</td>
                      <td className="py-3 text-zinc-500 font-medium">{pod.age}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 2: Databases & Caches */}
      {activeSubTab === "db_cache" && data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* PostgreSQL Primary & Replica */}
          <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-5">
            <h3 className="text-sm font-bold text-zinc-800 border-b pb-3 flex items-center gap-1.5">
              <Database className="h-4.5 w-4.5 text-teal-600" /> PostgreSQL Primary & Replica Details
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-zinc-50 rounded-lg border border-zinc-150">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Primary Node</span>
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                </div>
                <p className="text-lg font-bold text-zinc-800 mt-2 capitalize">{data.database.primary_status}</p>
                <p className="text-xs text-zinc-400 mt-1">Latency: {data.database.primary_latency_ms} ms</p>
              </div>
              <div className="p-4 bg-zinc-50 rounded-lg border border-zinc-150">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-500 uppercase">Read Replica</span>
                  {data.database.replica_status === "healthy" ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                  )}
                </div>
                <p className="text-lg font-bold text-zinc-800 mt-2 capitalize">{data.database.replica_status}</p>
                <p className="text-xs text-zinc-400 mt-1">Latency: {data.database.replica_latency_ms} ms</p>
              </div>
            </div>

            <div className="p-4 bg-teal-50/20 border border-teal-100 rounded-lg">
              <div className="flex justify-between text-xs text-zinc-700 font-bold mb-2">
                <span>Database Replication Lag:</span>
                <span className="font-mono text-teal-700">{data.database.replica_lag_ms} ms</span>
              </div>
              <p className="text-[10px] text-zinc-500 leading-relaxed">
                Primary-to-Replica data replication is configured with active transaction pipeline sync. Read queries for BI and dashboards are routed to replica engine.
              </p>
            </div>

            {/* Connection Pools */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase text-zinc-400">Connection Pool Metrics</h4>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] text-zinc-600 mb-1">
                    <span>Primary Pool Utilization ({data.database.pool_metrics.primary.checked_out} / {data.database.pool_metrics.primary.pool_size})</span>
                    <span className="font-bold">
                      {data.database.pool_metrics.primary.pool_size > 0 
                        ? Math.round((data.database.pool_metrics.primary.checked_out / data.database.pool_metrics.primary.pool_size) * 100)
                        : 0}%
                    </span>
                  </div>
                  <div className="w-full bg-zinc-100 h-1.5 rounded-full">
                    <div className="bg-teal-600 h-1.5 rounded-full" style={{
                      width: `${data.database.pool_metrics.primary.pool_size > 0 
                        ? (data.database.pool_metrics.primary.checked_out / data.database.pool_metrics.primary.pool_size) * 100
                        : 0}%`
                    }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] text-zinc-600 mb-1">
                    <span>Replica Pool Utilization ({data.database.pool_metrics.replica.checked_out} / {data.database.pool_metrics.replica.pool_size})</span>
                    <span className="font-bold">
                      {data.database.pool_metrics.replica.pool_size > 0 
                        ? Math.round((data.database.pool_metrics.replica.checked_out / data.database.pool_metrics.replica.pool_size) * 100)
                        : 0}%
                    </span>
                  </div>
                  <div className="w-full bg-zinc-100 h-1.5 rounded-full">
                    <div className="bg-blue-600 h-1.5 rounded-full" style={{
                      width: `${data.database.pool_metrics.replica.pool_size > 0 
                        ? (data.database.pool_metrics.replica.checked_out / data.database.pool_metrics.replica.pool_size) * 100
                        : 0}%`
                    }}></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Redis Sentinel & Cache Status */}
          <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-5">
            <h3 className="text-sm font-bold text-zinc-800 border-b pb-3 flex items-center gap-1.5">
              <Zap className="h-4.5 w-4.5 text-amber-500" /> Redis Cluster & Sentinel Caches
            </h3>
            <div className="space-y-4 text-xs font-semibold text-zinc-700">
              <div className="flex justify-between border-b pb-2">
                <span>Cluster State:</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusBadgeClass(data.redis.status)}`}>
                  {data.redis.status.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Connection Ping Latency:</span>
                <span className="font-mono text-zinc-900">{data.redis.latency_ms} ms</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Sentinel Mode Active:</span>
                <span className="font-bold text-teal-600">{data.redis.sentinel_active ? "ENABLED" : "DISABLED"}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Cluster Mode Active:</span>
                <span className="font-bold text-teal-600">{data.redis.cluster_active ? "ENABLED" : "DISABLED"}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Sentinel Service Name:</span>
                <span className="font-mono text-zinc-900">{data.redis.sentinel_service_name}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Connected Cache Clients:</span>
                <span className="font-bold text-zinc-900">{data.redis.connected_clients} clients</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Cache Hits Ratio:</span>
                <span className="font-bold text-teal-600">{data.redis.cache_hit_rate}%</span>
              </div>
              <div className="flex justify-between">
                <span>Total Keys Tracked:</span>
                <span className="font-mono text-zinc-900">{data.redis.keys_count} keys</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 3: Celery Workers & Queues */}
      {activeSubTab === "celery" && data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
              <p className="text-[10px] font-bold text-zinc-400 uppercase">Queue Depth Length</p>
              <p className="text-2xl font-bold text-zinc-800 mt-1">{data.celery.queue_length}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
              <p className="text-[10px] font-bold text-zinc-400 uppercase">Active Workers Online</p>
              <p className="text-2xl font-bold text-zinc-800 mt-1">{data.celery.active_workers_count}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
              <p className="text-[10px] font-bold text-zinc-400 uppercase">Active Tasks Processing</p>
              <p className="text-2xl font-bold text-zinc-800 mt-1">{data.celery.active_tasks_count}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-zinc-200 shadow-xs">
              <p className="text-[10px] font-bold text-zinc-400 uppercase">Autoscaling State</p>
              <p className="text-2xl font-bold text-teal-600 mt-1">ACTIVE</p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl border border-zinc-200">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-4">
              Registered Worker Daemons
            </h3>
            <div className="space-y-2">
              {data.celery.active_workers.map((worker, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-zinc-50 border rounded-lg hover:bg-zinc-100 transition-colors">
                  <span className="font-mono text-xs font-bold text-zinc-700">{worker}</span>
                  <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-full">
                    ONLINE
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 4: Core Resource Monitors */}
      {activeSubTab === "system" && data && (
        <div className="bg-white p-6 rounded-xl border border-zinc-200 space-y-6">
          <h3 className="text-sm font-bold text-zinc-800 border-b pb-3 flex items-center gap-1.5">
            <Cpu className="h-4.5 w-4.5 text-zinc-500" /> Host System Resource Monitors
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <div className="flex justify-between text-xs text-zinc-600 mb-1">
                <span>Host CPU Usage</span>
                <span className="font-bold">{data.system.cpu_percent}%</span>
              </div>
              <div className="w-full bg-zinc-100 h-2.5 rounded-full">
                <div className="bg-teal-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${data.system.cpu_percent}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-zinc-600 mb-1">
                <span>Virtual Memory ({data.system.memory_used_mb}MB / {data.system.memory_total_mb}MB)</span>
                <span className="font-bold">{data.system.memory_percent}%</span>
              </div>
              <div className="w-full bg-zinc-100 h-2.5 rounded-full">
                <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${data.system.memory_percent}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-zinc-600 mb-1">
                <span>Disk Partition Volume ({data.system.disk_used_gb}GB / {data.system.disk_total_gb}GB)</span>
                <span className="font-bold">{data.system.disk_percent}%</span>
              </div>
              <div className="w-full bg-zinc-100 h-2.5 rounded-full">
                <div className="bg-purple-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${data.system.disk_percent}%` }}></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
