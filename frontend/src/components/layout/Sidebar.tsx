"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Server,
  Coins,
  Cpu,
  BarChart3,
  Layers,
  LogOut,
  X,
  User as UserIcon,
} from "lucide-react";
import { clearSession, getSession } from "@/lib/api";

interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
  badgeColor?: string;
}

// Exactly the five approved main navigation items
const navItems: NavItem[] = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Accounts", href: "/accounts", icon: Server },
  { name: "Credits", href: "/credits", icon: Coins },
  { name: "Builds", href: "/builds", icon: Cpu, badge: "LIVE", badgeColor: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" },
  { name: "Reports", href: "/reports", icon: BarChart3 },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ mobileOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = getSession();

  const handleLogout = () => {
    clearSession();
    router.push("/login");
  };

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#0B132B] border-r border-slate-800/80 text-slate-300 select-none">
      {/* Brand Header (Autofleet-style high-contrast header) */}
      <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800/80 bg-[#080E21] shrink-0">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center text-white shadow-lg shadow-blue-500/25 group-hover:scale-105 transition-transform">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5 leading-none">
              Emergent <span className="text-blue-400 font-extrabold">Hub</span>
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mt-1">
              Central Platform
            </div>
          </div>
        </Link>
        {onClose && (
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation section */}
      <div className="flex-1 px-3 py-5 space-y-6 overflow-y-auto">
        <div>
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Main Navigation
          </div>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              const Icon = item.icon;

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={onClose}
                  className={`group relative flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? "bg-blue-600 text-white font-semibold shadow-md shadow-blue-600/25"
                      : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={`w-4 h-4 transition-transform group-hover:scale-110 ${
                        isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                      }`}
                    />
                    <span className="tracking-wide text-xs">{item.name}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${
                        item.badgeColor || "bg-slate-800 text-slate-300 border-slate-700"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-cyan-300 rounded-r-full" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* User / Profile Information at Bottom (Autofleet requirement) */}
      <div className="p-3 border-t border-slate-800/80 bg-[#080E21] shrink-0 space-y-2">
        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-xs shrink-0">
              <UserIcon className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-white truncate leading-tight">
                {session?.fullName || "Hub Administrator"}
              </div>
              <div className="text-[10px] text-slate-400 truncate flex items-center gap-1.5 mt-0.5">
                <span>{session?.role || "ADMIN"}</span>
                <span>•</span>
                <span className="text-emerald-400 font-medium">Active</span>
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors shrink-0"
            title="Log Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        {/* System Heartbeat */}
        <div className="flex items-center justify-between px-2 text-[10px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            API Connected (Live)
          </span>
          <span className="font-mono text-slate-400 text-[10px]">v1.0</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Fixed Sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 h-screen sticky top-0 z-20">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs transition-opacity"
            onClick={onClose}
          />
          <aside className="relative w-64 max-w-[80vw] h-full z-10 shadow-2xl animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </aside>
        </div>
      )}
    </>
  );
}
