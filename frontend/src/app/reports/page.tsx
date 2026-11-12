"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  BarChart3,
  Download,
  Calendar,
  ArrowUpRight,
  TrendingDown,
  Layers,
  Server,
  FolderGit2,
  CheckCircle2,
  Cpu,
  Clock,
} from "lucide-react";

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<"account" | "project" | "task">("account");
  const [report, setReport] = useState<any>({
    today_consumption: 0,
    monthly_consumption: 0,
    total_available: 0,
    account_reports: [],
  });

  const [tasks, setTasks] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);

  const loadData = async () => {
    try {
      const [summary, pList, tList] = await Promise.all([
        apiFetch<any>("/reports/summary").catch(() => null),
        apiFetch<any[]>("/projects").catch(() => []),
        apiFetch<any[]>("/autonomous/tasks?limit=50").catch(() => []),
      ]);

      if (summary) {
        setReport({
          today_consumption: Number(summary.today_consumption || 0),
          monthly_consumption: Number(summary.monthly_consumption || 0),
          total_available: Number(summary.total_available_credits || 0),
          account_reports: summary.account_reports || [],
        });
      }
      if (pList) setProjects(pList);
      if (tList) setTasks(tList);
    } catch (err) {
      console.error("Reports load error:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <AppShell>
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-600" />
            Platform Usage & Cost Reports
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Comprehensive account-wise, project-wise, and task-wise telemetry, credit expenditure, and execution results.
          </p>
        </div>

        <button
          onClick={() => window.print()}
          className="px-3.5 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Export Report
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Available Credits</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">${report.total_available?.toFixed(2)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Pool-wide balance</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Today's Consumption</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">${report.today_consumption?.toFixed(2)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Burn velocity</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">30-Day Monthly Run</div>
          <div className="text-2xl font-bold text-blue-600 mt-1">${report.monthly_consumption?.toFixed(2)}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Trailing consumption</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Monitored Tasks</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{tasks.length}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Execution records</div>
        </div>
      </div>

      {/* Report Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="flex border-b border-slate-200 bg-slate-50/60 text-xs font-semibold">
          <button
            onClick={() => setActiveTab("account")}
            className={`flex items-center gap-2 px-5 py-3 border-b-2 transition-all ${activeTab === "account"
              ? "border-blue-600 text-blue-600 bg-white"
              : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
          >
            <Server className="w-4 h-4" />
            Account-Wise Breakdown
          </button>

          <button
            onClick={() => setActiveTab("project")}
            className={`flex items-center gap-2 px-5 py-3 border-b-2 transition-all ${activeTab === "project"
              ? "border-blue-600 text-blue-600 bg-white"
              : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
          >
            <FolderGit2 className="w-4 h-4" />
            Project-Wise Usage
          </button>

          <button
            onClick={() => setActiveTab("task")}
            className={`flex items-center gap-2 px-5 py-3 border-b-2 transition-all ${activeTab === "task"
              ? "border-blue-600 text-blue-600 bg-white"
              : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
          >
            <Cpu className="w-4 h-4" />
            Task & Execution Results ({tasks.length})
          </button>
        </div>

        {/* TAB 1: ACCOUNT-WISE */}
        {activeTab === "account" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3">Account Name</th>
                  <th className="px-5 py-3">Identifier</th>
                  <th className="px-5 py-3">Available Balance</th>
                  <th className="px-5 py-3">Consumed Credits</th>
                  <th className="px-5 py-3">Total Allocated</th>
                  <th className="px-5 py-3">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {report.account_reports?.map((a: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3.5 font-bold text-slate-900">{a.account_name}</td>
                    <td className="px-5 py-3.5 font-mono text-blue-600 font-semibold">{a.account_identifier}</td>
                    <td className="px-5 py-3.5 font-mono font-semibold">${Number(a.available_credits).toFixed(2)}</td>
                    <td className="px-5 py-3.5 font-mono text-amber-700 font-semibold">
                      ${Number(a.consumed_credits).toFixed(2)}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-600">${Number(a.total_allocated).toFixed(2)}</td>
                    <td className="px-5 py-3.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 uppercase">
                        {a.balance_source}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 2: PROJECT-WISE */}
        {activeTab === "project" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3">Project Name</th>
                  <th className="px-5 py-3">Key</th>
                  <th className="px-5 py-3">Total Jobs Executed</th>
                  <th className="px-5 py-3">Total Credits Consumed</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {projects.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3.5 font-bold text-slate-900">{p.name}</td>
                    <td className="px-5 py-3.5 font-mono font-semibold text-blue-600">{p.key}</td>
                    <td className="px-5 py-3.5 font-mono">{p.jobs_count} builds</td>
                    <td className="px-5 py-3.5 font-mono text-amber-700 font-semibold">${p.credits_used.toFixed(2)}</td>
                    <td className="px-5 py-3.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 3: TASK & EXECUTION RESULTS */}
        {activeTab === "task" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3">Task ID</th>
                  <th className="px-5 py-3">Title</th>
                  <th className="px-5 py-3">Work Type</th>
                  <th className="px-5 py-3">Credits Cost</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {tasks.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3 font-mono text-blue-600 font-semibold">{t.task_identifier}</td>
                    <td className="px-5 py-3 max-w-xs">
                      <div className="font-semibold text-slate-900 truncate">{t.title}</div>
                      <div className="text-[11px] text-slate-500 truncate">{t.expected_result}</div>
                    </td>
                    <td className="px-5 py-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                        {t.work_type === "VIDEO_CREATION" ? "Video" : "Web/App"}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-mono font-semibold text-slate-900">
                      ${parseFloat(t.actual_credit_cost || "0").toFixed(3)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${t.status === "COMPLETED"
                          ? "bg-emerald-100 text-emerald-800"
                          : t.status === "IN_PROGRESS" || t.status === "CHECKPOINT"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-slate-100 text-slate-600"
                          }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
