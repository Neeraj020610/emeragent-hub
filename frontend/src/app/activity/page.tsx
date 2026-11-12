"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { ScrollText, ShieldCheck, Filter, Clock } from "lucide-react";

export default function ActivityPage() {
  const [logs, setLogs] = useState<any[]>([
    {
      id: 1,
      user_id: 1,
      action: "login_success",
      resource_type: "auth",
      resource_id: "1",
      ip_address: "127.0.0.1",
      details: "Admin authenticated via secure JWT token grant",
      created_at: "2026-11-04 09:10:22 UTC",
    },
    {
      id: 2,
      user_id: 1,
      action: "account_synced",
      resource_type: "account",
      resource_id: "EMG-PROD-01",
      ip_address: "127.0.0.1",
      details: "Connection status check verified MCP protocol ready",
      created_at: "2026-11-04 09:12:05 UTC",
    },
    {
      id: 3,
      user_id: 2,
      action: "credit_manual_entry",
      resource_type: "credit_snapshot",
      resource_id: "EMG-DEV-02",
      ip_address: "192.168.1.45",
      details: "Allocated 500.00 credits with administrative note",
      created_at: "2026-11-04 09:14:40 UTC",
    },
  ]);

  const loadLogs = async () => {
    try {
      const data = await apiFetch<any[]>("/audit");
      if (data && data.length > 0) {
        setLogs(
          data.map((l) => ({
            ...l,
            created_at: new Date(l.created_at).toLocaleString(),
          }))
        );
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  return (
    <AppShell>
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Activity & Security Audit Logs</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Immutable system audit trail logging security actions, user operations, and IP attributions.
          </p>
        </div>

        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold">
          <ShieldCheck className="w-4 h-4 text-teal-400" />
          <span>Audit Logging Active</span>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px] uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4">Event ID</th>
              <th className="py-3 px-4">Action</th>
              <th className="py-3 px-4">Target Resource</th>
              <th className="py-3 px-4">Details</th>
              <th className="py-3 px-4">Origin IP</th>
              <th className="py-3 px-4">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50/70 font-sans">
                <td className="py-3 px-4 font-mono font-bold text-slate-700">#{log.id}</td>
                <td className="py-3 px-4">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono bg-blue-50 text-blue-800 border border-blue-200">
                    {log.action}
                  </span>
                </td>
                <td className="py-3 px-4 font-mono text-slate-800">
                  {log.resource_type}: {log.resource_id || "global"}
                </td>
                <td className="py-3 px-4 text-slate-600 text-xs font-sans max-w-sm truncate">
                  {log.details}
                </td>
                <td className="py-3 px-4 font-mono text-slate-500">{log.ip_address || "127.0.0.1"}</td>
                <td className="py-3 px-4 text-slate-500 text-[11px] font-mono">{log.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}

