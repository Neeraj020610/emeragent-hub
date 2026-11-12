"use client";

import React, { useEffect, useState } from "react";
import { getSession, clearSession } from "@/lib/api";
import {
  Bell,
  Search,
  Menu,
  Plus,
  ShieldCheck,
  Cpu,
  Layers,
  Sparkles,
  ChevronRight,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface TopbarProps {
  onToggleMobileMenu?: () => void;
}

export function Topbar({ onToggleMobileMenu }: TopbarProps) {
  const router = useRouter();
  const [session, setSessionState] = useState<{ role: string; email: string; fullName: string } | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const s = getSession();
    if (s) {
      setSessionState(s);
    }
  }, []);

  const handleLogout = () => {
    clearSession();
    router.push("/login");
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    const q = searchQuery.toLowerCase().trim();
    if (q.includes("build") || q.includes("task") || q.includes("chat")) {
      router.push("/builds");
    } else if (q.includes("credit") || q.includes("budget") || q.includes("balance")) {
      router.push("/credits");
    } else if (q.includes("account") || q.includes("session") || q.includes("otp") || q.includes("key")) {
      router.push("/accounts");
    } else if (q.includes("report") || q.includes("export") || q.includes("metric")) {
      router.push("/reports");
    } else {
      router.push("/accounts");
    }
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200/90 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      {/* Left: Mobile Toggle & Global Search Bar (Autofleet style) */}
      <div className="flex items-center gap-3 sm:gap-4 flex-1 max-w-xl">
        <button
          onClick={onToggleMobileMenu}
          className="lg:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          title="Open Menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <form onSubmit={handleSearchSubmit} className="relative w-full max-w-md hidden sm:block">
          <div className="relative flex items-center">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search accounts, credits, builds, tasks... (Press Ctrl+K)"
              className="w-full pl-9 pr-14 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-hidden focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
            />
            <div className="absolute right-2 flex items-center gap-0.5">
              <kbd className="px-1.5 py-0.5 text-[9px] font-mono text-slate-400 bg-white border border-slate-200 rounded shadow-2xs">
                ⌘K
              </kbd>
            </div>
          </div>
        </form>

        <span className="inline-flex sm:hidden items-center gap-1.5 text-xs font-bold text-slate-900">
          Emergent <span className="text-blue-600">Hub</span>
        </span>
      </div>

      {/* Right: Quick Actions, Notifications & Profile */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Quick Action: Register Account */}
        <Link
          href="/accounts"
          className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200/80 transition-colors shadow-2xs"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Register Account</span>
        </Link>

        {/* Quick Action: Builds / Chat */}
        <Link
          href="/builds?tab=chat"
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-xs"
        >
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>New Build</span>
        </Link>

        {/* Notifications Popover */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 relative transition-colors"
            title="System Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-blue-600" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-xl border border-slate-200 p-3 z-50 animate-in fade-in zoom-in-95">
              <div className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-100 flex items-center justify-between">
                <span>System Notifications</span>
                <span className="text-[10px] text-blue-600 font-semibold bg-blue-50 px-2 py-0.5 rounded-full border border-blue-100">
                  2 Pending
                </span>
              </div>
              <div className="space-y-2 text-left">
                <div className="p-2 rounded-lg bg-amber-50/70 border border-amber-200/60 text-xs">
                  <div className="font-semibold text-amber-900 flex items-center gap-1">
                    <span>MFA / OTP Email Guard Active</span>
                  </div>
                  <div className="text-amber-800 text-[11px] mt-0.5">
                    Live email API is locked in fail-closed safety state pending provider verification.
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 text-xs">
                  <div className="font-semibold text-slate-900 flex items-center justify-between">
                    <span>3 Managed Accounts</span>
                    <span className="text-[10px] text-emerald-600 font-bold">2 Online</span>
                  </div>
                  <div className="text-slate-600 text-[11px] mt-0.5">
                    Persistent browser sessions ready for isolated provider login.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Pill (Autofleet topbar identity) */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
            {session?.fullName ? session.fullName[0].toUpperCase() : "A"}
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-semibold text-slate-900 leading-tight">
              {session?.fullName || "Hub Administrator"}
            </div>
            <div className="text-[10px] text-slate-500 leading-tight flex items-center gap-1 mt-0.5">
              <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider bg-slate-800 text-white">
                {session?.role || "ADMIN"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
