"use client";

import React, { ReactNode, useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { apiFetch } from "@/lib/api";
import { AlertCircle, ExternalLink, RefreshCw, X, ShieldAlert } from "lucide-react";

interface AppShellProps {
  children: ReactNode;
  noPadding?: boolean;
}

interface ExpiredSessionNotice {
  account_id: number;
  account_name: string;
  reason: string;
}

export function AppShell({ children, noPadding = false }: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [expiredSession, setExpiredSession] = useState<ExpiredSessionNotice | null>(null);
  const [reauthing, setReauthing] = useState(false);

  // Check for expired or reauth_required sessions (suppressing whichever account is actively logging in)
  const checkSessionHealth = async () => {
    try {
      const sessions = await apiFetch<any[]>("/sessions").catch(() => []);
      if (sessions && Array.isArray(sessions)) {
        const activeLoginId =
          typeof window !== "undefined" ? (window as any).__activeLoginAccountId : null;

        setExpiredSession((prev) => {
          if (prev) {
            if (activeLoginId && prev.account_id === activeLoginId) {
              return null;
            }
            const cur = sessions.find((s) => s.account_id === prev.account_id);
            if (
              !cur ||
              (cur.session_status !== "EXPIRED" && cur.session_status !== "SESSION_EXPIRED")
            ) {
              return null;
            }
            return prev;
          }

          const expired = sessions.find(
            (s) =>
              s.account_id !== activeLoginId &&
              (s.session_status === "EXPIRED" || s.session_status === "SESSION_EXPIRED")
          );
          if (expired) {
            return {
              account_id: expired.account_id,
              account_name: expired.account_name,
              reason: expired.reauth_reason || "Session expired or verification required",
            };
          }
          return null;
        });
      }
    } catch {
      // Fail safely without disrupting page rendering
    }
  };

  useEffect(() => {
    checkSessionHealth();
    const interval = setInterval(checkSessionHealth, 30000);
    const onLoginModalChange = (ev: Event) => {
      const detail = (ev as CustomEvent<{ accountId: number | null }>).detail;
      if (detail?.accountId) {
        setExpiredSession((prev) =>
          prev && prev.account_id === detail.accountId ? null : prev
        );
      }
    };
    window.addEventListener("emergent:login-modal-change", onLoginModalChange);
    return () => {
      clearInterval(interval);
      window.removeEventListener("emergent:login-modal-change", onLoginModalChange);
    };
  }, []);

  const handleLoginAgain = async () => {
    if (!expiredSession) return;
    setReauthing(true);
    try {
      await apiFetch<any>(`/sessions/${expiredSession.account_id}/launch-browser`, {
        method: "POST",
      });
      // Close notice after initiating browser
      setExpiredSession(null);
    } catch (err) {
      console.error("Failed to launch browser for re-auth:", err);
    } finally {
      setReauthing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-row">
      {/* Autofleet-Style Sidebar */}
      <Sidebar mobileOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        <Topbar onToggleMobileMenu={() => setMobileMenuOpen(true)} />
        {noPadding ? (
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-50">
            {children}
          </main>
        ) : (
          <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-7xl w-full mx-auto overflow-y-auto">
            {children}
          </main>
        )}
      </div>

      {/* Session Expiry Modal (Phase 6.3 Requirement 4: Session Expiry Flow) */}
      {expiredSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 relative animate-in zoom-in-95 duration-200">
            <button
              onClick={() => setExpiredSession(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
              title="Dismiss"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700 shrink-0">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-slate-900">
                  Session Re-Authentication Required
                </h3>
                <p className="text-xs text-slate-500">
                  Account session expired. Other accounts remain independently authorized and isolated.
                </p>
              </div>
            </div>

            <div className="mt-4 p-3 bg-amber-50/70 border border-amber-200/80 rounded-xl space-y-1.5 text-xs">
              <div className="flex items-center justify-between text-amber-900 font-semibold">
                <span>Account:</span>
                <span className="font-bold text-slate-900">{expiredSession.account_name}</span>
              </div>
              <div className="flex items-center justify-between text-amber-800 text-[11px]">
                <span>Reason:</span>
                <span>{expiredSession.reason}</span>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setExpiredSession(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Dismiss
              </button>
              <button
                type="button"
                onClick={handleLoginAgain}
                disabled={reauthing}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>{reauthing ? "Launching Browser..." : "Login Again"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
