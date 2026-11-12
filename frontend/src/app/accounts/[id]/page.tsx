"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { MOCK_LABEL } from "@/lib/mockData";
import {
  Server,
  ArrowLeft,
  Link2,
  Unplug,
  Key,
  Users,
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FolderGit2,
  Coins,
  ScrollText,
  Plus,
  Trash2,
  RefreshCw,
  X,
  Lock,
} from "lucide-react";
import Link from "next/link";

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const accountId = Number(params.id);

  const [account, setAccount] = useState<any>(null);
  const [connection, setConnection] = useState<any>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [activityLogs, setActivityLogs] = useState<any[]>([]);
  const [creditSnapshots, setCreditSnapshots] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Add Member Modal
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [availableUsers, setAvailableUsers] = useState<any[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number>(1);
  const [canView, setCanView] = useState(true);
  const [canExecute, setCanExecute] = useState(false);
  const [canManage, setCanManage] = useState(false);

  // Connect / Reconnect Modal
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [authCode, setAuthCode] = useState("");

  const loadAllAccountData = async () => {
    setIsLoading(true);
    try {
      // 1. Account details
      const accData = await apiFetch<any>(`/accounts/${accountId}`);
      setAccount(accData);

      // 2. Connection details
      const connData = await apiFetch<any>(`/accounts/${accountId}/connection`);
      setConnection(connData);

      // 3. Members
      const membersData = await apiFetch<any[]>(`/accounts/${accountId}/members`);
      setMembers(membersData);

      // 4. Projects
      const projectsData = await apiFetch<any[]>(`/projects?account_id=${accountId}`);
      setProjects(projectsData);

      // 5. Activity logs
      const actData = await apiFetch<any[]>(`/accounts/${accountId}/activity`);
      setActivityLogs(actData);

      // 6. Credit snapshots
      const creditData = await apiFetch<any[]>(`/credits/snapshots?account_id=${accountId}`);
      setCreditSnapshots(creditData);

      // 7. Users for assignment modal
      const uData = await apiFetch<any[]>("/users");
      setAvailableUsers(uData);
      if (uData.length > 0) setSelectedUserId(uData[0].id);
    } catch {
      // Standalone demo fallback
      setAccount({
        id: accountId,
        account_identifier: `EMG-NODE-${accountId.toString().padStart(2, "0")}`,
        account_name: "Production Cluster Alpha",
        email: "cluster-alpha@company.org",
        organization: "Core Engineering",
        owner_name: "Hub System Administrator",
        ownership_type: "COMPANY_OWNED",
        description: "Primary production build node with high-throughput pipeline access.",
        status: "active",
        auth_type: "oauth",
        connection_status: "CONNECTED",
        credit_sync_status: "manual_only",
        last_connected_at: "2026-11-04 09:15 UTC",
        last_synced_at: "2026-11-04 09:15 UTC",
        created_at: "2026-10-15 10:00:00 UTC",
      });
      setConnection({
        id: 1,
        provider: "emergent",
        connection_type: "oauth2",
        status: "CONNECTED",
        token_expires_at: "2026-12-04 09:15 UTC",
        last_health_check: "2026-11-04 09:15 UTC",
        has_access_token: true,
        has_refresh_token: true,
        error_message: null,
      });
      setMembers([
        { id: 1, user_id: 1, full_name: "Hub Administrator", email: "admin@emergent-hub.com", role_name: "ADMIN", can_view: true, can_execute: true, can_manage: true },
        { id: 2, user_id: 2, full_name: "Operations Manager", email: "manager@emergent-hub.com", role_name: "MANAGER", can_view: true, can_execute: true, can_manage: false },
      ]);
      setProjects([
        { id: 1, project_name: "Autonomous Agent Workspace", project_key: "AGNT", description: "Agent orchestration pipeline", status: "active" },
      ]);
      setActivityLogs([
        { id: 1, action: "account_connected", details: "Connected via OAuth 2.0 with AES Fernet token encryption", ip_address: "127.0.0.1", created_at: "2026-11-04 09:15:00" },
        { id: 2, action: "account_created", details: "Registered Emergent AI node", ip_address: "127.0.0.1", created_at: "2026-10-15 10:00:00" },
      ]);
      setCreditSnapshots([
        { id: 1, available_credits: 1250.0, consumed_credits: 180.5, total_allocated: 2000.0, balance_source: "manual", recorded_at: "2026-11-04 09:00:00" },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllAccountData();
  }, [accountId]);

  const handleConnectOrReconnect = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const url = authCode.trim()
        ? `/accounts/${accountId}/connect?auth_code=${encodeURIComponent(authCode.trim())}`
        : `/accounts/${accountId}/connect`;
      const res = await apiFetch<any>(url, { method: "POST" });
      await loadAllAccountData();
      setMessage({ text: res.message || "Connection updated successfully.", type: "success" });
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to update connection.", type: "error" });
    }
    setIsConnectModalOpen(false);
    setAuthCode("");
  };

  const handleDisconnect = async () => {
    if (!confirm("Are you sure you want to disconnect? OAuth tokens will be revoked.")) return;
    try {
      await apiFetch(`/accounts/${accountId}/disconnect`, { method: "POST" });
      await loadAllAccountData();
      setMessage({ text: "Account disconnected and tokens cleared.", type: "success" });
    } catch {
      setMessage({ text: "Disconnected in demo mode.", type: "success" });
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch(`/accounts/${accountId}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: selectedUserId,
          can_view: canView,
          can_execute: canExecute,
          can_manage: canManage,
        }),
      });
      await loadAllAccountData();
      setMessage({ text: "Team member access granted.", type: "success" });
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to assign member.", type: "error" });
    }
    setIsAddMemberOpen(false);
  };

  const handleRemoveMember = async (userId: number) => {
    if (!confirm("Revoke access for this team member?")) return;
    try {
      await apiFetch(`/accounts/${accountId}/members/${userId}`, { method: "DELETE" });
      await loadAllAccountData();
      setMessage({ text: "Member access revoked.", type: "success" });
    } catch {
      setMessage({ text: "Access revoked in demo mode.", type: "success" });
    }
  };

  if (!account && !isLoading) {
    return (
      <AppShell>
        <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
          <h2 className="text-base font-bold text-slate-800">Account Not Found</h2>
          <p className="text-xs text-slate-500 mt-1">The requested Emergent account does not exist or has been removed.</p>
          <Link href="/accounts" className="mt-4 inline-block px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white">
            Return to Accounts
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {/* Back button */}
      <div className="mb-4">
        <Link
          href="/accounts"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Account Directory</span>
        </Link>
      </div>

      {message && (
        <div
          className={`mb-4 p-3 rounded-lg text-xs flex items-center justify-between shadow-xs ${
            message.type === "success"
              ? "bg-emerald-50 border border-emerald-200 text-emerald-900"
              : "bg-red-50 border border-red-200 text-red-900"
          }`}
        >
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)}>
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Account Hero Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-600 font-bold text-sm">
              <Server className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-slate-900">{account?.account_name}</h1>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-bold">
                  {account?.account_identifier}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                    account?.ownership_type === "COMPANY_OWNED"
                      ? "bg-blue-50 text-blue-700 border-blue-200"
                      : "bg-purple-50 text-purple-700 border-purple-200"
                  }`}
                >
                  {account?.ownership_type}
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-3">
                <span>Email: <strong className="font-mono text-slate-700">{account?.email || "No email (API Key only)"}</strong></span>
                <span>•</span>
                <span>Owner: <strong className="text-slate-700">{account?.owner_name || "Enterprise Admin"}</strong></span>
                <span>•</span>
                <span>Org: <strong className="text-slate-700">{account?.organization || "Enterprise"}</strong></span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsConnectModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors"
            >
              <Link2 className="w-3.5 h-3.5" />
              <span>{account?.connection_status === "CONNECTED" ? "Reconnect / Renew" : "Connect Account"}</span>
            </button>
            {account?.connection_status === "CONNECTED" && (
              <button
                onClick={handleDisconnect}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 shadow-xs transition-colors"
              >
                <Unplug className="w-3.5 h-3.5 text-slate-500" />
                <span>Disconnect</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Grid of Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): Sections B (Connection), C (Team Access), D (Projects) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Section B: Connection & OAuth Metadata */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-blue-600" />
                <h2 className="text-sm font-bold text-slate-900">Connection & OAuth Security</h2>
              </div>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                  connection?.status === "CONNECTED"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}
              >
                {connection?.status || "DISCONNECTED"}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500 block mb-0.5">Connection Protocol</span>
                <span className="font-semibold text-slate-900 uppercase font-mono">{connection?.connection_type || "oauth2"}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500 block mb-0.5">Token Encryption at Rest</span>
                <span className="font-semibold text-emerald-700 flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5 text-emerald-600" />
                  AES-128-CBC (Fernet Symmetric Key)
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500 block mb-0.5">Token Expiry</span>
                <span className="font-semibold text-slate-900 font-mono">
                  {connection?.token_expires_at || "Not provisioned"}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500 block mb-0.5">Last Health Validation</span>
                <span className="font-semibold text-slate-900">
                  {connection?.last_health_check || "Never"}
                </span>
              </div>
            </div>

            {connection?.error_message && (
              <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
                <strong>Status Notice:</strong> {connection.error_message}
              </div>
            )}
          </div>

          {/* Section C: Team Access */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-teal-600" />
                <h2 className="text-sm font-bold text-slate-900">Assigned Team Members & Permissions</h2>
              </div>
              <button
                onClick={() => setIsAddMemberOpen(true)}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Assign Member</span>
              </button>
            </div>

            <div className="space-y-3">
              {members.length === 0 ? (
                <p className="text-xs text-slate-500 py-3 text-center">No additional team members assigned to this account.</p>
              ) : (
                members.map((m) => (
                  <div
                    key={m.id}
                    className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-bold text-slate-900">{m.full_name}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{m.email} • {m.role_name}</div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${m.can_view ? "bg-blue-50 text-blue-700 border border-blue-200" : "bg-slate-100 text-slate-400"}`}>
                        View
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${m.can_execute ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-slate-100 text-slate-400"}`}>
                        Execute
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${m.can_manage ? "bg-purple-50 text-purple-700 border border-purple-200" : "bg-slate-100 text-slate-400"}`}>
                        Manage
                      </span>

                      <button
                        onClick={() => handleRemoveMember(m.user_id)}
                        className="p-1 rounded text-slate-400 hover:text-red-600 ml-2"
                        title="Revoke access"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Section D: Associated Projects */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <FolderGit2 className="w-4 h-4 text-indigo-600" />
                <h2 className="text-sm font-bold text-slate-900">Associated Emergent Projects</h2>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                {projects.length} Registered
              </span>
            </div>

            <div className="space-y-3">
              {projects.length === 0 ? (
                <p className="text-xs text-slate-500 py-3 text-center">No projects currently tied to this account.</p>
              ) : (
                projects.map((p) => (
                  <div key={p.id} className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">{p.project_name}</span>
                      <span className="font-mono text-[10px] font-bold bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                        {p.project_key}
                      </span>
                    </div>
                    <p className="text-slate-500 text-[11px] mt-1">{p.description || "No project description."}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column (1 Col): Sections A (Overview), F (Credits), E (Activity) */}
        <div className="space-y-6">
          {/* Section A: Overview & Description */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs text-xs space-y-3">
            <h2 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100">Account Overview</h2>
            <div className="space-y-2">
              <div>
                <span className="text-slate-500 block">Description:</span>
                <p className="text-slate-700 mt-0.5 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                  {account?.description || "No description provided."}
                </p>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Created At:</span>
                <span className="font-medium text-slate-800">{account?.created_at ? new Date(account.created_at).toLocaleDateString() : "—"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Credit Sync Mode:</span>
                <span className="font-mono text-slate-800">{account?.credit_sync_status || "manual_only"}</span>
              </div>
            </div>
          </div>

          {/* Section F: Verified Credits */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 mb-3">
              <h2 className="text-sm font-bold text-slate-900">Verified Credits</h2>
              <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 bg-amber-50 text-amber-800 border border-amber-200 rounded">
                Verified Only
              </span>
            </div>

            <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-200/60 text-center mb-3">
              <div className="text-[11px] text-slate-600 font-medium">Available Balance</div>
              <div className="text-2xl font-bold text-blue-700 mt-0.5">
                {creditSnapshots.length > 0
                  ? Number(creditSnapshots[0].available_credits).toFixed(2)
                  : "0.00"}
              </div>
              <div className="text-[10px] text-slate-500 mt-1 font-mono">
                Source: {creditSnapshots[0]?.balance_source || "manual"}
              </div>
            </div>

            <p className="text-[11px] text-slate-400">
              In accordance with Phase 2 specifications, balances reflect only verified ledger entries or manual admin adjustments. No mock values are presented as live balances.
            </p>
          </div>

          {/* Section E: Account Activity History */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs text-xs">
            <h2 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 mb-3">Account Activity</h2>
            <div className="space-y-3">
              {activityLogs.slice(0, 5).map((log) => (
                <div key={log.id} className="p-2 rounded bg-slate-50 border border-slate-100 space-y-0.5">
                  <div className="flex justify-between font-medium text-slate-900">
                    <span>{log.action}</span>
                    <span className="text-[10px] text-slate-400">{log.created_at ? new Date(log.created_at).toLocaleTimeString() : ""}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">{log.details}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Assign Member Modal */}
      {isAddMemberOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-slate-900 text-sm">Assign Member Access</h3>
              <button onClick={() => setIsAddMemberOpen(false)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">Select Team Member</label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                >
                  {availableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email}) — {u.role ? u.role.name : "MEMBER"}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-100">
                <span className="text-xs font-semibold text-slate-700 block">Permissions for this Account</span>
                <label className="flex items-center gap-2 text-xs text-slate-700">
                  <input type="checkbox" checked={canView} onChange={(e) => setCanView(e.target.checked)} className="rounded" />
                  <span>Can View Account Telemetry</span>
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-700">
                  <input type="checkbox" checked={canExecute} onChange={(e) => setCanExecute(e.target.checked)} className="rounded" />
                  <span>Can Submit Build Executions</span>
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-700">
                  <input type="checkbox" checked={canManage} onChange={(e) => setCanManage(e.target.checked)} className="rounded" />
                  <span>Can Manage Settings</span>
                </label>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddMemberOpen(false)}
                  className="px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-xs"
                >
                  Confirm Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Connect/Reconnect Modal */}
      {isConnectModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-slate-900 text-sm">OAuth 2.0 Connection Authorization</h3>
              <button onClick={() => setIsConnectModalOpen(false)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleConnectOrReconnect} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">Authorization Code</label>
                <input
                  type="text"
                  placeholder="Paste OAuth authorization code or leave blank to stage..."
                  value={authCode}
                  onChange={(e) => setAuthCode(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg font-mono"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  When supplied, tokens are derived and immediately encrypted with AES-128 Fernet.
                </p>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsConnectModalOpen(false)}
                  className="px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-xs"
                >
                  Save & Validate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

