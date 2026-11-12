"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  FolderGit2,
  Plus,
  X,
  Layers,
  CheckCircle2,
  Clock,
  Search,
  Filter,
  ChevronRight,
  Calendar,
  Users,
} from "lucide-react";

interface ProjectItem {
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
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [desc, setDesc] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [projStatus, setProjStatus] = useState("PLANNING");
  const [formError, setFormError] = useState("");

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [projData, accData] = await Promise.allSettled([
        apiFetch<ProjectItem[]>("/projects"),
        apiFetch<any[]>("/accounts"),
      ]);

      if (projData.status === "fulfilled" && projData.value) {
        setProjects(projData.value);
      }
      if (accData.status === "fulfilled" && accData.value) {
        setAccounts(accData.value);
        if (accData.value.length > 0 && accountId === "") {
          setAccountId(accData.value[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load projects data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");

    if (!accountId) {
      setFormError("Please select an associated Emergent Account.");
      return;
    }

    try {
      await apiFetch<ProjectItem>("/projects", {
        method: "POST",
        body: JSON.stringify({
          account_id: Number(accountId),
          project_name: name.trim(),
          project_key: key.trim().toUpperCase(),
          description: desc,
          status: projStatus,
        }),
      });

      setIsModalOpen(false);
      setName("");
      setKey("");
      setDesc("");
      loadData();
    } catch (err: any) {
      setFormError(err.message || "Failed to create project.");
    }
  };

  const filteredProjects = projects.filter((p) => {
    if (statusFilter !== "ALL" && p.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = p.project_name.toLowerCase().includes(q);
      const matchKey = p.project_key.toLowerCase().includes(q);
      const matchDesc = p.description?.toLowerCase().includes(q);
      return matchName || matchKey || matchDesc;
    }
    return true;
  });

  const totalCount = projects.length;
  const activeCount = projects.filter((p) => p.status === "ACTIVE").length;
  const planningCount = projects.filter((p) => p.status === "PLANNING").length;
  const completedCount = projects.filter((p) => p.status === "COMPLETED").length;

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
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Project Management</h1>
            <p className="text-sm text-slate-500 mt-1">
              Organize multi-tenant AI build requests, team assignments, and target environments.
            </p>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Project
          </button>
        </div>

        {/* Overview Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-medium text-slate-500">Total Projects</span>
            <p className="text-2xl font-bold text-slate-900 mt-1">{totalCount}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-medium text-emerald-600">Active Workflows</span>
            <p className="text-2xl font-bold text-emerald-700 mt-1">{activeCount}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-medium text-blue-600">In Planning</span>
            <p className="text-2xl font-bold text-blue-700 mt-1">{planningCount}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-medium text-purple-600">Completed</span>
            <p className="text-2xl font-bold text-purple-700 mt-1">{completedCount}</p>
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search by project name, key..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="PLANNING">PLANNING</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ON_HOLD">ON_HOLD</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>
        </div>

        {/* Project Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-slate-500 font-medium">
                <tr>
                  <th className="px-4 py-3 text-left">Project Name & Key</th>
                  <th className="px-4 py-3 text-left">Associated Account</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Owner</th>
                  <th className="px-4 py-3 text-left">Builds</th>
                  <th className="px-4 py-3 text-left">Created Date</th>
                  <th className="px-4 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">Loading projects...</td>
                  </tr>
                ) : filteredProjects.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      No projects found matching the filter criteria.
                    </td>
                  </tr>
                ) : (
                  filteredProjects.map((proj) => (
                    <tr key={proj.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3.5">
                        <Link href={`/projects/${proj.id}`} className="font-semibold text-indigo-600 hover:text-indigo-800 flex items-center">
                          {proj.project_name}
                          <ChevronRight className="w-3.5 h-3.5 ml-1 text-slate-400" />
                        </Link>
                        <span className="text-[11px] text-slate-400 font-mono block mt-0.5">Key: {proj.project_key}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-medium text-slate-800">{proj.account_name || `Account #${proj.account_id}`}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        {getStatusBadge(proj.status)}
                      </td>
                      <td className="px-4 py-3.5 text-slate-600">
                        {proj.owner_name || "System Admin"}
                      </td>
                      <td className="px-4 py-3.5 font-mono text-slate-700">
                        <span className="font-bold">{proj.total_builds_count}</span> total
                        {proj.active_builds_count > 0 && (
                          <span className="ml-1 text-[11px] text-blue-600">({proj.active_builds_count} active)</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-slate-500 font-mono">
                        {new Date(proj.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <Link
                          href={`/projects/${proj.id}`}
                          className="px-2.5 py-1 text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 rounded inline-block"
                        >
                          Manage
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create Project Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
              <div className="flex items-center justify-between border-b pb-3">
                <h2 className="text-base font-bold text-slate-900">Create New Project</h2>
                <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {formError && (
                <div className="bg-rose-50 border border-rose-200 text-rose-700 px-3 py-2 rounded text-xs">
                  {formError}
                </div>
              )}

              <form onSubmit={handleCreateProject} className="space-y-3 text-xs">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Project Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Distributed Agent Orchestrator"
                    className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Project Key</label>
                    <input
                      type="text"
                      required
                      value={key}
                      onChange={(e) => setKey(e.target.value.toUpperCase())}
                      placeholder="e.g. AGENT-ORCH"
                      className="w-full px-3 py-2 border rounded-md font-mono focus:ring-1 focus:ring-indigo-500 uppercase"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-slate-700 mb-1">Initial Status</label>
                    <select
                      value={projStatus}
                      onChange={(e) => setProjStatus(e.target.value)}
                      className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="PLANNING">PLANNING</option>
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="ON_HOLD">ON_HOLD</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">Associated Emergent Account</label>
                  <select
                    value={accountId}
                    onChange={(e) => setAccountId(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.account_name} ({a.ownership_type})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">Description</label>
                  <textarea
                    rows={3}
                    value={desc}
                    onChange={(e) => setDesc(e.target.value)}
                    placeholder="Project scope, team objectives, and architectural goals..."
                    className="w-full px-3 py-2 border rounded-md focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div className="flex items-center justify-end space-x-2 pt-4 border-t">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-3 py-1.5 border rounded-md text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 bg-indigo-600 text-white rounded-md font-medium hover:bg-indigo-700"
                  >
                    Save Project
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
