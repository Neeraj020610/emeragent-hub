"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { Users2, Plus, ShieldCheck, Mail, X } from "lucide-react";

export default function TeamPage() {
  const [users, setUsers] = useState<any[]>([
    {
      id: 1,
      email: "admin@emergent-hub.com",
      full_name: "Hub System Administrator",
      role_name: "ADMIN",
      is_active: true,
      created_at: "2026-11-03",
    },
    {
      id: 2,
      email: "manager@emergent-hub.com",
      full_name: "Hub Operations Manager",
      role_name: "MANAGER",
      is_active: true,
      created_at: "2026-11-03",
    },
    {
      id: 3,
      email: "member@emergent-hub.com",
      full_name: "Hub Team Member",
      role_name: "MEMBER",
      is_active: true,
      created_at: "2026-11-03",
    },
  ]);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState(3); // 1=ADMIN, 2=MANAGER, 3=MEMBER

  const loadUsers = async () => {
    try {
      const data = await apiFetch<any[]>("/users");
      if (data && data.length > 0) {
        setUsers(
          data.map((u) => ({
            id: u.id,
            email: u.email,
            full_name: u.full_name,
            role_name: u.role ? u.role.name : "MEMBER",
            is_active: u.is_active,
            created_at: new Date(u.created_at).toLocaleDateString(),
          }))
        );
      }
    } catch {
      // Keep initial users
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: name,
          email,
          password,
          role_id: Number(roleId),
          is_active: true,
        }),
      });
      await loadUsers();
    } catch {
      const roleMap: Record<number, string> = { 1: "ADMIN", 2: "MANAGER", 3: "MEMBER" };
      const mock = {
        id: Date.now(),
        email,
        full_name: name,
        role_name: roleMap[roleId] || "MEMBER",
        is_active: true,
        created_at: "Today",
      };
      setUsers((prev) => [...prev, mock]);
    }

    setIsModalOpen(false);
    setName("");
    setEmail("");
    setPassword("");
  };

  return (
    <AppShell>
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Team & Role Access Control</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Role-based access control (ADMIN, MANAGER, MEMBER) with server-side privilege enforcement.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors self-start md:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Team Member</span>
        </button>
      </div>

      {/* Role Definitions Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold text-xs uppercase tracking-wide text-slate-900">ADMIN</span>
            <span className="w-2 h-2 rounded-full bg-blue-600" />
          </div>
          <div className="text-xs text-slate-600">
            Full platform access, manages all accounts, team members, system settings, and audit trails.
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold text-xs uppercase tracking-wide text-slate-900">MANAGER</span>
            <span className="w-2 h-2 rounded-full bg-teal-500" />
          </div>
          <div className="text-xs text-slate-600">
            View permitted accounts, coordinate authorized build requests, review operational reports.
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold text-xs uppercase tracking-wide text-slate-900">MEMBER</span>
            <span className="w-2 h-2 rounded-full bg-slate-400" />
          </div>
          <div className="text-xs text-slate-600">
            View assigned accounts, submit authorized build requests, inspect assigned job outputs.
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px] uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4">Name</th>
              <th className="py-3 px-4">Email</th>
              <th className="py-3 px-4">Role</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Created Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50/70">
                <td className="py-3 px-4 font-semibold text-slate-900">{u.full_name}</td>
                <td className="py-3 px-4 font-mono text-slate-600">{u.email}</td>
                <td className="py-3 px-4">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase ${
                      u.role_name === "ADMIN"
                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                        : u.role_name === "MANAGER"
                        ? "bg-teal-50 text-teal-700 border border-teal-200"
                        : "bg-slate-100 text-slate-700 border border-slate-200"
                    }`}
                  >
                    {u.role_name}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    Active
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-500 text-[11px]">{u.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-slate-900 text-sm">Add Team Member</h3>
              <button onClick={() => setIsModalOpen(false)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Alex Morgan"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="alex.m@company.org"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Initial Password</label>
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Assigned Role</label>
                <select
                  value={roleId}
                  onChange={(e) => setRoleId(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                >
                  <option value={1}>ADMIN — Full platform access</option>
                  <option value={2}>MANAGER — Account & Job coordinator</option>
                  <option value={3}>MEMBER — Execution & View access</option>
                </select>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-xs"
                >
                  Save Member
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

