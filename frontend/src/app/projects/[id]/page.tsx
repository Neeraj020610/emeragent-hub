"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  FolderGit2,
  Users,
  Plus,
  X,
  Layers,
  CheckCircle2,
  Clock,
  ArrowLeft,
  Calendar,
  Cpu,
  Trash2,
  ChevronRight,
  Activity,
  UserPlus,
  ShieldCheck,
  FileCode,
} from "lucide-react";

interface ProjectMember {
  id: number;
  project_id: number;
  user_id: number;
  role_in_project: string;
  assigned_at: string;
  user_email?: string;
  user_full_name?: string;
}

interface ProjectDetail {
  id: number;
  account_id: number;
  account_name?: string;
  owner_user_id?: number;
  owner_name?: string;
  project_name: string;
  project_key: string;
  description?: string;
  status: string;
  start_date?: string;
  expected_completion_date?: string;
  tags?: string;
  created_at: string;
  total_builds_count: number;
  active_builds_count: number;
  members: ProjectMember[];
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params?.id;
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [builds, setBuilds] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Add Member Modal
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | "">("");
  const [memberRole, setMemberRole] = useState("developer");
  const [memberError, setMemberError] = useState("");

  const loadData = async () => {
    if (!projectId) return;
    setIsLoading(true);
    try {
      const [projData, buildsData, actData, usersData] = await Promise.allSettled([
        apiFetch<ProjectDetail>(`/projects/${projectId}`),
        apiFetch<any[]>(`/jobs?project_id=${projectId}`),
        apiFetch<any[]>(`/projects/${projectId}/activity`),
        apiFetch<any[]>("/users"),
      ]);

      if (projData.status === "fulfilled" && projData.value) {
        setProject(projData.value);
      }
      if (buildsData.status === "fulfilled" && buildsData.value) {
        setBuilds(buildsData.value);
      }
      if (actData.status === "fulfilled" && actData.value) {
        setActivities(actData.value);
      }
      if (usersData.status === "fulfilled" && usersData.value) {
        setUsers(usersData.value);
        if (usersData.value.length > 0 && selectedUserId === "") {
          setSelectedUserId(usersData.value[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load project details:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setMemberError("");
    if (!selectedUserId) return;

    try {
      await apiFetch(`/projects/${projectId}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: Number(selectedUserId),
          role_in_project: memberRole,
        }),
      });
      setIsAddMemberOpen(false);
      loadData();
    } catch (err: any) {
      setMemberError(err.message || "Failed to add member to project.");
    }
  };

  const handleRemoveMember = async (userId: number) => {
    if (!confirm("Are you sure you want to remove this user from the project?")) return;
    try {
      await apiFetch(`/projects/${projectId}/members/${userId}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(`Error: ${err.message || "Failed to remove member"}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">ACTIVE</span>;
      case "PLANNING":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800">PLANNING</span>;
      case "ON_HOLD":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">ON HOLD</span>;
      case "COMPLETED":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-800">COMPLETED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center space-x-2 text-xs text-slate-500">
          <Link href="/projects" className="hover:text-slate-800 flex items-center">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Projects
          </Link>
          <span>/</span>
          <span className="font-semibold text-slate-800">{project?.project_name || `Project #${projectId}`}</span>
        </div>

        {isLoading ? (
          <div className="bg-white p-12 text-center text-slate-400 rounded-xl border">
            Loading project details...
          </div>
        ) : !project ? (
          <div className="bg-white p-12 text-center text-rose-500 rounded-xl border">
            Project not found.
          </div>
        ) : (
          <>
            {/* Header Card */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    {project.project_key}
                  </span>
                  {getStatusBadge(project.status)}
                </div>
                <h1 className="text-xl font-bold text-slate-900 mt-2">{project.project_name}</h1>
                <p className="text-xs text-slate-500 mt-1">
                  Account: <span className="font-medium text-slate-700">{project.account_name}</span> | Owner:{" "}
                  <span className="font-medium text-slate-700">{project.owner_name || "System Admin"}</span>
                </p>
              </div>

              <div className="flex items-center space-x-2">
                <Link
                  href="/builds"
                  className="px-3 py-1.5 text-xs font-medium border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50"
                >
                  View All Builds
                </Link>
                <button
                  onClick={() => setIsAddMemberOpen(true)}
                  className="px-3 py-1.5 text-xs font-semibold bg-indigo-600 text-white rounded-md hover:bg-indigo-700 flex items-center"
                >
                  <UserPlus className="w-3.5 h-3.5 mr-1.5" />
                  Assign Member
                </button>
              </div>
            </div>

            {/* 2-Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column (2 Cols): Overview & Related Builds */}
              <div className="lg:col-span-2 space-y-6">
                {/* Description & Overview */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                  <h3 className="text-sm font-bold text-slate-800 border-b pb-2">Project Overview</h3>
                  <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {project.description || "No project description provided."}
                  </p>

                  <div className="grid grid-cols-3 gap-4 pt-3 border-t text-xs">
                    <div>
                      <span className="text-slate-400 block font-medium">Total Builds</span>
                      <span className="text-slate-800 font-bold font-mono text-sm">{project.total_builds_count}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Active Builds</span>
                      <span className="text-blue-600 font-bold font-mono text-sm">{project.active_builds_count}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Created On</span>
                      <span className="text-slate-800 font-mono text-sm">
                        {new Date(project.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Related Builds */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-800 flex items-center">
                      <Cpu className="w-4 h-4 mr-2 text-indigo-600" />
                      Related Build Requests ({builds.length})
                    </h3>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 text-xs">
                      <thead className="bg-slate-50 text-slate-500 font-medium">
                        <tr>
                          <th className="px-4 py-2.5 text-left">Build Title</th>
                          <th className="px-4 py-2.5 text-left">Priority</th>
                          <th className="px-4 py-2.5 text-left">Status</th>
                          <th className="px-4 py-2.5 text-left">Duration</th>
                          <th className="px-4 py-2.5 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {builds.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="text-center py-6 text-slate-400">
                              No build requests have been scheduled for this project yet.
                            </td>
                          </tr>
                        ) : (
                          builds.map((b) => (
                            <tr key={b.id} className="hover:bg-slate-50">
                              <td className="px-4 py-3">
                                <Link href={`/builds/${b.id}`} className="font-semibold text-indigo-600 hover:text-indigo-800">
                                  #{b.id} — {b.title}
                                </Link>
                              </td>
                              <td className="px-4 py-3">
                                <span className="font-mono text-[11px] font-semibold">{b.priority}</span>
                              </td>
                              <td className="px-4 py-3">
                                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                                  {b.job_status}
                                </span>
                              </td>
                              <td className="px-4 py-3 font-mono text-slate-500">
                                {b.duration_seconds !== null && b.duration_seconds !== undefined
                                  ? `${b.duration_seconds.toFixed(1)}s`
                                  : "—"}
                              </td>
                              <td className="px-4 py-3 text-right">
                                <Link
                                  href={`/builds/${b.id}`}
                                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                                >
                                  View Details &rarr;
                                </Link>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Right Column (1 Col): Members & Activity */}
              <div className="space-y-6">
                {/* Team Members Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b pb-2">
                    <h3 className="text-sm font-bold text-slate-800 flex items-center">
                      <Users className="w-4 h-4 mr-2 text-indigo-600" />
                      Project Team ({project.members.length})
                    </h3>
                    <button
                      onClick={() => setIsAddMemberOpen(true)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                    >
                      + Add
                    </button>
                  </div>

                  {project.members.length === 0 ? (
                    <p className="text-xs text-slate-400">No team members assigned yet.</p>
                  ) : (
                    <div className="space-y-2.5">
                      {project.members.map((m) => (
                        <div key={m.id} className="flex items-center justify-between p-2 rounded bg-slate-50 border text-xs">
                          <div>
                            <span className="font-semibold text-slate-800 block">
                              {m.user_full_name || m.user_email || `User #${m.user_id}`}
                            </span>
                            <span className="text-[11px] text-slate-400 font-mono capitalize">
                              Role: {m.role_in_project}
                            </span>
                          </div>
                          <button
                            onClick={() => handleRemoveMember(m.user_id)}
                            className="text-slate-400 hover:text-rose-600 p-1"
                            title="Remove from project"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Activity Log Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                  <h3 className="text-sm font-bold text-slate-800 border-b pb-2">Project Activity Log</h3>
                  {activities.length === 0 ? (
                    <p className="text-xs text-slate-400">No activity recorded for this project.</p>
                  ) : (
                    <div className="space-y-2 text-xs">
                      {activities.slice(0, 8).map((act) => (
                        <div key={act.id} className="border-b pb-2 last:border-b-0">
                          <span className="font-semibold text-slate-800 block">{act.action}</span>
                          <p className="text-slate-500 text-[11px] mt-0.5">{act.details}</p>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {new Date(act.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Add Member Modal */}
            {isAddMemberOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
                <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 space-y-4">
                  <div className="flex items-center justify-between border-b pb-2">
                    <h3 className="text-sm font-bold text-slate-900">Assign Team Member</h3>
                    <button onClick={() => setIsAddMemberOpen(false)} className="text-slate-400 hover:text-slate-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {memberError && (
                    <div className="bg-rose-50 border border-rose-200 text-rose-700 px-3 py-1.5 rounded text-xs">
                      {memberError}
                    </div>
                  )}

                  <form onSubmit={handleAddMember} className="space-y-3 text-xs">
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Select User</label>
                      <select
                        value={selectedUserId}
                        onChange={(e) => setSelectedUserId(Number(e.target.value))}
                        className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                      >
                        {users.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.full_name} ({u.email})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Project Role</label>
                      <select
                        value={memberRole}
                        onChange={(e) => setMemberRole(e.target.value)}
                        className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                      >
                        <option value="developer">developer</option>
                        <option value="lead">lead</option>
                        <option value="reviewer">reviewer</option>
                        <option value="observer">observer</option>
                      </select>
                    </div>

                    <div className="flex items-center justify-end space-x-2 pt-3 border-t">
                      <button
                        type="button"
                        onClick={() => setIsAddMemberOpen(false)}
                        className="px-3 py-1.5 border rounded-md text-slate-600 hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-1.5 bg-indigo-600 text-white rounded-md font-medium hover:bg-indigo-700"
                      >
                        Add Member
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

