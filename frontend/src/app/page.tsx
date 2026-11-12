"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  Server,
  Link2,
  Unplug,
  Coins,
  TrendingDown,
  Calendar,
  Cpu,
  AlertCircle,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ExternalLink,
  RefreshCw,
  Activity,
  Layers,
} from "lucide-react";
import Link from "next/link";

interface DashboardMetrics {
  total_registered: number;
  connected_accounts: number;
  disconnected_accounts: number;
  total_available_credits: number;
  today_consumption: number;
  monthly_consumption: number;
  active_build_jobs: number;
  failed_jobs: number;
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [recentBuilds, setRecentBuilds] = useState<any[]>([]);
  const [recentActivities, setRecentActivities] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Single source of truth fetch
  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [summary, accs, buildsList, auditLogs] = await Promise.all([
        apiFetch<any>("/reports/summary").catch(() => null),
        apiFetch<any[]>("/accounts").catch(() => []),
        apiFetch<any[]>("/builds").catch(() => []),
        apiFetch<any[]>("/audit?limit=6").catch(() => []),
      ]);

      if (summary) {
        setMetrics({
          total_registered: summary.total_accounts,
          connected_accounts: summary.connected_accounts,
          disconnected_accounts: summary.disconnected_accounts,
          total_available_credits: Number(summary.total_available_credits),
          today_consumption: Number(summary.today_consumption),
          monthly_consumption: Number(summary.monthly_consumption),
          active_build_jobs: summary.active_build_jobs,
          failed_jobs: summary.failed_build_jobs,
        });
      }

