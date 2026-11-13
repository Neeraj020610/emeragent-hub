"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch, getSession } from "@/lib/api";
import {
  Users,
  Plus,
  Shield,
  ShieldAlert,
  UserCheck,
  Mail,
  Lock,
  X,
  Trash2,
  KeyRound,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

interface RoleItem {
  id: number;
  name: string;
  description?: string;
}

interface UserItem {
  id: number;
  email: string;
  full_name: string;
  role_id: number;
  role?: RoleItem;
  is_active: boolean;
  created_at: string;
}

export default function TeamPage() {
  const [currentUserRole, setCurrentUserRole] = useState("ADMIN");
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal: Create User
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<number>(4); // Default to EXECUTIVE if exists
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Modal: Reset Password
  const [userToReset, setUserToReset] = useState<UserItem | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [isResetting, setIsResetting] = useState(false);

  // Modal: Delete User
  const [userToDelete, setUserToDelete] = useState<UserItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const session = getSession();
    if (session) {
      setCurrentUserRole(session.role);
      setCurrentUserId(session.userId);
    }
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [fetchedRoles, fetchedUsers] = await Promise.all([
        apiFetch<RoleItem[]>("/users/roles").catch(() => []),
        apiFetch<UserItem[]>("/users").catch(() => []),
      ]);

      setRoles(fetchedRoles);
      setUsers(fetchedUsers);

      // Default selectedRoleId to EXECUTIVE role if found
      const execRole = fetchedRoles.find((r) => r.name === "EXECUTIVE");
      if (execRole) {
        setSelectedRoleId(execRole.id);
      } else if (fetchedRoles.length > 0) {
        setSelectedRoleId(fetchedRoles[0].id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load team data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: name,
          email: email.trim().toLowerCase(),
          password,
          role_id: Number(selectedRoleId),
          is_active: true,
        }),
      });

      setSuccessMsg(`User '${email}' created successfully! They can now log in.`);
      setIsCreateModalOpen(false);
      setName("");
      setEmail("");
      setPassword("");
      await loadData();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to create user.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userToReset) return;
    setIsResetting(true);
    setError(null);

    try {
      await apiFetch(`/users/${userToReset.id}`, {
        method: "PUT",
        body: JSON.stringify({
          password: newPassword,
        }),
      });

      setSuccessMsg(`Password for '${userToReset.email}' has been successfully updated.`);
      setUserToReset(null);
      setNewPassword("");
      await loadData();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to reset password.");
    } finally {
      setIsResetting(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    setIsDeleting(true);
    setError(null);

    try {
      await apiFetch(`/users/${userToDelete.id}`, {
        method: "DELETE",
      });

      setSuccessMsg(`User '${userToDelete.email}' was removed from the team.`);
      setUserToDelete(null);
      await loadData();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to delete user.");
    } finally {
      setIsDeleting(false);
    }
  };

  // If logged in as Executive, restrict access to this page
  if (currentUserRole === "EXECUTIVE") {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto my-12 p-8 bg-white border border-amber-200 rounded-2xl shadow-sm text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">User Management Restricted</h2>
          <p className="text-sm text-slate-600 leading-relaxed max-w-md mx-auto">
            Executive accounts do not have permission to manage users or create logins. Only <strong>System Administrators</strong> can create user accounts and assign roles.
          </p>
          <div className="pt-2">
            <Link
              href="/accounts"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-sm transition-colors"
            >
              Go to Account Registration →
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const selectedRoleObj = roles.find((r) => r.id === Number(selectedRoleId));

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-slate-900">
                  User & Executive Access Management
                </h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Admin portal to create new executive logins, reset credentials, and enforce role permissions.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            <button
              onClick={loadData}
              disabled={isLoading}
              className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
              title="Refresh users list"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create New User / Executive</span>
            </button>
          </div>
        </div>

        {/* Success or Error Banners */}
        {successMsg && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2 animate-in fade-in">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Role Breakdown Reference Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-xl border border-purple-200 shadow-xs relative overflow-hidden">
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-xs uppercase tracking-wide text-purple-900 flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-purple-600" />
                ADMIN (Administrator)
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">
                Full System Control
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Allowed to generate videos and AI builds, add and delete Emergent accounts, manage credit pools, and create or manage other user accounts.
            </p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-blue-200 shadow-xs relative overflow-hidden">
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-xs uppercase tracking-wide text-blue-900 flex items-center gap-1.5">
                <UserCheck className="w-4 h-4 text-blue-600" />
                EXECUTIVE (Fleet Operations)
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                Account Registration Only
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Main job is to register new Emergent accounts and complete browser OTP verification. <strong>Video generation and account deletion are blocked.</strong>
            </p>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wider">
              Registered System Users ({users.length})
            </h3>
            <span className="text-[11px] text-slate-500">All logins authenticated via BCrypt & JWT</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[10px] uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => {
                  const roleName = u.role?.name || "EXECUTIVE";
                  const isCurrentLoggedAdmin = u.id === currentUserId;

                  return (
                    <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-600 text-xs">
                            {u.full_name?.charAt(0).toUpperCase() || "U"}
                          </div>
                          <div>
                            <div>{u.full_name}</div>
                            {isCurrentLoggedAdmin && (
                              <div className="text-[10px] text-purple-600 font-medium">You (Logged In)</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-600">{u.email}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase inline-flex items-center gap-1 ${
                            roleName === "ADMIN"
                              ? "bg-purple-50 text-purple-700 border border-purple-200"
                              : roleName === "EXECUTIVE"
                              ? "bg-blue-50 text-blue-700 border border-blue-200"
                              : "bg-slate-100 text-slate-700 border border-slate-200"
                          }`}
                        >
                          {roleName === "ADMIN" ? "👑 ADMIN" : "👤 EXECUTIVE"}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          Active
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-500 text-[11px]">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "Active"}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setUserToReset(u);
                              setNewPassword("");
                            }}
                            className="px-2 py-1 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded border border-slate-200 text-xs flex items-center gap-1 transition-colors"
                            title="Reset password for this user"
                          >
                            <KeyRound className="w-3 h-3" />
                            <span>Password</span>
                          </button>

                          {!isCurrentLoggedAdmin && (
                            <button
                              type="button"
                              onClick={() => setUserToDelete(u)}
                              className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                              title="Delete user"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* MODAL 1: Create New User / Executive */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">Create New Team Login</h3>
                  <p className="text-[11px] text-slate-500">Add an Executive or Admin to the platform</p>
                </div>
              </div>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Rahul Sharma"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Email Address (Login ID)</label>
                <div className="relative mt-1">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    required
                    placeholder="rahul@company.org"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Initial Password</label>
                <div className="relative mt-1">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="Minimum 6 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-9 pr-9 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Select Role</label>
                <select
                  value={selectedRoleId}
                  onChange={(e) => setSelectedRoleId(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white font-medium focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                >
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name === "EXECUTIVE"
                        ? "👤 EXECUTIVE — Account Registration & OTP Verification"
                        : r.name === "ADMIN"
                        ? "👑 ADMIN — Full Platform & Video Generation Access"
                        : `${r.name} — ${r.description || ""}`}
                    </option>
                  ))}
                </select>

                <div className="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600">
                  {selectedRoleObj?.name === "EXECUTIVE" ? (
                    <span>
                      👤 <strong>Executive Role:</strong> Main work is registering new Emergent accounts and OTP verification. <strong>Video generation & account deletion will be blocked.</strong>
                    </span>
                  ) : (
                    <span>
                      👑 <strong>Admin Role:</strong> Has complete platform privileges including generating videos, deleting accounts, and managing user logins.
                    </span>
                  )}
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? "Creating User..." : "Create Login Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Reset Password */}
      {userToReset && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-sm w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-slate-900 text-sm">Reset Password</h3>
              <button onClick={() => setUserToReset(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600 mb-3">
              Set a new password for <strong>{userToReset.email}</strong>:
            </p>

            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">New Password</label>
                <input
                  type="password"
                  required
                  placeholder="Enter new password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setUserToReset(null)}
                  className="px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isResetting || !newPassword}
                  className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
                >
                  {isResetting ? "Updating..." : "Update Password"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Delete Confirmation */}
      {userToDelete && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-sm w-full p-6">
            <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mb-3">
              <Trash2 className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-slate-900 text-base">Delete User Account</h3>
            <p className="text-xs text-slate-600 mt-2">
              Are you sure you want to delete <strong>{userToDelete.full_name}</strong> (
              <span className="font-mono">{userToDelete.email}</span>)? They will no longer be able to log in.
            </p>

            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={() => setUserToDelete(null)}
                className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteUser}
                disabled={isDeleting}
                className="px-4 py-2 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-lg shadow-sm disabled:opacity-50"
              >
                {isDeleting ? "Deleting..." : "Delete Permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
