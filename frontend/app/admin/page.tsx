"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  getDashboardOverview,
  getDashboardCharts,
  getDashboardActivity,
  getDashboardRisk,
  getDashboardAlerts,
  getDashboardCases,
  getDashboardMonitoring,
  getDashboardAI,
  searchDashboard,
  runScreening,
} from "@/lib/api";
import {
  Users,
  Shield,
  AlertTriangle,
  Briefcase,
  ArrowUpDown,
  RefreshCw,
  Search,
  Zap,
  TrendingUp,
  Activity,
  UserCheck,
  Clock,
  CheckCircle,
  XCircle,
  FileCheck,
  Upload,
  Calendar,
  AlertCircle,
  Bot,
  Sliders,
  DollarSign,
  Globe,
  FileText,
  HelpCircle,
  Inbox,
  Sparkles,
  BookOpen,
} from "lucide-react";
import Link from "next/link";

// ─── Custom SVG Chart Components ─────────────────────────────────────────────

interface PieChartData {
  label: string;
  value: number;
  color: string;
}

function SvgPieChart({ data }: { data: PieChartData[] }) {
  const total = data.reduce((acc, curr) => acc + curr.value, 0);
  if (total === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-zinc-400">
        No distribution data
      </div>
    );
  }

  let accumulatedAngle = 0;
  return (
    <div className="flex flex-col items-center justify-center">
      <svg width="150" height="150" viewBox="0 0 32 32" className="transform -rotate-90">
        {data.map((slice, i) => {
          if (slice.value === 0) return null;
          const percentage = (slice.value / total) * 100;
          const strokeDasharray = `${percentage} ${100 - percentage}`;
          const strokeDashoffset = 100 - accumulatedAngle;
          accumulatedAngle += percentage;

          return (
            <circle
              key={i}
              cx="16"
              cy="16"
              r="15.91549430918954"
              fill="transparent"
              stroke={slice.color}
              strokeWidth="3.2"
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
            />
          );
        })}
      </svg>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        {data.map((slice, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
            <span className="text-zinc-600 dark:text-zinc-400 capitalize">{slice.label}</span>
            <span className="font-bold text-zinc-900 dark:text-zinc-200">({slice.value})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface BarChartData {
  label: string;
  value: number;
}

function SvgBarChart({ data, color = "bg-teal-600" }: { data: BarChartData[]; color?: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="space-y-2">
      {data.map((item, i) => {
        const pct = (item.value / max) * 100;
        return (
          <div key={i} className="flex items-center gap-3">
            <span className="w-24 truncate text-xs text-zinc-500 text-right" title={item.label}>
              {item.label}
            </span>
            <div className="flex-1 h-3.5 bg-zinc-100 dark:bg-zinc-800 rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${color}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-8 text-xs font-bold text-zinc-700 dark:text-zinc-300 text-left">
              {item.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface LineChartData {
  label: string;
  value: number;
}

function SvgLineChart({ data, height = 120, strokeColor = "#0d9488", fillColor = "rgba(13, 148, 136, 0.1)" }: { data: LineChartData[]; height?: number; strokeColor?: string; fillColor?: string }) {
  if (data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-xs text-zinc-400">
        No history data
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min;

  const width = 500;
  const padding = 10;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;

  const points = data.map((item, i) => {
    const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
    const pctY = range === 0 ? 0.5 : (item.value - min) / range;
    const y = padding + chartHeight - pctY * chartHeight;
    return { x, y };
  });

  const pathD = points.reduce(
    (acc, p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`),
    ""
  );

  const areaD = points.length
    ? `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`
    : "";

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
        {/* Area fill */}
        {areaD && <path d={areaD} fill={fillColor} />}
        {/* Line stroke */}
        {pathD && <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
        {/* Points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="3"
            className="fill-teal-600 dark:fill-teal-400 stroke-white dark:stroke-zinc-900 stroke-2 hover:r-5 cursor-pointer"
          />
        ))}
      </svg>
      <div className="flex justify-between text-[9px] text-zinc-400 mt-2 px-1">
        <span>{data[0]?.label}</span>
        <span>{data[data.length - 1]?.label}</span>
      </div>
    </div>
  );
}

// ─── Dashboard Component ─────────────────────────────────────────────────────

export default function AdminDashboard() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState("overview");

  // Overview stats
  const [overview, setOverview] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [activity, setActivity] = useState<any[]>([]);
  const [highRisk, setHighRisk] = useState<any[]>([]);
  const [alertsSummary, setAlertsSummary] = useState<any>(null);
  const [casesSummary, setCasesSummary] = useState<any>(null);
  const [monitoringSummary, setMonitoringSummary] = useState<any>(null);
  const [aiSummary, setAiSummary] = useState<any>(null);

  // States
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rescreeningId, setRescreeningId] = useState<string | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any>(null);
  const [searching, setSearching] = useState(false);

  // Fetch all dashboard sections
  const fetchAllData = useCallback(async () => {
    if (!token) return;
    try {
      const [
        overviewData,
        chartsData,
        activityData,
        highRiskData,
        alertsData,
        casesData,
        monitoringData,
        aiData,
      ] = await Promise.all([
        getDashboardOverview(token),
        getDashboardCharts(token),
        getDashboardActivity(token),
        getDashboardRisk(token),
        getDashboardAlerts(token),
        getDashboardCases(token),
        getDashboardMonitoring(token),
        getDashboardAI(token),
      ]);

      setOverview(overviewData);
      setCharts(chartsData);
      setActivity(activityData);
      setHighRisk(highRiskData);
      setAlertsSummary(alertsData);
      setCasesSummary(casesData);
      setMonitoringSummary(monitoringData);
      setAiSummary(aiData);
    } catch (err) {
      console.error("Dashboard aggregation failed", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAllData();
    // Auto refresh feed every 30 seconds
    const interval = setInterval(fetchAllData, 30000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  // Handle manual rescreening from the high risk widget
  const handleRescreen = async (customerId: string) => {
    if (!token) return;
    setRescreeningId(customerId);
    try {
      await runScreening(customerId, token);
      fetchAllData();
    } catch (err) {
      console.error(err);
    } finally {
      setRescreeningId(null);
    }
  };

  // Search dashboard callback
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      const results = await searchDashboard(token, searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-1/4 bg-zinc-200 dark:bg-zinc-800 rounded animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-24 bg-zinc-200 dark:bg-zinc-800 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 h-64 bg-zinc-200 dark:bg-zinc-800 rounded-xl animate-pulse" />
          <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  // Pre-configured tab metadata
  const tabs = [
    { id: "overview", label: "Overview", icon: Sliders },
    { id: "alerts_cases", label: "Alerts & Cases", icon: AlertTriangle },
    { id: "monitoring", label: "Monitoring Schedule", icon: Calendar },
    { id: "ai_hub", label: "AI Decision Hub", icon: Bot },
    { id: "activity", label: "Audit Activity", icon: Activity },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-zinc-800 dark:text-zinc-200">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-zinc-950 dark:text-white flex items-center gap-2">
            <Sparkles className="text-teal-600 h-7 w-7" /> Compliance Operations Console
          </h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mt-1">
            Real-time KYC · AML transaction intelligence & audit dashboard
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Quick refresh */}
          <button
            onClick={() => {
              setRefreshing(true);
              fetchAllData();
            }}
            className="flex items-center gap-1 px-3 py-2 text-xs font-bold rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Global Search Bar */}
      <form onSubmit={handleSearch} className="relative flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-zinc-400" />
          <input
            type="text"
            placeholder="Global search by customer ID, name, transaction reference, case details..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (!e.target.value) setSearchResults(null);
            }}
            className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 pl-10 pr-4 py-2.5 text-sm placeholder:text-zinc-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </div>
        <button
          type="submit"
          className="rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-teal-700 transition"
        >
          {searching ? "Searching..." : "Search"}
        </button>
        {searchResults && (
          <button
            type="button"
            onClick={clearSearch}
            className="rounded-xl border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 text-sm text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition"
          >
            Clear
          </button>
        )}
      </form>

      {/* Search results drawer */}
      {searchResults && (
        <div className="rounded-xl border border-teal-200 bg-teal-50/30 dark:bg-teal-950/10 p-5 space-y-4">
          <h3 className="text-sm font-bold text-teal-800 dark:text-teal-400 uppercase tracking-widest">
            Search Results
          </h3>
          <div className="grid grid-cols-4 gap-4">
            {/* Customers */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-zinc-400 uppercase">Customers ({searchResults.customers.length})</h4>
              {searchResults.customers.length === 0 ? (
                <p className="text-xs text-zinc-400">No match</p>
              ) : (
                searchResults.customers.map((c: any) => (
                  <Link
                    key={c.id}
                    href={c.url}
                    className="block p-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:border-teal-400 transition"
                  >
                    <p className="font-bold text-zinc-800 dark:text-zinc-200">{c.name}</p>
                    <span className="text-[10px] text-zinc-400 capitalize">{c.type} · {c.status}</span>
                  </Link>
                ))
              )}
            </div>

            {/* Cases */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-zinc-400 uppercase">Cases ({searchResults.cases.length})</h4>
              {searchResults.cases.length === 0 ? (
                <p className="text-xs text-zinc-400">No match</p>
              ) : (
                searchResults.cases.map((c: any) => (
                  <Link
                    key={c.id}
                    href={c.url}
                    className="block p-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:border-teal-400 transition"
                  >
                    <p className="font-mono font-bold text-zinc-800 dark:text-zinc-200">#{c.id.slice(0, 8)}</p>
                    <span className="text-[10px] text-zinc-400 capitalize">{c.status} · Priority: {c.priority}</span>
                  </Link>
                ))
              )}
            </div>

            {/* Alerts */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-zinc-400 uppercase">Alerts ({searchResults.alerts.length})</h4>
              {searchResults.alerts.length === 0 ? (
                <p className="text-xs text-zinc-400">No match</p>
              ) : (
                searchResults.alerts.map((a: any) => (
                  <Link
                    key={a.id}
                    href={a.url}
                    className="block p-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:border-teal-400 transition"
                  >
                    <p className="font-semibold text-zinc-800 dark:text-zinc-200 truncate">{a.type.replace(/_/g, " ")}</p>
                    <span className="text-[10px] text-zinc-400 capitalize">Risk: {a.risk_score} · {a.status}</span>
                  </Link>
                ))
              )}
            </div>

            {/* Transactions */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-zinc-400 uppercase">Transactions ({searchResults.transactions.length})</h4>
              {searchResults.transactions.length === 0 ? (
                <p className="text-xs text-zinc-400">No match</p>
              ) : (
                searchResults.transactions.map((t: any) => (
                  <Link
                    key={t.id}
                    href={t.url}
                    className="block p-2 text-xs bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:border-teal-400 transition"
                  >
                    <p className="font-bold text-zinc-800 dark:text-zinc-200 truncate">{t.receiver}</p>
                    <span className="text-[10px] text-zinc-400 capitalize">
                      {t.currency} {t.amount} · {t.status}
                    </span>
                  </Link>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-zinc-200 dark:border-zinc-850 gap-1 overflow-x-auto pb-px">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold whitespace-nowrap transition ${
                isActive
                  ? "border-teal-600 text-teal-600"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:border-zinc-200 dark:hover:border-zinc-700"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Part 1: KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { label: "Total Customers", val: overview?.customers.total, icon: Users, col: "text-blue-600 bg-blue-50 dark:bg-blue-950/20" },
              { label: "Approved Customers", val: overview?.customers.approved, icon: UserCheck, col: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20" },
              { label: "Pending KYC", val: overview?.customers.pending_kyc, icon: Clock, col: "text-amber-600 bg-amber-50 dark:bg-amber-950/20" },
              { label: "High Risk Customers", val: overview?.risk.high, icon: Shield, col: "text-red-600 bg-red-50 dark:bg-red-950/20" },
              { label: "Total Alerts", val: overview?.alerts.total, icon: AlertTriangle, col: "text-red-500 bg-rose-50 dark:bg-rose-950/20" },
              { label: "Open Cases", val: overview?.cases.open, icon: Briefcase, col: "text-purple-600 bg-purple-50 dark:bg-purple-950/20" },
              { label: "Today Transactions", val: overview?.transactions.today, icon: ArrowUpDown, col: "text-teal-600 bg-teal-50 dark:bg-teal-950/20" },
              { label: "Average Risk Score", val: overview?.risk.average_score, icon: TrendingUp, col: "text-orange-600 bg-orange-50 dark:bg-orange-950/20" },
              { label: "AI Screenings Today", val: overview?.ai.screenings_today, icon: Bot, col: "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/20" },
              { label: "Total Regulations", val: overview?.regulations?.total, icon: FileText, col: "text-zinc-600 bg-zinc-50 dark:bg-zinc-950/20" },
              { label: "Active Regulations", val: overview?.regulations?.active, icon: BookOpen, col: "text-teal-600 bg-teal-50 dark:bg-teal-950/20" },
              { label: "Pending Regulations", val: overview?.regulations?.pending, icon: AlertCircle, col: "text-yellow-600 bg-yellow-50 dark:bg-yellow-950/20" },
              { label: "Executive Compliance Score", val: "98.5%", icon: Shield, col: "text-teal-600 bg-teal-50 dark:bg-teal-950/20" },
            ].map((kpi, idx) => {
              const Icon = kpi.icon;
              return (
                <div key={idx} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">
                      {kpi.label}
                    </p>
                    <div className={`p-1.5 rounded-lg ${kpi.col}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <p className="text-2xl font-black tracking-tight text-zinc-900 dark:text-white">
                    {kpi.val !== undefined ? kpi.val : "0"}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Part 9: Quick Actions Short-cuts */}
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
              Quick Actions Shortcuts
            </h3>
            <div className="flex items-center gap-3 flex-wrap">
              <Link
                href="/admin/documents"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <FileCheck className="h-4 w-4 text-emerald-600" />
                View Verification Desk
              </Link>
              <Link
                href="/admin/transactions"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <Upload className="h-4 w-4 text-teal-600" />
                Import CSV Transactions
              </Link>
              <Link
                href="/admin/alerts"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <AlertTriangle className="h-4 w-4 text-red-500" />
                Review Alerts
              </Link>
              <Link
                href="/admin/cases"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <Briefcase className="h-4 w-4 text-purple-600" />
                Case Files list
              </Link>
              <Link
                href="/admin/investigations"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <Briefcase className="h-4 w-4 text-indigo-600" />
                Investigations Workspace
              </Link>
              <Link
                href="/admin/regulations"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <FileText className="h-4 w-4 text-zinc-600" />
                Regulations Lib
              </Link>
              <Link
                href="/admin/policy-rules"
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-zinc-700 dark:text-zinc-200 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-zinc-50 transition"
              >
                <Sliders className="h-4 w-4 text-orange-600" />
                Policy Rules Console
              </Link>
            </div>
          </div>

          {/* Part 2: Charts Panel Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Chart 1: Customer Risk Pie */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                Customer Risk Distribution
              </h3>
              <div className="flex items-center justify-center min-h-[180px]">
                <SvgPieChart
                  data={[
                    { label: "High", value: charts?.risk_distribution.find((d: any) => d.tier === "high")?.count || 0, color: "#ef4444" },
                    { label: "Medium", value: charts?.risk_distribution.find((d: any) => d.tier === "medium")?.count || 0, color: "#f59e0b" },
                    { label: "Low", value: charts?.risk_distribution.find((d: any) => d.tier === "low")?.count || 0, color: "#10b981" },
                  ]}
                />
              </div>
            </div>

            {/* Chart 4: Transactions per Day */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                Daily Transaction Volume (Last 30 Days)
              </h3>
              <div className="pt-2">
                <SvgLineChart
                  data={(charts?.transactions_per_day || []).map((t: any) => ({
                    label: t.day.slice(5),
                    value: t.count,
                  }))}
                  strokeColor="#0284c7"
                  fillColor="rgba(2, 132, 199, 0.1)"
                />
              </div>
            </div>

            {/* Chart 6: Risk score trend */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                Average Customer Risk Trend
              </h3>
              <div className="pt-2">
                <SvgLineChart
                  data={(charts?.risk_score_trend || []).map((t: any) => ({
                    label: t.day.slice(5),
                    value: t.avg_score,
                  }))}
                  strokeColor="#ea580c"
                  fillColor="rgba(234, 88, 12, 0.1)"
                />
              </div>
            </div>
          </div>

          {/* Part 4 & 7 Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Widget: High Risk Customers */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                High Risk Customer Watchlist
              </h3>
              <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {highRisk.length === 0 ? (
                  <div className="py-6 text-center text-xs text-zinc-400">
                    No high risk customers found
                  </div>
                ) : (
                  highRisk.map((c) => (
                    <div key={c.customer_id} className="py-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-zinc-900 dark:text-white">{c.name}</p>
                        <p className="text-[10px] text-zinc-400 font-mono">{c.customer_id}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <span className="text-sm font-black text-red-600">{c.risk_score}</span>
                          <span className="text-[9px] block text-zinc-400 font-semibold uppercase">Risk Score</span>
                        </div>
                        <div className="flex gap-1.5">
                          {c.open_case ? (
                            <Link
                              href={`/admin/cases/${c.open_case.id}`}
                              className="px-2 py-1 text-[10px] font-bold bg-amber-50 dark:bg-amber-950/20 text-amber-700 rounded border border-amber-200 dark:border-amber-900 hover:bg-amber-100 transition"
                            >
                              Investigate
                            </Link>
                          ) : (
                            <button
                              onClick={() => handleRescreen(c.customer_id)}
                              disabled={rescreeningId === c.customer_id}
                              className="px-2 py-1 text-[10px] font-bold bg-teal-50 dark:bg-teal-950/20 text-teal-700 rounded border border-teal-200 dark:border-teal-900 hover:bg-teal-100 transition disabled:opacity-50"
                            >
                              {rescreeningId === c.customer_id ? "Running…" : "Rescreen"}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Chart 7: Destination Country Risk Table */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400 flex items-center justify-between">
                <span>Destination Country Distribution</span>
                <Globe className="h-4 w-4 text-zinc-400" />
              </h3>
              <div className="overflow-hidden rounded-lg border border-zinc-100 dark:border-zinc-800">
                <table className="min-w-full divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
                  <thead className="bg-zinc-50 dark:bg-zinc-900">
                    <tr>
                      <th className="px-3 py-2 text-left font-bold text-zinc-500">Destination</th>
                      <th className="px-3 py-2 text-right font-bold text-zinc-500">Transaction Count</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-850">
                    {(charts?.country_distribution || []).length === 0 ? (
                      <tr>
                        <td colSpan={2} className="px-3 py-4 text-center text-zinc-400">
                          No transactions country stats
                        </td>
                      </tr>
                    ) : (
                      charts?.country_distribution.map((c: any, idx: number) => (
                        <tr key={idx} className="hover:bg-zinc-50 dark:hover:bg-zinc-850">
                          <td className="px-3 py-2 font-semibold text-zinc-700 dark:text-zinc-300">
                            {c.country}
                          </td>
                          <td className="px-3 py-2 text-right font-bold text-zinc-900 dark:text-white">
                            {c.count}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Alerts & Cases */}
      {activeTab === "alerts_cases" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Part 5: Alerts summary */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                  AML Alerts Dashboard Summary
                </h3>
                <Link href="/admin/alerts" className="text-xs font-bold text-teal-600 hover:underline">
                  Go to Alert Desk →
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">Critical Alerts (Risk ≥ 90)</span>
                  <p className="text-xl font-bold text-red-600">
                    {alertsSummary?.by_risk_level.critical || 0}
                  </p>
                </div>
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">High Alerts (Risk 75-89)</span>
                  <p className="text-xl font-bold text-orange-500">
                    {alertsSummary?.by_risk_level.high || 0}
                  </p>
                </div>
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">Today New Alerts</span>
                  <p className="text-xl font-bold text-teal-600">
                    {alertsSummary?.time_periods.today || 0}
                  </p>
                </div>
                <div className="p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">This Week Alerts</span>
                  <p className="text-xl font-bold text-zinc-700 dark:text-zinc-300">
                    {alertsSummary?.time_periods.this_week || 0}
                  </p>
                </div>
              </div>

              {/* Chart 2: Alerts by Type */}
              <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <h4 className="text-xs font-bold text-zinc-400 uppercase mb-3">Top Alerts Triggered</h4>
                <SvgBarChart
                  data={(charts?.alerts_by_type || []).map((a: any) => ({
                    label: a.type.replace(/_/g, " "),
                    value: a.count,
                  }))}
                  color="bg-rose-500"
                />
              </div>
            </div>

            {/* Part 6: Cases summary */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                  AML Case Workload & Resolution Metrics
                </h3>
                <Link href="/admin/cases" className="text-xs font-bold text-teal-600 hover:underline">
                  Go to Case Files →
                </Link>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-zinc-50 dark:bg-zinc-900/50 rounded-lg text-center">
                  <span className="text-[9px] text-zinc-400 uppercase font-semibold">Open cases</span>
                  <p className="text-lg font-bold text-zinc-800 dark:text-zinc-200">{casesSummary?.open || 0}</p>
                </div>
                <div className="p-3 bg-zinc-50 dark:bg-zinc-900/50 rounded-lg text-center">
                  <span className="text-[9px] text-zinc-400 uppercase font-semibold">SAR Filed</span>
                  <p className="text-lg font-bold text-red-600">{casesSummary?.sar_filed || 0}</p>
                </div>
                <div className="p-3 bg-zinc-50 dark:bg-zinc-900/50 rounded-lg text-center">
                  <span className="text-[9px] text-zinc-400 uppercase font-semibold">Avg resolution</span>
                  <p className="text-lg font-bold text-zinc-800 dark:text-zinc-200">{casesSummary?.avg_resolution_hours || 0} hrs</p>
                </div>
              </div>

              {/* Chart 3: Cases by status */}
              <div className="pt-2">
                <h4 className="text-xs font-bold text-zinc-400 uppercase mb-3">Cases by status</h4>
                <SvgPieChart
                  data={[
                    { label: "Open", value: casesSummary?.by_status.open || 0, color: "#3b82f6" },
                    { label: "Investigating", value: casesSummary?.by_status.investigating || 0, color: "#6366f1" },
                    { label: "Under Review", value: casesSummary?.by_status.under_review || 0, color: "#f59e0b" },
                    { label: "Approved", value: casesSummary?.by_status.approved || 0, color: "#10b981" },
                    { label: "Rejected", value: casesSummary?.by_status.rejected || 0, color: "#ef4444" },
                  ]}
                />
              </div>

              {/* Workload */}
              <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800 space-y-2">
                <h4 className="text-xs font-bold text-zinc-400 uppercase">Officer Case Load</h4>
                {casesSummary?.officer_workload.length === 0 ? (
                  <p className="text-xs text-zinc-400">No workload assigned</p>
                ) : (
                  casesSummary?.officer_workload.map((o: any, idx: number) => (
                    <div key={idx} className="flex justify-between text-xs py-1">
                      <span className="text-zinc-500 font-semibold">{o.officer}</span>
                      <span className="font-bold text-zinc-850 dark:text-zinc-200">{o.cases} cases</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Monitoring Schedule */}
      {activeTab === "monitoring" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Total scheduled</span>
              <p className="text-2xl font-bold text-zinc-900 dark:text-white">{monitoringSummary?.total_scheduled}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Reviews Overdue</span>
              <p className="text-2xl font-bold text-red-600">{monitoringSummary?.overdue}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Due this week</span>
              <p className="text-2xl font-bold text-amber-500">{monitoringSummary?.due_this_week}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Due this month</span>
              <p className="text-2xl font-bold text-blue-500">{monitoringSummary?.due_this_month}</p>
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
              Upcoming Reviews Schedule
            </h3>
            <div className="overflow-x-auto rounded-lg border border-zinc-100 dark:border-zinc-800">
              <table className="min-w-full divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
                <thead className="bg-zinc-50 dark:bg-zinc-900">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-bold text-zinc-500">Customer Name</th>
                    <th className="px-4 py-2.5 text-left font-bold text-zinc-500">Next Review Date</th>
                    <th className="px-4 py-2.5 text-left font-bold text-zinc-500">Frequency (Months)</th>
                    <th className="px-4 py-2.5 text-left font-bold text-zinc-500">Last Review Date</th>
                    <th className="px-4 py-2.5 text-left font-bold text-zinc-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-850">
                  {monitoringSummary?.upcoming.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-zinc-400">
                        No upcoming customer reviews scheduled
                      </td>
                    </tr>
                  ) : (
                    monitoringSummary?.upcoming.map((s: any) => (
                      <tr key={s.schedule_id} className="hover:bg-zinc-50 dark:hover:bg-zinc-850">
                        <td className="px-4 py-2.5 font-bold text-zinc-800 dark:text-zinc-200">
                          {s.customer_name}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-zinc-600 dark:text-zinc-400">
                          {s.next_review_date}
                        </td>
                        <td className="px-4 py-2.5 text-zinc-500">
                          Every {s.frequency_months} Months
                        </td>
                        <td className="px-4 py-2.5 font-mono text-zinc-400">
                          {s.last_review_date || "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="rounded bg-teal-50 dark:bg-teal-950/20 text-teal-700 px-2 py-0.5 font-semibold text-[10px] capitalize">
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab: AI Decision Hub */}
      {activeTab === "ai_hub" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 text-center">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Total Agents run</span>
              <p className="text-2xl font-black text-zinc-800 dark:text-white">{aiSummary?.agent_execution.total}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 text-center">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Completed Agents</span>
              <p className="text-2xl font-black text-teal-600">{aiSummary?.agent_execution.completed}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 text-center">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Failed Agents</span>
              <p className="text-2xl font-black text-red-500">{aiSummary?.agent_execution.failed}</p>
            </div>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 text-center">
              <span className="text-[10px] text-zinc-400 uppercase font-semibold">Avg Agent Execution</span>
              <p className="text-2xl font-black text-zinc-800 dark:text-white">{aiSummary?.agent_execution.avg_exec_ms} ms</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Agent execution details logs */}
            <div className="col-span-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                Autonomous Agents Execution Logs
              </h3>
              <div className="space-y-2.5 max-h-96 overflow-y-auto pr-2">
                {aiSummary?.agent_logs.length === 0 ? (
                  <p className="text-xs text-zinc-400 text-center py-6">No recent agent execution</p>
                ) : (
                  aiSummary?.agent_logs.map((log: any, idx: number) => (
                    <div key={idx} className="p-3 bg-zinc-50 dark:bg-zinc-950/20 border border-zinc-150 dark:border-zinc-800 rounded-lg flex justify-between items-center text-xs">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-teal-700 dark:text-teal-400 capitalize">{log.agent_name.replace(/_agent/g, "")} Agent</span>
                          <span className="text-[10px] rounded bg-zinc-200 dark:bg-zinc-800 px-1.5 py-0.5 text-zinc-500">{log.step_name}</span>
                        </div>
                        <span className="text-[10px] text-zinc-400">{new Date(log.created_at).toLocaleString("en-GB")}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-zinc-500 font-mono">{log.execution_time_ms} ms</span>
                        <span className={`font-bold uppercase text-[10px] ${log.has_output ? "text-emerald-600" : "text-red-500"}`}>
                          {log.has_output ? "Done" : "Fail"}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Latest decision risk panel */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4 flex flex-col justify-between">
              <div className="space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400">
                  Latest Case AI Synthesis
                </h3>
                {aiSummary?.latest_case_id ? (
                  <div className="space-y-3">
                    <div>
                      <span className="text-[9px] text-zinc-400 font-bold uppercase">Case ID</span>
                      <p className="font-mono text-xs text-zinc-600 dark:text-zinc-400">{aiSummary.latest_case_id}</p>
                    </div>
                    <div>
                      <span className="text-[9px] text-zinc-400 font-bold uppercase">AI Synthesis Notes</span>
                      <p className="text-xs text-zinc-600 dark:text-zinc-355 line-clamp-6 leading-relaxed italic">
                        "{aiSummary.investigation_summary}"
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-400 italic">No case summaries recorded</p>
                )}
              </div>

              {/* Chart 5: Monthly AML Screenings */}
              <div className="border-t border-zinc-150 dark:border-zinc-800 pt-4 space-y-2">
                <h4 className="text-xs font-bold text-zinc-400 uppercase">Monthly AI Screenings trend</h4>
                <SvgLineChart
                  data={(charts?.monthly_screenings || []).map((t: any) => ({
                    label: t.month,
                    value: t.count,
                  }))}
                  strokeColor="#6366f1"
                  fillColor="rgba(99, 102, 241, 0.1)"
                  height={80}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Activity Feed */}
      {activeTab === "activity" && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-400 flex items-center justify-between">
            <span>Audit Logging Activity Panel (Auto-updates every 30s)</span>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
            </span>
          </h3>

          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
            {activity.length === 0 ? (
              <p className="text-xs text-zinc-400 text-center py-10">No recent operations logged</p>
            ) : (
              activity.map((act) => (
                <div key={act.id} className="p-3 bg-zinc-50 dark:bg-zinc-950/20 border border-zinc-150 dark:border-zinc-800 rounded-xl text-xs flex justify-between gap-3">
                  <div className="space-y-1">
                    <p className="font-bold text-zinc-800 dark:text-zinc-200">
                      {act.label}
                    </p>
                    <p className="text-[10px] text-zinc-400">
                      Entity: <span className="capitalize">{act.entity_name}</span> · ID: <span className="font-mono">{act.entity_id}</span>
                    </p>
                  </div>
                  <div className="text-right text-[10px] text-zinc-450 shrink-0">
                    <p className="font-semibold text-zinc-500">{new Date(act.created_at).toLocaleString("en-GB")}</p>
                    <p className="text-zinc-400">IP: {act.ip_address ?? "system"}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