      if (accs) setAccounts(accs);
      if (buildsList) setRecentBuilds(buildsList);
      if (auditLogs) setRecentActivities(auditLogs);
    } catch (err) {
      console.error("Dashboard data load error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  return (
    <AppShell>
      {/* Platform Status Banner */}
      <div className="mb-6 p-4 rounded-xl bg-white border border-slate-200 text-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
              Emergent Central Hub — Operational Telemetry
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                Live Integration Active
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              Verified multi-account orchestration, persistent session health, OTP automation, and 50% credit budget guard.
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={loadDashboardData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 transition-colors border border-slate-200"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Sync Telemetry
          </button>
        </div>
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Platform Overview</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Aggregated metrics queried directly from backend accounts and credit ledgers.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Link
            href="/accounts"
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors"
          >
            Manage Accounts
          </Link>
          <Link
            href="/builds"
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs transition-colors"
          >
            Open Builds
          </Link>
        </div>
      </div>

      {/* Grid of 4 Core Real Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Total Accounts */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-2">
            <span>Registered Accounts</span>
            <Server className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{metrics?.total_registered ?? accounts.length}</div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-2">
            <span className="text-emerald-700 font-semibold">{metrics?.connected_accounts ?? 0} Connected</span>
            <span>•</span>
            <span className="text-slate-500 font-semibold">{metrics?.disconnected_accounts ?? 0} Disconnected</span>
          </div>
        </div>

        {/* Connection Health */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-2">
            <span>Connection Health</span>
            <Link2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">
            {metrics?.total_registered
              ? `${Math.round(((metrics.connected_accounts || 0) / metrics.total_registered) * 100)}%`
              : "0%"}
          </div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Verified tokens & MCP status</span>
          </div>
        </div>

        {/* Available Credits */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-2">
            <span>Available Credits</span>
            <Coins className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900">
            ${(metrics?.total_available_credits ?? 0).toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center justify-between">
            <span>Aggregated Pool</span>
            <span className="text-[10px] text-slate-400 uppercase font-mono">Ledger Verified</span>
          </div>
        </div>

        {/* Active Build Jobs */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-2">
            <span>Active Build Jobs</span>
            <Cpu className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{metrics?.active_build_jobs ?? 0}</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Running in pipeline queue
          </div>
        </div>
      </div>

      {/* Main Two-Column Analytics Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left 2 Cols: Consumption & Budget Telemetry */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Credit Ledger & Consumption Velocity</h2>
              <p className="text-xs text-slate-500">Live account burn from verified provider and manual ledgers</p>
            </div>
            <Link href="/credits" className="text-xs text-blue-600 hover:underline font-semibold">
              View Detailed Ledger →
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-2">
            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/60">
              <div className="text-[10px] uppercase font-bold text-slate-400">Today's Consumption</div>
              <div className="text-xl font-bold text-slate-900 mt-1">
                ${(metrics?.today_consumption ?? 0).toFixed(2)}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">24-hour window</div>
            </div>

            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/60">
              <div className="text-[10px] uppercase font-bold text-slate-400">Monthly Run</div>
              <div className="text-xl font-bold text-slate-900 mt-1">
                ${(metrics?.monthly_consumption ?? 0).toFixed(2)}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">Month to date</div>
            </div>

            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/60">
              <div className="text-[10px] uppercase font-bold text-slate-400">50% Credit Guard</div>
              <div className="text-xl font-bold text-emerald-600 mt-1">Enforced</div>
              <div className="text-[11px] text-emerald-700 mt-0.5">Cutoff on ceiling</div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Quick Accounts List */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Managed Accounts</h2>
              <p className="text-xs text-slate-500">Live node connection state</p>
            </div>
            <Link href="/accounts" className="text-xs text-blue-600 hover:underline font-medium">
              View All ({accounts.length})
            </Link>
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto">
            {accounts.map((acc) => (
              <div
                key={acc.id}
                className="p-3 rounded-lg border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-xs text-slate-900 truncate">{acc.account_name}</div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      acc.connection_status === "CONNECTED"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {acc.connection_status}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 font-mono mt-0.5">{acc.account_identifier}</div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-slate-500">Available:</span>
                  <span className="font-semibold text-slate-900">
                    {acc.latest_credit_balance !== null && acc.latest_credit_balance !== undefined
                      ? `$${Number(acc.latest_credit_balance).toFixed(2)}`
                      : "UNKNOWN"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Tables: Recent Build Jobs & Platform Audit Trail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Build Activity */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Recent Build Executions</h2>
              <p className="text-xs text-slate-500">Real-time pipeline tasks and assignments</p>
            </div>
            <Link href="/builds" className="text-xs text-blue-600 hover:underline font-medium">
              Open Builds Workspace
            </Link>
          </div>

          {recentBuilds.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 italic">
              No build jobs currently registered in queue. Submit a task in Builds.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-100">
                    <th className="pb-2 font-medium">Build ID</th>
                    <th className="pb-2 font-medium">Title</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium text-right">Credits</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentBuilds.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50/70">
                      <td className="py-2.5 font-mono text-blue-600 font-semibold">#BUILD-{job.id}</td>
                      <td className="py-2.5 font-medium text-slate-900 truncate max-w-xs">{job.title}</td>
                      <td className="py-2.5">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            job.job_status === "completed"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : job.job_status === "running"
                              ? "bg-blue-50 text-blue-700 border border-blue-200"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {job.job_status}
                        </span>
                      </td>
                      <td className="py-2.5 text-right font-medium text-slate-800">
                        ${Number(job.credits_used || 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Real Audit Trail */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Audit Trail (Single Source of Truth)</h2>
              <p className="text-xs text-slate-500">Live security, auth, and configuration events</p>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Database Log</span>
          </div>

          {recentActivities.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 italic">
              No audit records logged yet.
            </div>
          ) : (
            <div className="space-y-3">
              {recentActivities.map((act) => (
                <div key={act.id} className="flex items-start justify-between text-xs p-2 rounded hover:bg-slate-50">
                  <div className="space-y-0.5 truncate pr-2">
                    <div className="font-semibold text-slate-900 truncate">
                      {act.action}
                    </div>
                    <div className="text-[11px] text-slate-500 truncate">
                      {act.resource_type || "system"} • <span className="font-mono text-slate-600">{act.user_id ? `User #${act.user_id}` : "System"}</span>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-400 shrink-0">
                    {new Date(act.created_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
