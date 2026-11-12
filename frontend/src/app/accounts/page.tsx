"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { INITIAL_ACCOUNTS, AccountItem } from "@/lib/mockData";
import { apiFetch, API_BASE_URL } from "@/lib/api";
import {
  Server,
  Plus,
  Search,
  RefreshCw,
  ExternalLink,
  Shield,
  CheckCircle2,
  AlertTriangle,
  X,
  Link2,
  Unplug,
  Key,
  Users,
  Eye,
  EyeOff,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Lock,
  KeyRound,
  Zap,
  Mail,
  Sliders,
  Copy,
  Check,
  Radio,
  Clock,
  Layers,
} from "lucide-react";
import Link from "next/link";

interface AccountSessionItem {
  id: number;
  account_id: number;
  account_identifier: string;
  account_name: string;
  account_email: string | null;
  ownership_type: string;
  session_token: string;
  auth_method: string;
  session_status: string;
  token_expires_at: string | null;
  last_validated_at: string | null;
  last_active_at: string | null;
  reauth_required: boolean;
  reauth_reason: string | null;
  is_currently_active: boolean;
  browser_profile_isolated: boolean;
  created_at: string;
}

interface MailboxAccount {
  id: number;
  email_address: string;
  employee_name: string;
  provider: string;
  api_base_url: string;
  account_id: number | null;
  ownership_type: string;
  is_active: boolean;
  verified_access: boolean;
  notes: string | null;
  created_at: string;
}

interface OTPRequest {
  id: number;
  mailbox_id: number;
  account_id: number | null;
  account_name: string | null;
  mailbox_email: string | null;
  employee_name: string | null;
  status: string;
  correlation_id: string;
  command_id: string | null;
  attempts_count: number;
  error_reason: string | null;
  sender_filter: string | null;
  subject_filter: string | null;
  expires_at: string;
  received_at: string | null;
  completed_at: string | null;
  created_at: string;
  is_verified: boolean;
}

interface UniversalKeyItem {
  id: number;
  account_id: number;
  account_name: string;
  account_email: string | null;
  key_name: string;
  masked_key: string;
  proxy_base_url: string;
  is_active: boolean;
  validation_status: string;
  validation_message: string | null;
  last_validated_at: string | null;
  created_at: string;
}

function AccountsContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const initialTab =
    tabParam === "sessions"
      ? "sessions"
      : tabParam === "otp"
        ? "otp"
        : tabParam === "keys"
          ? "keys"
          : "directory";

  const [activeTab, setActiveTab] = useState<"directory" | "sessions" | "otp" | "keys">(initialTab);

  // --- Directory State ---
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newIdentifier, setNewIdentifier] = useState("");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [newMailboxEmail, setNewMailboxEmail] = useState("");
  const [newOrg, setNewOrg] = useState("AI Operations");
  const [newOwner, setNewOwner] = useState("Hub Admin");
  const [newOwnershipType, setNewOwnershipType] = useState<"COMPANY_OWNED" | "PERSONAL">("COMPANY_OWNED");
  const [newApiKey, setNewApiKey] = useState("");
  const [newProxyUrl, setNewProxyUrl] = useState("https://proxy.emergent.ai");

  // --- Sessions State ---
  const [sessions, setSessions] = useState<AccountSessionItem[]>([]);
  const [revalidatingId, setRevalidatingId] = useState<number | null>(null);

  // --- OTP State ---
  const [mailboxes, setMailboxes] = useState<MailboxAccount[]>([]);
  const [otpRequests, setOtpRequests] = useState<OTPRequest[]>([]);
  const [revealedOtp, setRevealedOtp] = useState<string | null>(null);

  // --- Universal Keys State ---
  const [keys, setKeys] = useState<UniversalKeyItem[]>([]);

  // Load Directory
  const loadAccounts = async () => {
    try {
      const data = await apiFetch<any[]>("/accounts");
      if (data && data.length > 0) {
        setAccounts(
          data.map((d) => ({
            id: d.id,
            account_identifier: d.account_identifier,
            account_name: d.account_name,
            email: d.email,
            organization: d.organization || "Enterprise",
            owner_name: d.owner_name || "Enterprise Admin",
            ownership_type: (d.ownership_type as any) || "COMPANY_OWNED",
            description: d.description || "",
            status: d.status,
            auth_type: d.auth_type,
            connection_status: (d.connection_status?.toUpperCase() as any) || "DISCONNECTED",
            credit_sync_status: d.credit_sync_status || "manual_only",
            latest_credit_balance: d.latest_credit_balance ? Number(d.latest_credit_balance) : 0,
            last_connected_at: d.last_connected_at ? new Date(d.last_connected_at).toLocaleString() : null,
            last_synced_at: d.last_synced_at ? new Date(d.last_synced_at).toLocaleString() : "Never",
            assigned_members_count: d.assigned_members_count || 1,
            has_saved_password: Boolean(d.has_saved_password),
            is_mock: false,
          }))
        );
      }
    } catch { }
  };

  // Load Sessions
  const loadSessions = async () => {
    try {
      const data = await apiFetch<AccountSessionItem[]>("/sessions");
      if (data) setSessions(data);
    } catch { }
  };

  // Load OTP data
  const loadOTPData = async () => {
    try {
      const [m, r] = await Promise.all([
        apiFetch<MailboxAccount[]>("/otp/mailboxes").catch(() => []),
        apiFetch<OTPRequest[]>("/otp/requests").catch(() => []),
      ]);
      if (m) setMailboxes(m);
      if (r) setOtpRequests(r);
    } catch { }
  };

  // Load Keys
  const loadKeys = async () => {
    try {
      const data = await apiFetch<UniversalKeyItem[]>("/keys");
      if (data) setKeys(data);
    } catch { }
  };

  useEffect(() => {
    loadAccounts();
    loadSessions();
    loadOTPData();
    loadKeys();
  }, []);

  useEffect(() => {
    if (searchParams.get("signin") && accounts.length > 0 && !isLoginModalOpen) {
      openSecureLoginModal(accounts[0]);
    }
    if (searchParams.get("otp_fallback") && accounts.length > 0 && !isLoginModalOpen) {
      openSecureLoginModal(accounts[0]);
      setLoginStep("browser_launched");
      setOtpRetrievalStatus("Phx Email API is disabled globally (EMAIL_API_ENABLED=False) for security verification. Manual OTP entry is available.");
    }
  }, [searchParams, accounts]);

  // Handle Create Account
  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim()) {
      alert("Account Name and Emergent Email are required.");
      return;
    }
    try {
      const created = await apiFetch<any>("/accounts", {
        method: "POST",
        body: JSON.stringify({
          account_identifier: newIdentifier.trim() || undefined,
          account_name: newName.trim(),
          email: newEmail.trim(),
          password: newPassword || undefined,
          mailbox_email: newMailboxEmail.trim() || newEmail.trim(),
          organization: newOrg,
          owner_name: newOwner,
          ownership_type: newOwnershipType,
          auth_type: "oauth",
        }),
      });
      setIsAddModalOpen(false);
      await loadAccounts();
      await loadSessions();

      const savedEmail = newEmail.trim();
      const savedPass = newPassword;
      const savedMb = newMailboxEmail.trim() || savedEmail;
      setNewName("");
      setNewEmail("");
      setNewPassword("");
      setNewMailboxEmail("");
      setNewIdentifier("");

      // Provide immediate Sign In action
      if (created && created.id) {
        const accObj: AccountItem = {
          id: created.id,
          account_identifier: created.account_identifier,
          account_name: created.account_name,
          email: created.email,
          organization: created.organization || "Enterprise",
          owner_name: created.owner_name || "Enterprise Admin",
          ownership_type: created.ownership_type || "COMPANY_OWNED",
          description: created.description || "",
          status: created.status || "active",
          auth_type: created.auth_type || "oauth",
          connection_status: "PENDING",
          credit_sync_status: "manual_only",
          latest_credit_balance: 0,
          last_connected_at: null,
          last_synced_at: "Never",
          assigned_members_count: 1,
          has_saved_password: Boolean(savedPass && savedPass.trim()),
          is_mock: false,
        };
        setSelectedLoginAccount(accObj);
        setLoginEmail(savedEmail);
        setLoginPassword(savedPass);
        setMailboxEmail(savedMb);
        setAutoOtp(true);
        setLoginError(null);
        setOtpRetrievalStatus(null);
        setLoginLoading(true);
        setLoginStep("credentials");
        setIsLoginModalOpen(true);

        // Directly launch the isolated browser profile
        try {
          const resp = await apiFetch<any>(`/sessions/${created.id}/secure-login`, {
            method: "POST",
            body: JSON.stringify({
              email: savedEmail,
              password: savedPass || "interactive_auth",
              mailbox_email: savedMb,
              auto_otp: true,
            }),
          });
          if (resp) {
            setLoginStep("browser_launched");
            setLoginStatusMsg(resp.message || "Isolated browser launched to https://app.emergent.sh.");
            setOtpRetrievalStatus(resp.otp_retrieval_status || null);
          }
        } catch (launchErr: any) {
          setLoginError(launchErr.message || "Failed to launch isolated browser profile.");
          setLoginStep("credentials");
        } finally {
          setLoginLoading(false);
          loadSessions();
          loadAccounts();
        }
      }
    } catch (err: any) {
      alert("Error registering account: " + err.message);
    }
  };

  // Handle Session Validate
  const handleValidateSession = async (sessId: number) => {
    setRevalidatingId(sessId);
    try {
      await apiFetch(`/sessions/${sessId}/validate`, { method: "POST" });
      loadSessions();
    } catch (e) {
      console.error("Session validation error:", e);
    } finally {
      setRevalidatingId(null);
    }
  };

  // Handle Launch Isolated Browser
  const handleLaunchBrowser = async (accountId: number) => {
    try {
      const resp = await apiFetch<any>(`/sessions/${accountId}/launch-browser`, { method: "POST" });
      await loadSessions();
      await loadAccounts();
      const targetAcc = accounts.find((a) => a.id === accountId);
      if (targetAcc) {
        setSelectedLoginAccount(targetAcc);
        setLoginEmail(targetAcc.email || "");
        setLoginPassword("");
        setShowPassword(false);
        setMailboxEmail(targetAcc.email || "");
        setAutoOtp(true);
        setLoginStep("browser_launched");
        setOtpCode("");
        setLoginLoading(false);
        setLoginStatusMsg(resp?.message || "Isolated browser window opened to https://app.emergent.sh.");
        setLoginError(null);
        setOtpRetrievalStatus(null);
        setIsLoginModalOpen(true);
      }
    } catch (e: any) {
      alert("Failed to launch browser: " + (e.message || e));
    }
  };

  // Secure Login Modal State (Phase 6.4)
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [selectedLoginAccount, setSelectedLoginAccount] = useState<AccountItem | null>(null);

  // Broadcast active login account ID so AppShell suppresses re-auth popup for the account currently signing in
  useEffect(() => {
    const activeId = isLoginModalOpen && selectedLoginAccount ? selectedLoginAccount.id : null;
    if (typeof window !== "undefined") {
      (window as any).__activeLoginAccountId = activeId;
      window.dispatchEvent(new CustomEvent("emergent:login-modal-change", { detail: { accountId: activeId } }));
    }
    return () => {
      if (typeof window !== "undefined" && (window as any).__activeLoginAccountId === activeId) {
        (window as any).__activeLoginAccountId = null;
        window.dispatchEvent(new CustomEvent("emergent:login-modal-change", { detail: { accountId: null } }));
      }
    };
  }, [isLoginModalOpen, selectedLoginAccount?.id]);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mailboxEmail, setMailboxEmail] = useState("");
  const [autoOtp, setAutoOtp] = useState(true);
  const [loginStep, setLoginStep] = useState<"credentials" | "browser_launched" | "verified">("credentials");
  const [otpCode, setOtpCode] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginStatusMsg, setLoginStatusMsg] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [otpRetrievalStatus, setOtpRetrievalStatus] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState<string>("Initializing...");
  const [progressLogs, setProgressLogs] = useState<Array<{ time: string; msg: string; level?: string }>>([]);
  const [commandId, setCommandId] = useState<string | null>(null);
  const [detectedOtp, setDetectedOtp] = useState<string | null>(null);
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [copiedOtp, setCopiedOtp] = useState<boolean>(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [syncingAccountId, setSyncingAccountId] = useState<number | null>(null);

  const logsEndRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  // Poll progress while browser_launched
  React.useEffect(() => {
    if (loginStep !== "browser_launched" || !selectedLoginAccount) return;

    let active = true;
    const pollInterval = setInterval(async () => {
      try {
        const prog = await apiFetch<any>(`/sessions/${selectedLoginAccount.id}/login-progress`);
        if (!active || !prog) return;

        if (prog.step) setProgressStep(prog.step);
        if (prog.logs) setProgressLogs(prog.logs);
        if (prog.command_id) setCommandId(prog.command_id);
        if (prog.otp_code) setDetectedOtp(prog.otp_code);
        if (prog.screenshot_url) setScreenshotUrl(prog.screenshot_url);

        if (prog.status === "SUCCESS" || prog.is_complete && !prog.error) {
          setLoginStep("verified");
          loadSessions();
          loadAccounts();
          clearInterval(pollInterval);
        } else if (prog.status === "FAILED" && prog.error) {
          setLoginError(prog.error);
        }
      } catch (err) {
        // Polling failure safely ignored
      }
    }, 1500);

    return () => {
      active = false;
      clearInterval(pollInterval);
    };
  }, [loginStep, selectedLoginAccount]);

  const openSecureLoginModal = (acc: AccountItem) => {
    setSelectedLoginAccount(acc);
    setLoginEmail(acc.email || "");
    setLoginPassword("");
    setShowPassword(false);
    setMailboxEmail(acc.email || "");
    setAutoOtp(true);
    setLoginStep("credentials");
    setOtpCode("");
    setLoginLoading(false);
    setLoginStatusMsg("");
    setLoginError(null);
    setOtpRetrievalStatus(null);
    setProgressLogs([]);
    setCommandId(null);
    setDetectedOtp(null);
    setScreenshotUrl(null);
    setCopiedOtp(false);
    setCopiedField(null);
    setProgressStep("Ready to launch");
    setIsLoginModalOpen(true);
  };

  const handleExecuteSecureLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLoginAccount || !loginEmail) return;

    setLoginLoading(true);
    setLoginError(null);
    setProgressLogs([]);
    setCommandId(null);
    setDetectedOtp(null);
    setScreenshotUrl(null);

    try {
      // Trigger automated login workflow in background
      await apiFetch<any>(`/sessions/${selectedLoginAccount.id}/start-automated-login`, {
        method: "POST",
        body: JSON.stringify({
          email: loginEmail,
          password: loginPassword || "",
          mailbox_email: mailboxEmail || loginEmail,
          auto_otp: autoOtp,
        }),
      });

      setLoginStep("browser_launched");
      setProgressStep("Chrome launching on desktop...");
      loadSessions();
      loadAccounts();
      loadAccounts();
    } catch (err: any) {
      setLoginError(err.message || "Failed to start automated login workflow.");
      setLoginStep("credentials");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSubmitManualOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLoginAccount || !otpCode.trim()) return;
    setLoginLoading(true);
    setLoginError(null);
    try {
      const resp = await apiFetch<any>(`/sessions/${selectedLoginAccount.id}/submit-otp`, {
        method: "POST",
        body: JSON.stringify({ otp_code: otpCode.trim() }),
      });
      if (resp && resp.status === "SUCCESS") {
        setLoginStep("verified");
        loadSessions();
        loadAccounts();
      }
    } catch (err: any) {
      setLoginError(err.message || "Failed to submit OTP code.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleConfirmDashboard = async () => {
    if (!selectedLoginAccount) return;
    setLoginLoading(true);
    setLoginError(null);
    try {
      const resp = await apiFetch<any>(`/sessions/${selectedLoginAccount.id}/confirm-dashboard`, {
        method: "POST",
      });
      if (resp) {
        setLoginStep("verified");
        loadSessions();
        loadAccounts();
      }
    } catch (err: any) {
      setLoginError(err.message || "Failed to confirm dashboard session.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleAbortLogin = async () => {
    if (selectedLoginAccount) {
      try {
        await apiFetch(`/sessions/${selectedLoginAccount.id}/abort-login`, { method: "POST" });
      } catch (e) {
        console.error("Error cancelling login:", e);
      }
    }
    setIsLoginModalOpen(false);
    setSelectedLoginAccount(null);
    setOtpCode("");
    setDetectedOtp(null);
    setProgressLogs([]);
    setLoginError(null);
    await loadAccounts();
    await loadSessions();
  };

  const handleSyncCredits = async (accountId: number) => {
    setSyncingAccountId(accountId);
    try {
      const res = await apiFetch<any>(`/sessions/${accountId}/sync-credits`, { method: "POST" });
      if (res && res.available_credits !== null && res.available_credits !== undefined) {
        alert(`Credit Balance Synced: ${res.available_credits} Credits`);
      } else {
        alert(res?.message || "Sync completed. Check session status.");
      }
      await loadAccounts();
    } catch (err: any) {
      alert("Credit sync failed: " + (err.message || err));
    } finally {
      setSyncingAccountId(null);
    }
  };

  const filteredAccounts = accounts.filter(
    (a) =>
      a.account_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.account_identifier.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.email && a.email.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const renderConnectionBadge = (status: string) => {
    const s = (status || "").toUpperCase();
    if (s === "CONNECTED" || s === "AUTHENTICATED" || s === "ACTIVE") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
          Connected
        </span>
      );
    }
    if (s === "LOGIN_IN_PROGRESS" || s === "PENDING" || s === "PENDING_VERIFICATION") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
          Login in Progress
        </span>
      );
    }
    if (s === "OTP_REQUIRED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse" />
          OTP Required
        </span>
      );
    }
    if (s === "LOGIN_FAILED" || s === "ERROR") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-600" />
          Login Failed
        </span>
      );
    }
    // Default for any unauthenticated / disconnected state:
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-50 text-amber-900 border border-amber-300 shadow-2xs">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
        Login Required
      </span>
    );
  };

  return (
    <AppShell>
      {/* Header & Tabs */}
      <div className="mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <Server className="w-6 h-6 text-blue-600" />
              Emergent Accounts & Authentication
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Centralized management of Emergent accounts, persistent authorized browser sessions, OTP automation, and Universal API keys.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Register Account
            </button>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-2 pt-2 border-b border-slate-200">
          <button
            onClick={() => setActiveTab("directory")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${activeTab === "directory"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
          >
            <Server className="w-3.5 h-3.5" />
            Accounts Directory ({accounts.length})
          </button>

          <button
            onClick={() => setActiveTab("sessions")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${activeTab === "sessions"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Persistent Sessions ({sessions.length})
          </button>

          <button
            onClick={() => setActiveTab("otp")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${activeTab === "otp"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
          >
            <Mail className="w-3.5 h-3.5" />
            OTP Automation & Fallback ({otpRequests.length})
          </button>

          <button
            onClick={() => setActiveTab("keys")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${activeTab === "keys"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
          >
            <KeyRound className="w-3.5 h-3.5" />
            Universal Keys ({keys.length})
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* TAB 1: ACCOUNTS DIRECTORY                                 */}
      {/* ========================================================= */}
      {activeTab === "directory" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search by account name, identifier or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>
            <button
              onClick={loadAccounts}
              className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Account Name</th>
                  <th className="px-4 py-3">Identifier</th>
                  <th className="px-4 py-3">Ownership</th>
                  <th className="px-4 py-3">Auth Type</th>
                  <th className="px-4 py-3">Connection</th>
                  <th className="px-4 py-3">Balance</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredAccounts.map((acc) => (
                  <tr key={acc.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900">{acc.account_name}</div>
                      <div className="text-[11px] text-slate-500">{acc.email || "No email assigned"}</div>
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-blue-600">{acc.account_identifier}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                        {acc.ownership_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px]">{acc.auth_type}</td>
                    <td className="px-4 py-3">
                      {renderConnectionBadge(acc.connection_status)}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                      {acc.connection_status === "CONNECTED" || acc.connection_status === "AUTHENTICATED" ? (
                        acc.latest_credit_balance !== null && acc.latest_credit_balance !== undefined ? (
                          <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-xs">
                            {Number(acc.latest_credit_balance).toLocaleString()} Credits
                          </span>
                        ) : (
                          <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-xs font-sans">
                            0 Credits
                          </span>
                        )
                      ) : (
                        <span className="text-slate-400 font-sans text-xs italic">Login required</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {(acc.connection_status === "CONNECTED" || acc.connection_status === "AUTHENTICATED") && (
                          <button
                            type="button"
                            disabled={syncingAccountId === acc.id}
                            onClick={() => handleSyncCredits(acc.id)}
                            className="px-2 py-1 rounded-md border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-semibold text-xs flex items-center gap-1 transition-colors shadow-2xs disabled:opacity-50"
                            title="Sync live credits from Emergent session"
                          >
                            <RefreshCw className={`w-3 h-3 ${syncingAccountId === acc.id ? "animate-spin text-emerald-600" : ""}`} />
                            <span>{syncingAccountId === acc.id ? "Syncing..." : "Sync Balance"}</span>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => openSecureLoginModal(acc)}
                          className="px-2.5 py-1 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1 transition-colors shadow-2xs"
                        >
                          <KeyRound className="w-3 h-3" />
                          <span>{acc.connection_status === "CONNECTED" ? "Re-auth" : "Sign In"}</span>
                        </button>
                        <Link
                          href={`/accounts/${acc.id}`}
                          className="text-slate-500 hover:text-slate-900 font-medium text-xs"
                        >
                          Details →
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 2: PERSISTENT SESSIONS (Phase 4B Architecture)       */}
      {/* ========================================================= */}
      {activeTab === "sessions" && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-900 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Multi-Account Persistent Session Architecture: </span>
              Maintains independent authenticated browser profiles per account. Log in once on https://app.emergent.sh, and the session persists across restarts without cookie cross-contamination.
            </div>
          </div>

          {sessions.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Registered Accounts Awaiting Persistent Browser Sessions
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Click below to open an isolated browser profile (Chrome or Edge) for any account. Log in to Emergent, and the session will be bound exclusively to that account.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {accounts.map((acc) => (
                  <div
                    key={acc.id}
                    className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3 hover:border-slate-300 transition-colors"
                  >
                    <div>
                      <div className="font-bold text-slate-900 text-xs">{acc.account_name}</div>
                      <div className="text-[11px] font-mono text-slate-500">{acc.account_identifier}</div>
                      <div className="text-[11px] text-slate-600 truncate mt-0.5">{acc.email || "No email assigned"}</div>
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Auth Method: <span className="font-mono uppercase">{acc.auth_type}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleLaunchBrowser(acc.id)}
                      className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Open Isolated Browser</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessions.map((sess) => (
                <div key={sess.id} className="bg-white border border-slate-200 rounded-xl p-4 space-y-3 shadow-xs">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-bold text-slate-900">{sess.account_name}</div>
                      <div className="text-[11px] font-mono text-slate-500">{sess.account_identifier}</div>
                    </div>
                    {renderConnectionBadge(sess.session_status)}
                  </div>

                  <div className="text-xs space-y-1 text-slate-600 pt-1 border-t border-slate-100">
                    <div>
                      Profile Isolation:{" "}
                      <span className="font-semibold text-emerald-700">
                        {sess.browser_profile_isolated ? "Independent Directory" : "Shared"}
                      </span>
                    </div>
                    <div>
                      Auth Method: <span className="font-mono">{sess.auth_method}</span>
                    </div>
                    <div>
                      Last Validated:{" "}
                      <span className="text-slate-500">
                        {sess.last_validated_at ? new Date(sess.last_validated_at).toLocaleTimeString() : "Never"}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 flex items-center justify-between gap-2">
                    <button
                      onClick={() => handleLaunchBrowser(sess.account_id)}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-colors flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3 text-slate-500" />
                      <span>Launch</span>
                    </button>
                    <button
                      onClick={() => handleValidateSession(sess.id)}
                      disabled={revalidatingId === sess.id}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-xs font-semibold text-white transition-colors"
                    >
                      {revalidatingId === sess.id ? "Validating..." : "Validate"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 3: OTP AUTOMATION & FALLBACK                          */}
      {/* ========================================================= */}
      {activeTab === "otp" && (
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 flex items-start gap-2">
            <Mail className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Background OTP Automation Operational: </span>
              Account logins automatically retrieve OTP codes via the backend Phx Email integration. This interface serves for administrative verification, mailbox configuration, and manual OTP fallback.
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
            <h2 className="text-base font-bold text-slate-900">Active OTP Verification Requests</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-2.5">Correlation ID</th>
                    <th className="px-4 py-2.5">Account</th>
                    <th className="px-4 py-2.5">Mailbox</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {otpRequests.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-4 text-center text-slate-400 italic">
                        No active OTP requests pending. Automation idle.
                      </td>
                    </tr>
                  ) : (
                    otpRequests.map((r) => (
                      <tr key={r.id}>
                        <td className="px-4 py-3 font-mono text-blue-600">{r.correlation_id}</td>
                        <td className="px-4 py-3 font-semibold text-slate-900">{r.account_name}</td>
                        <td className="px-4 py-3 text-slate-600">{r.mailbox_email}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${r.status === "completed"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                              }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-500">{new Date(r.created_at).toLocaleTimeString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 4: UNIVERSAL KEYS                                     */}
      {/* ========================================================= */}
      {activeTab === "keys" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {keys.map((k) => (
              <div key={k.id} className="bg-white border border-slate-200 rounded-xl p-4 space-y-3 shadow-xs">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold text-slate-900">{k.key_name}</div>
                    <div className="text-[11px] text-slate-500">{k.account_name}</div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${k.validation_status === "VALID"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-slate-100 text-slate-600"
                      }`}
                  >
                    {k.validation_status}
                  </span>
                </div>

                <div className="text-xs space-y-1 font-mono text-slate-600 pt-1 border-t border-slate-100">
                  <div>Key: {k.masked_key}</div>
                  <div className="text-[11px] truncate text-slate-400">Proxy: {k.proxy_base_url}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Registration Modal (Phase 6.5 Requirement 1: Full Registration) */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
                  <KeyRound className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">Register Emergent Account</h3>
                  <p className="text-[11px] text-slate-500">Configure account credentials and associated Phx mailbox.</p>
                </div>
              </div>
              <button onClick={() => setIsAddModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700">Account Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Emergent Production Main"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white text-xs"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700">Emergent Email *</label>
                <input
                  type="email"
                  required
                  placeholder="e.g. dev-agent@company.com"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white text-xs"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700">Account Password</label>
                <div className="relative mt-1">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    placeholder="Emergent account password (for automated sign-in)"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-9 text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700">Associated Phx Mailbox Email (for Automated OTP)</label>
                <input
                  type="email"
                  placeholder="e.g. mailbox@phx.co.in (or leave blank to use account email)"
                  value={newMailboxEmail}
                  onChange={(e) => setNewMailboxEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700">Ownership Type</label>
                  <select
                    value={newOwnershipType}
                    onChange={(e) => setNewOwnershipType(e.target.value as any)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 focus:outline-none focus:border-blue-500 text-xs"
                  >
                    <option value="COMPANY_OWNED">COMPANY_OWNED</option>
                    <option value="PERSONAL">PERSONAL</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700">Account Identifier (Optional)</label>
                  <input
                    type="text"
                    placeholder="Auto-generated if blank"
                    value={newIdentifier}
                    onChange={(e) => setNewIdentifier(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 focus:outline-none focus:border-blue-500 text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs transition-colors"
                >
                  Register & Sign In →
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SECURE EMERGENT LOGIN MODAL (Phase 6.4 Implementation)     */}
      {/* ========================================================= */}
      {isLoginModalOpen && selectedLoginAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 relative animate-in zoom-in-95 duration-200">
            <button
              onClick={handleAbortLogin}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
              title="Close & Cancel"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Header */}
            <div className="flex items-start gap-3.5 pb-4 border-b border-slate-100">
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Secure Emergent Authentication
                </h3>
                <div className="text-xs text-slate-500 font-mono mt-0.5">
                  Account: <span className="font-semibold text-slate-800">{selectedLoginAccount.account_name}</span> ({selectedLoginAccount.account_identifier})
                </div>
              </div>
            </div>

            {/* Security Notice */}
            <div className="my-4 p-3 bg-blue-50/70 border border-blue-200/80 rounded-xl text-xs text-blue-900 flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Encrypted Credential Vault: </span>
                Passwords are stored with AES Fernet encryption on your local backend and automatically reused for Sign In & Re-auth so you don&apos;t have to re-enter them every time.
              </div>
            </div>

            {loginError && (
              <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{loginError}</span>
              </div>
            )}

            {/* STEP 1: CREDENTIALS INPUT */}
            {loginStep === "credentials" && (
              <form onSubmit={handleExecuteSecureLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700">Emergent Email Address</label>
                  <input
                    type="email"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="w-full mt-1.5 px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-semibold text-slate-700">Emergent Password</label>
                    {selectedLoginAccount.has_saved_password && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        ✓ Saved (Encrypted)
                      </span>
                    )}
                  </div>
                  <div className="relative mt-1.5">
                    <input
                      type={showPassword ? "text" : "password"}
                      required={!selectedLoginAccount.has_saved_password}
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder={
                        selectedLoginAccount.has_saved_password
                          ? "Saved password ready — leave blank to reuse or type new"
                          : "••••••••••••"
                      }
                      className="w-full px-3 py-2 pr-9 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700">Associated Phx Mailbox (for OTP Interception)</label>
                  <input
                    type="email"
                    value={mailboxEmail}
                    onChange={(e) => setMailboxEmail(e.target.value)}
                    placeholder="mailbox@phx.co.in or account email"
                    className="w-full mt-1.5 px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white"
                  />
                  <div className="flex items-center gap-2 mt-2">
                    <input
                      type="checkbox"
                      id="autoOtp"
                      checked={autoOtp}
                      onChange={(e) => setAutoOtp(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <label htmlFor="autoOtp" className="text-xs text-slate-600">
                      Auto-retrieve OTP via Phx Email API if MFA is requested
                    </label>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2.5">
                  <button
                    type="button"
                    onClick={handleAbortLogin}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loginLoading}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>{loginLoading ? "Opening Profile..." : "Launch Isolated Browser & Sign In"}</span>
                  </button>
                </div>
              </form>
            )}

            {/* STEP 2: BROWSER LAUNCHED & LIVE AUTOMATED OTP LOGS */}
            {loginStep === "browser_launched" && (
              <div className="space-y-4">
                {/* Isolated Sandboxed Profile Indicator */}
                <div className="flex items-center justify-between p-3 bg-slate-900 border border-slate-800 text-white rounded-xl shadow-xs">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg">
                      <ShieldCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white flex items-center gap-2">
                        <span>Dedicated Isolated Profile</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          acc_{selectedLoginAccount?.id}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400">Zero personal cookie bleed • Independent multi-account session</div>
                    </div>
                  </div>
                </div>

                {/* Quick Credentials Copy Bar */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-[11px] text-slate-600 font-mono truncate mr-2">{loginEmail}</span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(loginEmail);
                        setCopiedField("email");
                        setTimeout(() => setCopiedField(null), 2000);
                      }}
                      className="text-[11px] text-blue-600 font-bold hover:underline shrink-0"
                    >
                      {copiedField === "email" ? "Copied!" : "Copy Email"}
                    </button>
                  </div>
                  <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-[11px] text-slate-600 font-mono">Password: ••••••••</span>
                    <button
                      type="button"
                      onClick={() => {
                        if (loginPassword) {
                          navigator.clipboard.writeText(loginPassword);
                          setCopiedField("pass");
                          setTimeout(() => setCopiedField(null), 2000);
                        }
                      }}
                      className="text-[11px] text-blue-600 font-bold hover:underline shrink-0"
                    >
                      {copiedField === "pass" ? "Copied!" : "Copy Pass"}
                    </button>
                  </div>
                </div>

                {/* Prominent OTP Received Card */}
                {detectedOtp && (
                  <div className="p-3.5 bg-emerald-50 border-2 border-emerald-500 rounded-xl flex items-center justify-between shadow-xs">
                    <div>
                      <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide block">OTP Received via Phx API</span>
                      <span className="text-2xl font-mono font-black tracking-widest text-emerald-600">{detectedOtp}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(detectedOtp);
                        setCopiedOtp(true);
                        setTimeout(() => setCopiedOtp(false), 2500);
                      }}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
                    >
                      <Check className="w-3.5 h-3.5" />
                      {copiedOtp ? "Copied!" : "Copy OTP"}
                    </button>
                  </div>
                )}

                {/* Live Screen Preview if available */}
                {screenshotUrl && (
                  <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-900 shadow-xs">
                    <div className="px-3 py-1.5 bg-slate-800 text-[11px] text-slate-300 flex items-center justify-between font-mono">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        Live Emergent Page View
                      </span>
                      <span className="text-slate-400 text-[10px]">Auto-refreshed</span>
                    </div>
                    <img
                      src={screenshotUrl.startsWith("http") ? screenshotUrl : `${API_BASE_URL}${screenshotUrl}`}
                      alt="Emergent Screen"
                      className="w-full h-auto max-h-48 object-contain bg-black"
                    />
                  </div>
                )}

                {/* Live Progress Status Bar */}
                <div className="p-3 bg-slate-900 text-white rounded-xl text-xs space-y-2 border border-slate-800 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                      <span className="text-emerald-400 font-bold">Automation Active</span>
                      <span className="text-slate-400 font-mono text-[11px]">— {progressStep}</span>
                    </div>
                    {commandId && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30">
                        Cmd #{commandId}
                      </span>
                    )}
                  </div>

                  {detectedOtp && (
                    <div className="p-2 bg-emerald-500/20 border border-emerald-500/40 rounded-lg flex items-center justify-between text-xs text-emerald-300">
                      <span className="font-semibold">Phx OTP Received:</span>
                      <span className="font-mono font-bold text-base tracking-widest text-emerald-400 bg-slate-900 px-3 py-0.5 rounded border border-emerald-500/40">
                        {detectedOtp}
                      </span>
                    </div>
                  )}

                  {/* Terminal Log Output Window */}
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-mono text-[11px] text-slate-300 max-h-48 overflow-y-auto space-y-1">
                    {progressLogs.length === 0 ? (
                      <div className="text-slate-500 italic">Starting automated browser and Phx OTP listener...</div>
                    ) : (
                      progressLogs.map((lg, idx) => (
                        <div
                          key={idx}
                          className={`flex items-start gap-2 ${lg.level === "error"
                              ? "text-rose-400"
                              : lg.level === "warn"
                                ? "text-amber-400"
                                : lg.msg.includes("OTP FOUND") || lg.msg.includes("verified")
                                  ? "text-emerald-400 font-semibold"
                                  : "text-slate-300"
                            }`}
                        >
                          <span className="text-slate-600 select-none shrink-0">[{lg.time}]</span>
                          <span className="break-all">{lg.msg}</span>
                        </div>
                      ))
                    )}
                    <div ref={logsEndRef} />
                  </div>
                </div>

                {/* Error Banner in Step 2 */}
                {loginError && (
                  <div className="p-3 bg-rose-50 border-2 border-rose-300 rounded-xl text-xs text-rose-800 flex items-start gap-2 shadow-xs">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-bold text-rose-900">Authentication Failed / Rejected</div>
                      <div className="mt-0.5">{loginError}</div>
                    </div>
                  </div>
                )}

                {/* Manual OTP Entry Fallback Form */}
                <form onSubmit={handleSubmitManualOTP} className="space-y-3 pt-2 border-t border-slate-100">
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-bold text-slate-900">
                        Manual OTP Entry (Optional Fallback)
                      </label>
                      <span className="text-[10px] text-slate-400">If needed, enter code manually</span>
                    </div>
                    <div className="flex gap-2 mt-1.5">
                      <input
                        type="text"
                        maxLength={8}
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value)}
                        placeholder="123456"
                        className="flex-1 px-3 py-2 text-center font-mono text-sm tracking-widest bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 font-bold"
                      />
                      <button
                        type="submit"
                        disabled={loginLoading || !otpCode.trim()}
                        className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition-colors disabled:opacity-50"
                      >
                        {loginLoading ? "Verifying..." : "Submit OTP"}
                      </button>
                    </div>
                  </div>
                </form>

                {/* Footer Controls: Cancel / Abort and Confirm Dashboard */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={handleAbortLogin}
                    className="px-3.5 py-2 rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold transition-colors flex items-center gap-1.5 shadow-2xs"
                  >
                    <X className="w-3.5 h-3.5" />
                    <span>Cancel & Abort Login</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmDashboard}
                    disabled={loginLoading}
                    className="px-3 py-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-xs font-semibold text-slate-800 transition-colors flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Confirm Dashboard Opened</span>
                  </button>
                </div>
              </div>
            )}

            {/* STEP 3: VERIFIED ACTIVE */}
            {loginStep === "verified" && (
              <div className="text-center py-6 space-y-3">
                <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-sm">
                  <CheckCircle2 className="w-7 h-7" />
                </div>
                <h4 className="text-sm font-bold text-slate-900">
                  Authentication & Session Verified!
                </h4>
                <p className="text-xs text-slate-500 max-w-xs mx-auto">
                  Persistent session for <span className="font-semibold text-slate-800">{selectedLoginAccount.account_name}</span> is saved and verified ACTIVE.
                </p>
                <div className="pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsLoginModalOpen(false);
                      loadAccounts();
                      loadSessions();
                    }}
                    className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs transition-colors"
                  >
                    Done & Refresh Ledger
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}

export default function AccountsPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-center text-slate-500">Loading Accounts...</div>}>
      <AccountsContent />
    </React.Suspense>
  );
}
