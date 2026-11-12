"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  Play,
  Pause,
  RotateCcw,
  Ban,
  Activity,
  ArrowLeft,
  Server,
  Layers,
  ShieldCheck,
  ExternalLink,
  FileCode,
  Calendar,
  User,
  Hash,
  Download,
} from "lucide-react";

interface BuildJobHistory {
  id: number;
  from_status?: string;
  to_status: string;
  worker_id?: string;
  message?: string;
  error_details?: string;
  created_at: string;
}

interface BuildJobDetail {
  id: number;
  project_id: number;
  project_name?: string;
  project_key?: string;
  account_id: number;
  account_name?: string;
  account_email?: string;
  initiated_by_user_id?: number;
  initiator_name?: string;
  title: string;
  job_type: string;
  job_status: string;
  priority: string;
  requirements?: string;
  reference_urls?: string[];
  notes?: string;
  attachments_metadata?: any[];
  expected_completion_date?: string;
  idempotency_key?: string;
  worker_id?: string;
  last_heartbeat_at?: string;
  retry_count: number;
  max_retries: number;
  timeout_seconds: number;
  execution_adapter: string;
  is_mock: boolean;
  started_at?: string;
  paused_at?: string;
  cancelled_at?: string;
  completed_at?: string;
  credits_used: string | number;
  result_summary?: string;
  result_metadata?: string;
  error_details?: string;
  created_at: string;
  updated_at: string;
  assigned_user_name?: string;
  duration_seconds?: number;
  history: BuildJobHistory[];
}

