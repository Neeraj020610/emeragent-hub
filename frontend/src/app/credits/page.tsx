"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  Coins,
  TrendingUp,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Plus,
  FileSpreadsheet,
  CheckCircle2,
  Clock,
  Layers,
  Server,
  Zap,
  Lock,
  HelpCircle,
  Sliders,
  Upload,
  ArrowDownRight,
  ArrowUpRight,
  History,
  X,
} from "lucide-react";

interface AccountCreditDetail {
  id: number;
  account_id: number;
  account_name: string;
  starting_balance: string;
  verified_current_balance: string;
  credit_usage: string;
  reserved_credits: string;
  ceiling_percentage: string;
  planned_ceiling_limit: string;
  remaining_eligible_budget: string;
  balance_source: string; // "REAL_PROVIDER", "manual", "csv_import", "UNKNOWN"
  is_eligible: boolean;
  ineligibility_reason?: string;
  universal_api_usage: string;
  platform_build_usage: string;
  updated_at?: string;
}

interface CreditEventLog {
  id: number;
  account_id: number;
  event_type: string; // "deposit", "consume", "adjustment", "refund"
  amount: string;
  balance_after?: string;
  notes?: string;
  event_timestamp: string;
}

export default function CreditsPage() {
  const [budgets, setBudgets] = useState<AccountCreditDetail[]>([]);
  const [events, setEvents] = useState<CreditEventLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [syncingAccountId, setSyncingAccountId] = useState<number | null>(null);
  const [isSyncingAll, setIsSyncingAll] = useState(false);

  // Manual Adjust Modal
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState<number>(6);
  const [manualAvailable, setManualAvailable] = useState("100.00");
  const [manualAllocated, setManualAllocated] = useState("100.00");
  const [manualNotes, setManualNotes] = useState("Administrative balance update");

  // Ceiling Percentage Modal
  const [isCeilingModalOpen, setIsCeilingModalOpen] = useState(false);
  const [ceilingAccount, setCeilingAccount] = useState<AccountCreditDetail | null>(null);
  const [newCeilingPct, setNewCeilingPct] = useState("50.00");

  // CSV Import Modal
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<string | null>(null);

  const loadCreditTelemetry = async () => {
    setIsLoading(true);
    try {
      const [budgetData, eventData] = await Promise.all([
        apiFetch<AccountCreditDetail[]>("/autonomous/budgets"),
        apiFetch<CreditEventLog[]>("/credits/events?limit=25").catch(() => []),
      ]);

      if (budgetData && budgetData.length > 0) {
        setBudgets(budgetData);
        if (!budgetData.some((b) => b.account_id === selectedAccountId)) {
          setSelectedAccountId(budgetData[0].account_id);
        }
      }
      if (eventData) {
        setEvents(eventData);
      }
    } catch (e) {
      console.error("Credit load error:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCreditTelemetry();
  }, []);

  // Sync balance for a specific account via active session scraper
  const handleSyncBalance = async (accountId: number) => {
    setSyncingAccountId(accountId);
    try {
      const res = await apiFetch<{ status: string; available_credits?: number; message?: string }>(
        `/sessions/${accountId}/sync-credits`,
        { method: "POST" }
      );
      if (res && res.available_credits !== undefined && res.available_credits !== null) {
        alert(`Success: Live balance detected: ${res.available_credits} Credits`);
      } else {
        alert(res?.message || "Synced balance successfully.");
      }
      await loadCreditTelemetry();
    } catch (err: any) {
      alert("Sync error: " + (err.message || "Failed to sync credit balance from session."));
    } finally {
      setSyncingAccountId(null);
    }
  };

  // Sync all connected accounts
  const handleSyncAll = async () => {
    setIsSyncingAll(true);
    try {
      const eligible = budgets.filter((b) => b.is_eligible || b.balance_source?.toUpperCase().includes("PROVIDER"));
      if (eligible.length === 0) {
        // Fallback: sync all accounts
        for (const b of budgets) {
          try {
            await apiFetch(`/sessions/${b.account_id}/sync-credits`, { method: "POST" });
          } catch {}
        }
      } else {
        for (const b of eligible) {
          try {
            await apiFetch(`/sessions/${b.account_id}/sync-credits`, { method: "POST" });
          } catch {}
        }
      }
      await loadCreditTelemetry();
    } finally {
      setIsSyncingAll(false);
    }
  };

  // Manual balance submit
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/credits/manual", {
        method: "POST",
        body: JSON.stringify({
          account_id: Number(selectedAccountId),
          available_credits: parseFloat(manualAvailable),
          total_allocated: parseFloat(manualAllocated),
          notes: manualNotes,
        }),
      });
      setIsManualModalOpen(false);
      loadCreditTelemetry();
    } catch (err: any) {
      alert("Error updating credit balance: " + err.message);
    }
  };

  // Ceiling percentage update
  const handleCeilingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ceilingAccount) return;
    try {
      await apiFetch(`/autonomous/budgets/${ceilingAccount.account_id}`, {
        method: "PUT",
        body: JSON.stringify({
          starting_balance: parseFloat(ceilingAccount.starting_balance) || 0,
          ceiling_percentage: parseFloat(newCeilingPct),
          balance_source: ceilingAccount.balance_source,
        }),
      });
      setIsCeilingModalOpen(false);
      setCeilingAccount(null);
      loadCreditTelemetry();
    } catch (err: any) {
      alert("Error updating ceiling limit: " + err.message);
    }
  };

  // CSV Import handler
  const handleCsvSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setCsvUploading(true);
    setCsvResult(null);

    try {
      const formData = new FormData();
      formData.append("file", csvFile);

      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("http://localhost:8000/api/v1/credits/import-csv", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token || ""}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "CSV upload failed" }));
        throw new Error(err.detail || "Upload error");
      }

      const summary = await res.json();
      setCsvResult(
        `Imported ${summary.successful_imports} accounts successfully. ${summary.failed_rows > 0 ? `Failed: ${summary.failed_rows}` : ""}`
      );
      setTimeout(() => {
        setIsCsvModalOpen(false);
        setCsvResult(null);
        setCsvFile(null);
        loadCreditTelemetry();
      }, 1500);
    } catch (err: any) {
      setCsvResult("Error: " + err.message);
    } finally {
      setCsvUploading(false);
    }
  };

  // Aggregated totals
  const totalStarting = budgets.reduce((acc, b) => acc + (parseFloat(b.starting_balance) || 0), 0);
  const totalAvailable = budgets.reduce((acc, b) => acc + (parseFloat(b.verified_current_balance) || 0), 0);
  const totalUsed = budgets.reduce((acc, b) => acc + (parseFloat(b.credit_usage) || 0), 0);
  const totalCeiling = budgets.reduce((acc, b) => acc + (parseFloat(b.planned_ceiling_limit) || 0), 0);
  const totalHeadroom = budgets.reduce((acc, b) => acc + (parseFloat(b.remaining_eligible_budget) || 0), 0);
  const totalApiUsage = budgets.reduce((acc, b) => acc + (parseFloat(b.universal_api_usage) || 0), 0);
  const totalBuildUsage = budgets.reduce((acc, b) => acc + (parseFloat(b.platform_build_usage) || 0), 0);

  // Helper badge for balance source
  const renderSourceBadge = (src: string) => {
    const s = src?.toLowerCase() || "unknown";
    if (s.includes("real") || s.includes("provider") || s.includes("emergent") || s.includes("sync_adapter")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          Verified (Provider)
        </span>
      );
    }
    if (s.includes("manual")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
          <Lock className="w-3 h-3 text-amber-600" />
          Manually Entered
        </span>
      );
    }
    if (s.includes("csv")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-300">
          <FileSpreadsheet className="w-3 h-3 text-blue-600" />
          CSV Import
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-300">
        <HelpCircle className="w-3 h-3 text-slate-400" />
        Unverified (Login Required)
      </span>
    );
  };

  const getAccountName = (accId: number) => {
    const acc = budgets.find((b) => b.account_id === accId);
    return acc ? acc.account_name : `Account #${accId}`;
  };

  return (
    <AppShell>
      {/* Page Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Coins className="w-6 h-6 text-amber-500" />
            Credit Analytics & 50% Budget Guard
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time Emergent balance telemetry, automated 50% ceiling headroom, and multi-account consumption tracking.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleSyncAll}
            disabled={isSyncingAll}
            className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors disabled:opacity-50"
            title="Scrape and sync live balances from active browser sessions"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncingAll ? "animate-spin" : ""}`} />
            {isSyncingAll ? "Syncing Active..." : "Sync All Balances"}
          </button>

          <button
            onClick={() => setIsCsvModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            Import CSV
          </button>

          <button
            onClick={() => setIsManualModalOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Adjust Balance
          </button>

          <button
            onClick={loadCreditTelemetry}
            className="p-2 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 shadow-xs"
            title="Refresh telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Aggregated Pool Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Available Credits</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{totalAvailable.toFixed(2)} Cr</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Starting pool: {totalStarting.toFixed(2)} Cr</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Credits Consumed</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{totalUsed.toFixed(2)} Cr</div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            API: {totalApiUsage.toFixed(2)} Cr • Build: {totalBuildUsage.toFixed(2)} Cr
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Ceiling Limit (50%)</div>
          <div className="text-2xl font-bold text-blue-600 mt-1">{totalCeiling.toFixed(2)} Cr</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Max allowable quota</div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
          <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Remaining Headroom</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{totalHeadroom.toFixed(2)} Cr</div>
          <div className="text-[11px] text-emerald-700 font-semibold mt-0.5">Eligible before rotation</div>
        </div>
      </div>

      {/* Account-Wise Detailed Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs mb-8">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-teal-600" />
            Account-Wise Credit Balances & Ceiling Ledger
          </h2>
          <span className="text-xs text-slate-500">{budgets.length} accounts configured</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Account</th>
                <th className="px-4 py-3">Starting Pool</th>
                <th className="px-4 py-3">Verified Current</th>
                <th className="px-4 py-3">Consumed</th>
                <th className="px-4 py-3">Ceiling ({budgets[0]?.ceiling_percentage || 50}%)</th>
                <th className="px-4 py-3">Eligible Headroom</th>
                <th className="px-4 py-3">Source Provenance</th>
                <th className="px-4 py-3">Worker Eligibility</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {budgets.map((b) => {
                const ceilingLimit = parseFloat(b.planned_ceiling_limit) || 0;
                const committed = parseFloat(b.credit_usage) || 0;
                const pct = ceilingLimit > 0 ? Math.min(100, Math.round((committed / ceilingLimit) * 100)) : 0;
                const isUnknown = b.balance_source?.toUpperCase() === "UNKNOWN" || parseFloat(b.starting_balance) === 0;

                return (
                  <tr key={b.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-4 py-3.5">
                      <div className="font-bold text-slate-900">{b.account_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">ID: #{b.account_id}</div>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-800">
                      {isUnknown ? (
                        <span className="text-slate-400 italic">0.00 Cr</span>
                      ) : (
                        `${parseFloat(b.starting_balance).toFixed(2)} Cr`
                      )}
                    </td>
                    <td className="px-4 py-3.5 font-mono font-semibold">
                      {isUnknown ? (
                        <span className="text-slate-400 italic">0.00 Cr</span>
                      ) : (
                        <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">
                          {parseFloat(b.verified_current_balance).toFixed(2)} Cr
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-amber-700 font-semibold">
                      {parseFloat(b.credit_usage).toFixed(2)} Cr
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-700">
                      {isUnknown ? "0.00 Cr" : `${ceilingLimit.toFixed(2)} Cr`}
                      <div className="text-[10px] text-slate-400">Limit: {b.ceiling_percentage}%</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-mono font-bold text-emerald-600">
                        {parseFloat(b.remaining_eligible_budget).toFixed(2)} Cr
                      </div>
                      <div className="w-24 h-1.5 bg-slate-200 rounded-full mt-1 overflow-hidden">
                        <div
                          className={`h-full ${pct >= 100 ? "bg-rose-500" : pct > 75 ? "bg-amber-500" : "bg-blue-600"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3.5">{renderSourceBadge(b.balance_source)}</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          b.is_eligible
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : b.ineligibility_reason?.includes("Ceiling")
                            ? "bg-rose-100 text-rose-800 border border-rose-300"
                            : "bg-amber-100 text-amber-800 border border-amber-300"
                        }`}
                      >
                        {b.is_eligible ? "Eligible" : b.ineligibility_reason || "Ineligible"}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() => handleSyncBalance(b.account_id)}
                          disabled={syncingAccountId === b.account_id}
                          className="px-2.5 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 shadow-2xs flex items-center gap-1 disabled:opacity-50"
                          title="Scrape genuine balance from Emergent browser"
                        >
                          <RefreshCw className={`w-3 h-3 ${syncingAccountId === b.account_id ? "animate-spin" : ""}`} />
                          Sync
                        </button>
                        <button
                          onClick={() => {
                            setCeilingAccount(b);
                            setNewCeilingPct(b.ceiling_percentage || "50.00");
                            setIsCeilingModalOpen(true);
                          }}
                          className="px-2.5 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 shadow-2xs flex items-center gap-1"
                          title="Customize ceiling percentage"
                        >
                          <Sliders className="w-3 h-3 text-slate-500" />
                          Ceiling
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Credit Activity & Telemetry Ledger */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <History className="w-4 h-4 text-blue-600" />
            Recent Credit Events & Audit History
          </h2>
          <span className="text-xs text-slate-400">{events.length} events logged</span>
        </div>

        {events.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No credit consumption or adjustment events recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Account</th>
                  <th className="px-4 py-2.5">Event Type</th>
                  <th className="px-4 py-2.5">Amount</th>
                  <th className="px-4 py-2.5">Balance After</th>
                  <th className="px-4 py-2.5">Notes & Context</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {events.map((evt) => (
                  <tr key={evt.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-2.5 text-slate-400 font-mono text-[11px]">
                      {new Date(evt.event_timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}{" "}
                      <span className="text-[10px]">
                        ({new Date(evt.event_timestamp).toLocaleDateString()})
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-semibold text-slate-900">
                      {getAccountName(evt.account_id)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          evt.event_type === "deposit"
                            ? "bg-emerald-100 text-emerald-800"
                            : evt.event_type === "consume"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {evt.event_type === "deposit" ? (
                          <ArrowUpRight className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <ArrowDownRight className="w-3 h-3 text-amber-600" />
                        )}
                        {evt.event_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono font-bold text-slate-900">
                      {evt.event_type === "consume" ? "-" : "+"}
                      {parseFloat(evt.amount).toFixed(2)} Cr
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-600">
                      {evt.balance_after ? `${parseFloat(evt.balance_after).toFixed(2)} Cr` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 max-w-md truncate">
                      {evt.notes || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Manual Balance Entry Modal */}
      {isManualModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Adjust Account Credit Balance</h3>
              <button
                onClick={() => setIsManualModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Update balance for an account when external top-ups or resets occur. This will be recorded as Manually Entered.
            </p>

            <form onSubmit={handleManualSubmit} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Select Account</label>
                <select
                  value={selectedAccountId}
                  onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                >
                  {budgets.map((b) => (
                    <option key={b.account_id} value={b.account_id}>
                      {b.account_name} (Current: {parseFloat(b.verified_current_balance).toFixed(2)} Cr)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-700">Available Credits</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={manualAvailable}
                  onChange={(e) => setManualAvailable(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Starting / Allocated Pool</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={manualAllocated}
                  onChange={(e) => setManualAllocated(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Notes / Reason</label>
                <input
                  type="text"
                  value={manualNotes}
                  onChange={(e) => setManualNotes(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsManualModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold"
                >
                  Save Balance
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Ceiling Percentage Adjustment Modal */}
      {isCeilingModalOpen && ceilingAccount && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Adjust Ceiling Limit %</h3>
              <button
                onClick={() => setIsCeilingModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Configure maximum quota allowance for{" "}
              <strong className="text-slate-900">{ceilingAccount.account_name}</strong>. Default is 50.00%.
            </p>

            <form onSubmit={handleCeilingSubmit} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Ceiling Percentage (%)</label>
                <input
                  type="number"
                  step="1"
                  min="5"
                  max="100"
                  required
                  value={newCeilingPct}
                  onChange={(e) => setNewCeilingPct(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 font-mono text-base font-bold"
                />
              </div>

              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-[11px] text-slate-600 space-y-1">
                <div>Starting Pool: {parseFloat(ceilingAccount.starting_balance).toFixed(2)} Cr</div>
                <div className="font-semibold text-blue-700">
                  New Allowable Budget:{" "}
                  {((parseFloat(ceilingAccount.starting_balance) * (parseFloat(newCeilingPct) || 50)) / 100).toFixed(2)}{" "}
                  Cr
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCeilingModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-semibold"
                >
                  Update Ceiling
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CSV Import Modal */}
      {isCsvModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Bulk Import Credits via CSV</h3>
              <button
                onClick={() => setIsCsvModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Upload a CSV file containing balances. Required column headers:
              <br />
              <code className="text-blue-600 font-mono text-[11px]">account_identifier,available_credits,total_allocated</code>
            </p>

            <form onSubmit={handleCsvSubmit} className="space-y-4 text-xs">
              <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-xl p-6 text-center cursor-pointer bg-slate-50">
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="csv-file-input"
                />
                <label htmlFor="csv-file-input" className="cursor-pointer">
                  <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <span className="font-semibold text-blue-600 hover:underline">
                    {csvFile ? csvFile.name : "Click to select CSV file"}
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">UTF-8 encoded comma separated text</div>
                </label>
              </div>

              {csvResult && (
                <div
                  className={`p-3 rounded-lg text-xs font-semibold ${
                    csvResult.startsWith("Error")
                      ? "bg-rose-50 text-rose-700 border border-rose-200"
                      : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  }`}
                >
                  {csvResult}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCsvModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!csvFile || csvUploading}
                  className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-black text-white font-semibold disabled:opacity-50"
                >
                  {csvUploading ? "Uploading..." : "Upload & Sync"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
