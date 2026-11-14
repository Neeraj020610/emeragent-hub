"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { setSession } from "@/lib/api";
import { Layers, ShieldCheck, Lock, Mail, ArrowRight, AlertCircle, Shield, UserCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectRolePreset = (role: "SUPERADMIN" | "ADMIN" | "EXECUTIVE") => {
    if (role === "SUPERADMIN") {
      setEmail("superadmin@emergent-hub.com");
      setPassword("SuperAdmin2026!");
    } else if (role === "ADMIN") {
      setEmail("admin@emergent-hub.com");
      setPassword("EmergentAdmin2026!");
    } else {
      setEmail("executive@emergent-hub.com");
      setPassword("Executive2026!");
    }
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Authentication failed. Check credentials.");
      }

      const data = await res.json();
      setSession(data);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Invalid email or password.");
    } finally {
      setIsLoading(false);
    }
  };

  const isCurrentSuper = email === "superadmin@emergent-hub.com";
  const isCurrentAdmin = email === "admin@emergent-hub.com";
  const isCurrentExec = email === "executive@emergent-hub.com";

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        {/* Top Header */}
        <div className="bg-slate-900 p-8 text-white text-center relative">
          <div className="w-12 h-12 mx-auto rounded-xl bg-gradient-to-tr from-blue-600 to-teal-400 flex items-center justify-center shadow-lg shadow-blue-500/20 mb-3">
            <Layers className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold tracking-tight">Emergent Central Hub</h1>
          <p className="text-xs text-slate-400 mt-1">Enterprise Multi-Account & Orchestration Portal</p>

          <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">
            <ShieldCheck className="w-3 h-3 text-teal-400" />
            Role-Based Access Control (RBAC)
          </div>
        </div>

        {/* Quick Role Selector Buttons */}
        <div className="px-8 pt-6 pb-2">
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 block">
            Select Role to Test:
          </label>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => selectRolePreset("SUPERADMIN")}
              className={`p-2 rounded-xl border text-left transition-all ${
                isCurrentSuper
                  ? "bg-amber-50 border-amber-300 text-amber-900 shadow-xs ring-2 ring-amber-500/20"
                  : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <div className="flex items-center gap-1 text-[11px] font-extrabold text-amber-900">
                <Shield className="w-3.5 h-3.5 text-amber-600" />
                <span>SuperAdmin</span>
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5 leading-tight">Supreme Control</div>
            </button>

            <button
              type="button"
              onClick={() => selectRolePreset("ADMIN")}
              className={`p-2 rounded-xl border text-left transition-all ${
                isCurrentAdmin
                  ? "bg-purple-50 border-purple-300 text-purple-900 shadow-xs ring-2 ring-purple-500/20"
                  : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <div className="flex items-center gap-1 text-[11px] font-bold text-purple-900">
                <Shield className="w-3.5 h-3.5 text-purple-600" />
                <span>Admin</span>
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5 leading-tight">Video & Full Control</div>
            </button>

            <button
              type="button"
              onClick={() => selectRolePreset("EXECUTIVE")}
              className={`p-2 rounded-xl border text-left transition-all ${
                isCurrentExec
                  ? "bg-blue-50 border-blue-300 text-blue-900 shadow-xs ring-2 ring-blue-500/20"
                  : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <div className="flex items-center gap-1 text-[11px] font-bold text-blue-900">
                <UserCheck className="w-3.5 h-3.5 text-blue-600" />
                <span>Executive</span>
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5 leading-tight">Fleet Registration</div>
            </button>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="px-8 pb-8 pt-3 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">Account Email</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@emergent-hub.com"
                className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>

          {isCurrentAdmin && (
            <div className="p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-[11px] text-purple-900">
              👑 <strong>Admin Mode:</strong> Full platform control, video/task execution, and user management.
            </div>
          )}
          {isCurrentExec && (
            <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-[11px] text-blue-900">
              👤 <strong>Executive Mode:</strong> Registering new Emergent accounts and OTP verification. Video generation is blocked.
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm shadow-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <span>{isLoading ? "Authenticating..." : "Sign in to Hub"}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="px-8 pb-6 text-center text-xs text-slate-400 border-t border-slate-100 pt-4">
          Strict Role-Based Access Control • BCrypt Hashing • JWT Tokenized
        </div>
      </div>
    </div>
  );
}