export default function BuildDetailPage() {
  const params = useParams();
  const jobId = params?.id;
  const [job, setJob] = useState<BuildJobDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const loadJob = async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const data = await apiFetch<BuildJobDetail>(`/jobs/${jobId}`);
      setJob(data);
    } catch (err) {
      console.error("Failed to load job details:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadJob();
  }, [jobId]);

  const handleAction = async (actionName: "start" | "pause" | "resume" | "retry" | "cancel") => {
    setActionLoading(true);
    try {
      await apiFetch(`/jobs/${jobId}/${actionName}`, { method: "POST" });
      await loadJob();
    } catch (err: any) {
      alert(`Action error: ${err.message || "Failed to execute state transition"}`);
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-emerald-100 text-emerald-800"><CheckCircle2 className="w-3.5 h-3.5 mr-1" />Completed</span>;
      case "RUNNING":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-blue-100 text-blue-800 animate-pulse"><Activity className="w-3.5 h-3.5 mr-1" />Running</span>;
      case "QUEUED":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-amber-100 text-amber-800"><Clock className="w-3.5 h-3.5 mr-1" />Queued</span>;
      case "STARTING":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-sky-100 text-sky-800"><Cpu className="w-3.5 h-3.5 mr-1" />Starting</span>;
      case "PAUSED":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-purple-100 text-purple-800"><Pause className="w-3.5 h-3.5 mr-1" />Paused</span>;
      case "FAILED":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-rose-100 text-rose-800"><AlertCircle className="w-3.5 h-3.5 mr-1" />Failed</span>;
      case "CANCELLED":
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-slate-200 text-slate-700"><Ban className="w-3.5 h-3.5 mr-1" />Cancelled</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-semibold bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  let parsedMetadata: any = null;
  if (job?.result_metadata) {
    try {
      parsedMetadata = JSON.parse(job.result_metadata);
    } catch {
      // Raw string fallback
    }
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center space-x-2 text-xs text-slate-500">
          <Link href="/builds" className="hover:text-slate-800 flex items-center">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Builds
          </Link>
          <span>/</span>
          <span className="font-semibold text-slate-800">Build #{jobId}</span>
        </div>

        {isLoading ? (
          <div className="bg-white p-12 text-center text-slate-400 rounded-xl border">
            Loading build details...
          </div>
        ) : !job ? (
          <div className="bg-white p-12 text-center text-rose-500 rounded-xl border">
            Build request not found.
          </div>
        ) : (
          <>
            {/* Header Card */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                    ID #{job.id}
                  </span>
                  {getStatusBadge(job.job_status)}
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border">
                    {job.priority} PRIORITY
                  </span>
                  {job.is_mock && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                      MOCK EXECUTION
                    </span>
                  )}
                </div>
                <h1 className="text-xl font-bold text-slate-900 mt-2">{job.title}</h1>
                <p className="text-xs text-slate-500 mt-1 font-mono">
                  Project: {job.project_name} ({job.project_key}) | Account: {job.account_name}
                </p>
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center gap-2">
                {job.job_status === "DRAFT" && (
                  <button
                    onClick={() => handleAction("start")}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 rounded-md shadow-sm"
                  >
                    Queue Job
                  </button>
                )}
                {job.job_status === "RUNNING" && (
                  <button
                    onClick={() => handleAction("pause")}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold bg-purple-600 text-white hover:bg-purple-700 rounded-md shadow-sm flex items-center"
                  >
                    <Pause className="w-3.5 h-3.5 mr-1" /> Pause
                  </button>
                )}
                {job.job_status === "PAUSED" && (
                  <button
                    onClick={() => handleAction("resume")}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 rounded-md shadow-sm flex items-center"
                  >
                    <Play className="w-3.5 h-3.5 mr-1" /> Resume
                  </button>
                )}
                {job.job_status === "FAILED" && (
                  <button
                    onClick={() => handleAction("retry")}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 rounded-md shadow-sm flex items-center"
                  >
                    <RotateCcw className="w-3.5 h-3.5 mr-1" /> Retry
                  </button>
                )}
                {!["COMPLETED", "CANCELLED", "FAILED"].includes(job.job_status) && (
                  <button
                    onClick={() => handleAction("cancel")}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 rounded-md flex items-center"
                  >
                    <Ban className="w-3.5 h-3.5 mr-1" /> Cancel Job
                  </button>
                )}
              </div>
            </div>

            {/* Main Content 2-Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column (2 Cols) */}
              <div className="lg:col-span-2 space-y-6">
                {/* Build Overview Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                  <h3 className="text-sm font-bold text-slate-800 flex items-center border-b pb-2">
                    <Layers className="w-4 h-4 mr-2 text-indigo-600" />
                    Build Execution Overview
                  </h3>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                    <div>
                      <span className="text-slate-400 block font-medium">Job Type</span>
                      <span className="text-slate-800 font-semibold font-mono">{job.job_type}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Associated Account</span>
                      <span className="text-slate-800 font-semibold">{job.account_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Initiated By</span>
                      <span className="text-slate-800 font-semibold">{job.initiator_name || "System"}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Assigned Operator</span>
                      <span className="text-slate-800 font-semibold">{job.assigned_user_name || "Unassigned"}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Credits Consumed</span>
                      <span className="text-slate-800 font-mono font-semibold">{Number(job.credits_used).toFixed(4)} cr</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Execution Duration</span>
                      <span className="text-slate-800 font-mono font-semibold">
                        {job.duration_seconds !== null && job.duration_seconds !== undefined
                          ? `${job.duration_seconds.toFixed(1)}s`
                          : "—"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Requirements & References Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                  <h3 className="text-sm font-bold text-slate-800 border-b pb-2">Requirements & Constraints</h3>
                  <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-3 rounded border">
                    {job.requirements || "No specific requirements provided."}
                  </p>

                  {job.reference_urls && job.reference_urls.length > 0 && (
                    <div className="pt-2">
                      <span className="text-xs font-semibold text-slate-600 block mb-1">Reference Documentation:</span>
                      <div className="space-y-1">
                        {job.reference_urls.map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center font-mono"
                          >
                            <ExternalLink className="w-3.5 h-3.5 mr-1" />
                            {url}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Execution Results & Artifacts Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                  <h3 className="text-sm font-bold text-slate-800 border-b pb-2 flex items-center justify-between">
                    <span>Execution Result Summary</span>
                    {job.is_mock && (
                      <span className="text-[11px] font-normal text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        Disclaimed: Synthetic Mock Output
                      </span>
                    )}
                  </h3>

                  {job.error_details && (
                    <div className="bg-rose-50 border border-rose-200 p-3 rounded-lg text-xs text-rose-800">
                      <strong>Execution Error:</strong> {job.error_details}
                    </div>
                  )}

                  <p className="text-xs text-slate-700">
                    {job.result_summary || "No execution result summary available yet. Build is awaiting worker execution."}
                  </p>

                  {/* Synthetic Artifacts List */}
                  {parsedMetadata?.artifacts && (
                    <div className="pt-3 border-t space-y-2">
                      <span className="text-xs font-semibold text-slate-700 block">Generated Build Artifacts:</span>
                      <div className="space-y-1.5">
                        {parsedMetadata.artifacts.map((art: any, idx: number) => (
                          <div key={idx} className="flex items-center justify-between p-2 rounded bg-slate-50 border text-xs">
                            <div className="flex items-center space-x-2">
                              <FileCode className="w-4 h-4 text-indigo-600" />
                              <span className="font-mono text-slate-800 font-medium">{art.name}</span>
                              <span className="text-slate-400">({art.size_kb} KB)</span>
                            </div>
                            <span className="text-[11px] text-slate-400 font-mono">
                              sha256: {art.sha256 ? `${art.sha256.substring(0, 12)}...` : "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column (1 Col) */}
              <div className="space-y-6">
                {/* Worker & Reliability Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                  <h3 className="text-sm font-bold text-slate-800 flex items-center border-b pb-2">
                    <Server className="w-4 h-4 mr-2 text-indigo-600" />
                    Worker & Queue Engine
                  </h3>

                  <div className="space-y-2.5 text-xs">
                    <div>
                      <span className="text-slate-400 block font-medium">Assigned Worker</span>
                      <span className="font-mono font-semibold text-slate-800">{job.worker_id || "Unclaimed (In Queue)"}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Retry Policy</span>
                      <span className="text-slate-800 font-semibold font-mono">
                        {job.retry_count} of {job.max_retries} max attempts
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Job Timeout Limit</span>
                      <span className="text-slate-800 font-semibold font-mono">{job.timeout_seconds} seconds (1 hr)</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block font-medium">Execution Adapter</span>
                      <span className="font-mono font-semibold text-indigo-600">{job.execution_adapter}</span>
                    </div>
                    {job.idempotency_key && (
                      <div>
                        <span className="text-slate-400 block font-medium">Idempotency Key</span>
                        <span className="font-mono text-[11px] text-slate-600 truncate block">{job.idempotency_key}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Execution Timeline Card */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                  <h3 className="text-sm font-bold text-slate-800 border-b pb-2">Execution History Timeline</h3>

                  {job.history.length === 0 ? (
                    <p className="text-xs text-slate-400">No state transition history recorded.</p>
                  ) : (
                    <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                      {job.history.map((hist) => (
                        <div key={hist.id} className="relative text-xs">
                          <div className="absolute -left-6 top-0.5 w-2.5 h-2.5 rounded-full bg-indigo-600 border-2 border-white" />
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-800">
                              {hist.from_status ? `${hist.from_status} -> ` : ""}
                              {hist.to_status}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {new Date(hist.created_at).toLocaleTimeString()}
                            </span>
                          </div>
                          {hist.message && (
                            <p className="text-slate-600 text-[11px] mt-0.5">{hist.message}</p>
                          )}
                          {hist.worker_id && (
                            <span className="text-[10px] text-slate-400 font-mono block">Worker: {hist.worker_id}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

